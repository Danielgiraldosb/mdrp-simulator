"""
Gurobi callback for the hierarchical model (épica §4).

What it does on each event:

  MULTIOBJ  closes the previous pass (takes its final incumbent), announces
            the next one (name, priority, pass number).
  MESSAGE   parses the Gurobi log: "Multi-objectives: optimize objective N
            (name)", "Optimal solution found", "Time limit reached", "Solve
            interrupted", "Explored N nodes (...) in X seconds (W work units)".
            Zero cost and the most reliable source of pass boundaries.
  MIPSOL    new incumbent: ONE cbGetSolution over every x, structure
            indicators (orders covered, couriers used, lateness, minutes),
            progress history, partial publication (throttled).
  MIP       dual bound and GAP -> progress = 100 - GAP; heartbeat; applies
            skip / stop / stop_after.

Every early termination writes its ``end_reason`` at the point that decides
it (épica §4.5).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import gurobipy as gp
from gurobipy import GRB

from .objectives import MULTI_OBJ_FACTOR, MAIN_OBJECTIVE

_RE_PASS = re.compile(r'Multi-objectives: optimize objective (\d+) \(([^)]*)\)')
_RE_EXPLORED = re.compile(r'Explored (\d+) nodes \((\d+) simplex iterations\) in ([\d.]+) seconds(?: \(([\d.]+) work units\))?')
_RE_OPTIMAL = re.compile(r'Optimal solution found')
_RE_TIME = re.compile(r'Time limit reached')
_RE_INTERRUPTED = re.compile(r'Solve interrupted')
_RE_BOUND = re.compile(r'Best objective ([-\d.e+]+), best bound ([-\d.e+]+), gap ([\d.e+%-]+)')

PARTIAL_MIN_INTERVAL_S = 2.0
PARTIAL_HEARTBEAT_S = 20.0


def progress_from_gap(best: Optional[float], bound: Optional[float]) -> float:
    """100 - GAP, clipped to [0, 100]; 0 without an incumbent."""
    if best is None or bound is None:
        return 0.0
    if abs(best) > 1e99 or abs(bound) > 1e99:
        return 0.0
    denom = max(abs(best), 1e-9)
    gap = abs(bound - best) / denom
    return max(0.0, min(100.0, 100.0 * (1.0 - gap)))


@dataclass
class PassStats:
    name: str
    priority: int
    index: int                 # Gurobi objective index
    pass_no: int               # 1-based order of execution
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    first_incumbent_s: Optional[float] = None
    last_improvement_s: Optional[float] = None
    proof_s: Optional[float] = None
    value: Optional[float] = None
    bound: Optional[float] = None
    gap_end: Optional[float] = None
    end_reason: Optional[str] = None
    nodes: int = 0
    simplex_iterations: int = 0
    work_units: Optional[float] = None
    solutions: int = 0
    mip_gap_param: Optional[float] = None
    time_limit_param: Optional[float] = None
    progress: float = 0.0
    skip_state: str = 'none'   # none | requested | applied

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        return d


class HierCallback:
    """Callable passed to ``model.optimize(cb)``. Keeps all pass state by NAME."""

    def __init__(self, context, pass_specs, x_vars: Dict[Any, gp.Var],
                 settings, on_partial: Optional[Callable[[Dict[str, Any]], None]] = None,
                 stop_after: Optional[Dict[str, float]] = None):
        self.ctx = context
        self.specs = pass_specs                      # ordered: pass 1 first
        self.x_keys = list(x_vars.keys())
        self.x_list = [x_vars[k] for k in self.x_keys]
        self.on_partial = on_partial
        self.stop_after = stop_after or {}
        self.t0 = time.perf_counter()
        self.stats: Dict[str, PassStats] = {}
        self.by_index: Dict[int, str] = {}
        for pos, s in enumerate(self.specs):
            st = PassStats(name=s.name, priority=s.priority, index=pos, pass_no=pos + 1)
            cfg = settings.get(s.name)
            if cfg is not None:
                st.mip_gap_param = cfg.mip_gap
                st.time_limit_param = cfg.time_limit
            self.stats[s.name] = st
            self.by_index[pos] = s.name
        self.active: Optional[str] = None
        self.objective_name_order: List[str] = []    # real order of passes
        self.progress_history: List[Dict[str, Any]] = []
        self.percentage_history: List[Dict[str, Any]] = []
        self.partials: List[Dict[str, Any]] = []
        self.last_partial_s = -1e9
        self.stop_requested = False
        self.stop_reason: Optional[str] = None
        self.skip_requested: set = set()
        self.last_incumbent: Optional[Dict[str, Any]] = None
        self.n_message = 0

    # -- control from outside (actions en caliente) -----------------------------

    def signal_stop(self, reason: str = 'user_stop'):
        self.stop_requested = True
        self.stop_reason = reason

    def signal_skip(self, name: str):
        if name in self.stats:
            self.skip_requested.add(name)
            self.stats[name].skip_state = 'requested'

    # -- helpers ---------------------------------------------------------------------

    def _elapsed(self) -> float:
        return time.perf_counter() - self.t0

    def _open_pass(self, name: str):
        if self.active == name:
            return
        if self.active is not None:
            self._close_pass(self.active)
        self.active = name
        st = self.stats[name]
        if st.start_s is None:
            st.start_s = self._elapsed()
        self.objective_name_order.append(name)
        self.ctx.log(f"pass {st.pass_no}/{len(self.specs)} -> {name} (priority {st.priority})")

    def _close_pass(self, name: str):
        st = self.stats[name]
        if st.end_s is None:
            st.end_s = self._elapsed()
        if st.end_reason is None:
            st.end_reason = 'optimal'   # overwritten below by MESSAGE when it says otherwise

    def pct(self) -> float:
        progs = {n: s.progress for n, s in self.stats.items()}
        if not progs:
            return 0.0
        main = MAIN_OBJECTIVE if MAIN_OBJECTIVE in progs else next(iter(progs))
        others = [p for n, p in progs.items() if n != main]
        if not others:
            return progs[main]
        f = MULTI_OBJ_FACTOR
        return (1 - f) * progs[main] + f / len(others) * sum(others)

    def _indicators(self, values: List[float]) -> Dict[str, Any]:
        covered = set()
        couriers = set()
        lateness = 0.0
        minutes = 0.0
        chosen = []
        cands = self.ctx.candidates
        for key, v in zip(self.x_keys, values):
            if v > 0.5:
                c = cands[key]
                chosen.append(key)
                couriers.add(key[0])
                covered.update(key[1])
                lateness += c['lateness']
                minutes += c['total_tt']
        return {
            'orders_covered': len(covered),
            'orders_pending': len(self.ctx.orders),
            'couriers_used': len(couriers),
            'couriers_available': len(self.ctx.couriers),
            'lateness_min': round(lateness, 3),
            'courier_minutes': round(minutes, 3),
            'chosen': chosen,
        }

    def _maybe_partial(self, model, force: bool = False):
        if self.last_incumbent is None:
            return
        now = self._elapsed()
        if not force and now - self.last_partial_s < PARTIAL_MIN_INTERVAL_S:
            return
        self.last_partial_s = now
        snap = {
            'status': 'RUNNING',
            'elapsed_s': round(now, 3),
            'pct': round(self.pct(), 2),
            'active_pass': self.active,
            'objective_progress': {n: round(s.progress, 2) for n, s in self.stats.items()},
            'indicators': {k: v for k, v in self.last_incumbent.items() if k != 'chosen'},
        }
        self.partials.append(snap)
        if self.on_partial:
            try:
                self.on_partial(snap)
            except Exception as exc:   # publishing never breaks the solve
                self.ctx.log(f"partial consumer failed: {exc}")

    def _apply_actions(self, model, where):
        if self.stop_requested:
            if self.active:
                self.stats[self.active].end_reason = self.stop_reason or 'user_stop'
            model.terminate()
            return
        if self.active and self.active in self.skip_requested:
            st = self.stats[self.active]
            if st.skip_state != 'applied':
                st.skip_state = 'applied'
                st.end_reason = 'skipped'
                self.ctx.log(f"skip applied to pass '{self.active}'")
                model.cbStopOneMultiObj(st.index)
        sa = self.stop_after
        if sa:
            secs = sa.get('seconds')
            pctm = sa.get('percentage')
            if secs is not None and self._elapsed() >= secs and (pctm is None or self.pct() >= pctm):
                self.stop_requested = True
                self.stop_reason = 'stop_after'
                if self.active:
                    self.stats[self.active].end_reason = 'stop_after'
                model.terminate()

    # -- the callback ----------------------------------------------------------------

    def __call__(self, model, where):
        try:
            if where == GRB.Callback.MULTIOBJ:
                cnt = model.cbGet(GRB.Callback.MULTIOBJ_OBJCNT)   # passes finished so far
                if cnt > 0 and cnt - 1 in self.by_index:
                    self._close_pass(self.by_index[cnt - 1])
                if cnt in self.by_index:
                    self._open_pass(self.by_index[cnt])
            elif where == GRB.Callback.MESSAGE:
                self.n_message += 1
                self._on_message(model.cbGet(GRB.Callback.MSG_STRING))
            elif where == GRB.Callback.MIPSOL:
                self._on_mipsol(model)
            elif where == GRB.Callback.MIP:
                self._on_mip(model)
            if where in (GRB.Callback.MIP, GRB.Callback.MIPSOL, GRB.Callback.MIPNODE,
                         GRB.Callback.MULTIOBJ, GRB.Callback.SIMPLEX):
                self._apply_actions(model, where)
        except gp.GurobiError as exc:
            self.ctx.log(f"callback error: {exc}")

    def _on_message(self, msg: str):
        m = _RE_PASS.search(msg)
        if m:
            # Gurobi prints the 1-based pass number and the objective NAME; go by name
            name = m.group(2).strip()
            if name in self.stats:
                self._open_pass(name)
            else:
                idx = int(m.group(1)) - 1
                if idx in self.by_index:
                    self._open_pass(self.by_index[idx])
            return
        if self.active is None:
            return
        st = self.stats[self.active]
        m = _RE_EXPLORED.search(msg)
        if m:
            st.nodes = int(m.group(1))
            st.simplex_iterations = int(m.group(2))
            if m.group(4):
                st.work_units = float(m.group(4))
            return
        m = _RE_BOUND.search(msg)
        if m:
            try:
                st.value = float(m.group(1))
                st.bound = float(m.group(2))
                g = m.group(3).rstrip('%')
                st.gap_end = float(g) / 100.0 if m.group(3).endswith('%') else float(g)
            except ValueError:
                pass
            return
        if _RE_OPTIMAL.search(msg):
            st.proof_s = self._elapsed()
            st.progress = 100.0
            if st.end_reason in (None, 'optimal'):
                st.end_reason = 'optimal'
            return
        if _RE_TIME.search(msg):
            st.end_reason = 'time_limit'
            return
        if _RE_INTERRUPTED.search(msg):
            if st.end_reason is None:
                st.end_reason = 'interrupted'

    def _on_mipsol(self, model):
        if self.active is None:
            return
        st = self.stats[self.active]
        now = self._elapsed()
        obj = model.cbGet(GRB.Callback.MIPSOL_OBJ)
        st.solutions += 1
        if st.first_incumbent_s is None:
            st.first_incumbent_s = now
        st.last_improvement_s = now
        st.value = obj
        values = model.cbGetSolution(self.x_list)       # ONE call for the whole batch
        ind = self._indicators(values)
        ind['objective'] = obj
        ind['pass'] = self.active
        self.last_incumbent = ind
        self.progress_history.append({
            't': round(now, 3), 'pass': self.active, 'value': obj,
            'prog': round(st.progress, 2), 'orders_covered': ind['orders_covered'],
        })
        self._maybe_partial(model)

    def _on_mip(self, model):
        if self.active is None:
            return
        st = self.stats[self.active]
        best = model.cbGet(GRB.Callback.MIP_OBJBST)
        bound = model.cbGet(GRB.Callback.MIP_OBJBND)
        prog = progress_from_gap(best, bound)
        if abs(best) < 1e99:
            st.value = best
        if abs(bound) < 1e99:
            st.bound = bound
        if prog != st.progress:
            st.progress = prog
            self.percentage_history.append({'t': round(self._elapsed(), 3), 'pct': round(self.pct(), 2)})
        if self._elapsed() - self.last_partial_s >= PARTIAL_HEARTBEAT_S:
            self._maybe_partial(model, force=True)

    # -- after optimize() --------------------------------------------------------------

    def finalize(self, model, ended_by: Optional[str] = None):
        """Fill what the callback could not see (tiny models solve without events)."""
        if self.active is not None:
            self._close_pass(self.active)
        total = model.NumObj
        multi = total >= 1 and len(self.specs) > 1
        for i in range(max(total, 1) if self.specs else 0):
            name = self.by_index.get(i)
            if name is None:
                continue
            st = self.stats[name]
            try:
                if model.SolCount > 0:
                    if multi:
                        model.params.ObjNumber = i
                        st.value = model.ObjNVal
                    else:
                        st.value = model.ObjVal      # mono-objective model (HIER_SINGLE_OBJ gate)
            except gp.GurobiError:
                pass
            if st.start_s is None:
                st.start_s = 0.0
                self.objective_name_order.append(name)
            if st.end_s is None:
                st.end_s = self._elapsed()
            if st.end_reason is None:
                if ended_by:
                    st.end_reason = ended_by
                elif model.Status == GRB.OPTIMAL:
                    st.end_reason = 'optimal'
                elif model.Status == GRB.TIME_LIMIT:
                    st.end_reason = 'time_limit'
                elif model.Status == GRB.INTERRUPTED:
                    st.end_reason = self.stop_reason or 'interrupted'
                else:
                    st.end_reason = f'status_{model.Status}'
            if st.end_reason == 'optimal':
                st.progress = 100.0
                st.gap_end = 0.0
                if st.bound is None:
                    st.bound = st.value
