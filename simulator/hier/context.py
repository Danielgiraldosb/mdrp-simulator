"""
HierContext: one dispatch round of the MDRP as a hierarchical multi-objective
MIP in Gurobi (épica §3). The structure is the one ported from XO:

  configure()   previous solution (fixed) -> candidate generation with
                annotated prefilters -> variables (x per candidate, y per
                order) -> constraint families, one per block, with stable row
                names -> fixed / impossible rows -> objectives (one pass each,
                all MAX) -> per-pass parameters.
  optimize()    Gurobi + HierCallback; partials; actions (stop / skip /
                stop_after); per-pass indicators; solution.
  artifacts     <id>_input.json, <id>_sol.json, <id>_partialN.json,
                <id>.lp (WRITE_LP), <id>_infeasible.ilp; fingerprint().

Time model (épica D1/D2): the simulator already works in rolling rounds of
``cfg.rolling_horizon`` minutes, so the round is the decision unit; routes
are ENUMERATED columns (routing.generate_store_routes) whose feasibility and
costs are computed outside the MIP (routing.route_feasibility). No big-M,
no continuous time inside the model. D3: an order may stay uncovered at no
infeasibility (CourierOnce/Cover are <= / == with y free), so demand never
makes the model infeasible.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

import gurobipy as gp
from gurobipy import GRB

from config import Config
from models import Order, Courier, Location, EquityHistory
from distance import dist_km
from routing import generate_store_routes, route_feasibility

from .flags import flag
from .objectives import (ObjectiveSpec, ObjectiveSetting, resolve_order, resolve_settings)
from .callback import HierCallback

logger = logging.getLogger(__name__)

RouteKey = Tuple[int, ...]
CandKey = Tuple[int, RouteKey]

DEFAULT_TOP_K = 25


# -- JSON round (offline reproduction, fixtures) ------------------------------------------

def round_to_json(couriers: List[Courier], orders: List[Order], cfg: Config, t: float,
                  top_k: int = DEFAULT_TOP_K, order: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        'version': 1,
        'time': t,
        'params': {
            'meters_per_minute': cfg.meters_per_minute,
            'pickup_service_min': cfg.pickup_service_min,
            'dropoff_service_min': cfg.dropoff_service_min,
            'late_tolerance_min': cfg.late_tolerance_min,
            'max_bundle_size': cfg.max_bundle_size,
            'pay_per_order': cfg.pay_per_order,
            'guaranteed_pay_per_hour': cfg.guaranteed_pay_per_hour,
            'top_k': top_k,
            'order': list(order) if order else None,
        },
        'couriers': [{
            'id': c.courier_id, 'x': c.location.x, 'y': c.location.y,
            'on_time': c.on_time, 'off_time': c.off_time,
            'earnings': c.history.earnings, 'orders_delivered': c.history.orders_delivered,
            'active_time': c.history.active_time, 'dist_traveled': c.history.dist_traveled,
        } for c in couriers],
        'orders': [{
            'id': o.order_id, 'placement_time': o.placement_time, 'ready_time': o.ready_time,
            'store': [o.store_loc.x, o.store_loc.y], 'user': [o.user_loc.x, o.user_loc.y],
            'target_click_to_door': o.target_click_to_door, 'max_click_to_door': o.max_click_to_door,
            'rejected_by': sorted(o.rejected_by),
        } for o in orders],
    }


def round_from_json(doc: Dict[str, Any]) -> Tuple[List[Courier], List[Order], Config, float, Dict[str, Any]]:
    p = doc['params']
    cfg = Config()
    cfg.meters_per_minute = p['meters_per_minute']
    cfg.pickup_service_min = p['pickup_service_min']
    cfg.dropoff_service_min = p['dropoff_service_min']
    cfg.late_tolerance_min = p.get('late_tolerance_min', 0.0)
    cfg.max_bundle_size = p.get('max_bundle_size', 3)
    cfg.pay_per_order = p.get('pay_per_order', 10.0)
    cfg.guaranteed_pay_per_hour = p.get('guaranteed_pay_per_hour', 15.0)
    couriers = []
    for c in doc['couriers']:
        cr = Courier(courier_id=c['id'], on_time=c.get('on_time', 0.0), off_time=c.get('off_time', 1440.0),
                     home_loc=Location(c['x'], c['y']))
        cr.condition = 'idle'
        cr.history = EquityHistory(earnings=c.get('earnings', 0.0),
                                   orders_delivered=c.get('orders_delivered', 0),
                                   active_time=c.get('active_time', 0.0),
                                   dist_traveled=c.get('dist_traveled', 0.0))
        couriers.append(cr)
    orders = []
    for o in doc['orders']:
        od = Order(order_id=o['id'], placement_time=o['placement_time'],
                   store_loc=Location(*o['store']), user_loc=Location(*o['user']),
                   ready_time=o['ready_time'], target_click_to_door=o['target_click_to_door'],
                   max_click_to_door=o['max_click_to_door'])
        od.rejected_by = set(o.get('rejected_by', []))
        orders.append(od)
    extra = {'top_k': p.get('top_k', DEFAULT_TOP_K), 'order': p.get('order')}
    return couriers, orders, cfg, float(doc['time']), extra


# -- Context ---------------------------------------------------------------------------------

class HierContext:
    """Build and solve ONE dispatch round. Usage: ctx.configure(); ctx.optimize()."""

    def __init__(self, couriers: List[Courier], orders: List[Order], cfg: Config, t: float, *,
                 order: Optional[List[str]] = None,
                 settings: Optional[Dict[str, ObjectiveSetting]] = None,
                 top_k: int = DEFAULT_TOP_K,
                 on_partial: Optional[Callable[[Dict[str, Any]], None]] = None,
                 stop_after: Optional[Dict[str, float]] = None,
                 prev_solution: Optional[List[Tuple[int, List[int]]]] = None,
                 run_id: Optional[str] = None,
                 env: Optional[gp.Env] = None,
                 write_model: bool = False,
                 compute_iis: bool = True,
                 seed: Optional[int] = None,
                 log: Optional[Callable[[str], None]] = None):
        self.couriers = [c for c in couriers if c.is_available] if couriers else []
        self.orders = list(orders)
        self.cfg = cfg
        self.t = float(t)
        self.order_names = list(order) if order else None
        self.specs: List[ObjectiveSpec] = []
        self.settings_in = settings or {}
        self.settings: Dict[str, ObjectiveSetting] = {}
        self.top_k = int(top_k)
        self.on_partial = on_partial
        self.stop_after = stop_after
        self.prev_solution = prev_solution or []
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._env = env
        self.write_model = write_model or flag('WRITE_LP')
        self.compute_iis = compute_iis
        self.seed = seed
        self._log_fn = log or (lambda m: logger.debug(m))

        # built by configure()
        self.alias_c: Dict[int, str] = {}
        self.alias_o: Dict[int, str] = {}
        self.alias_r: Dict[RouteKey, str] = {}
        self.candidates: Dict[CandKey, Dict[str, Any]] = {}
        self.discards: Dict[str, int] = {}
        self.discards_by_order: Dict[int, Dict[str, int]] = {}
        self.impossible: List[int] = []
        self.fixed: List[CandKey] = []
        self.model: Optional[gp.Model] = None
        self.x: Dict[CandKey, gp.Var] = {}
        self.y: Dict[int, gp.Var] = {}
        self.rows_by_family: Dict[str, int] = {}
        self.configure_profile: Dict[str, float] = {}
        # produced by optimize()
        self.cb: Optional[HierCallback] = None
        self.status: Optional[int] = None
        self.inner_status: Optional[str] = None
        self.solution: List[Tuple[int, List[int], float]] = []
        self.solve_s: Optional[float] = None
        self.ended_by: Optional[str] = None
        self._multiobj_envs = False

    # -- logging ----------------------------------------------------------------------------

    def log(self, msg: str):
        self._log_fn(f"[hier {self.run_id}] {msg}")

    # -- 3.2 configure() ----------------------------------------------------------------------

    def configure(self) -> 'HierContext':
        t0 = time.perf_counter()
        self._aliases()
        self.configure_profile['aliases'] = time.perf_counter() - t0

        t1 = time.perf_counter()
        self._generate_candidates()
        self.configure_profile['candidates'] = time.perf_counter() - t1

        t2 = time.perf_counter()
        self._build_model()
        self.configure_profile['model'] = time.perf_counter() - t2

        t3 = time.perf_counter()
        self._objectives()
        self.configure_profile['objectives'] = time.perf_counter() - t3
        self.configure_profile['total'] = time.perf_counter() - t0
        return self

    def _aliases(self):
        for i, c in enumerate(sorted(self.couriers, key=lambda c: c.courier_id), 1):
            self.alias_c[c.courier_id] = f"C{i}"
        for i, o in enumerate(sorted(self.orders, key=lambda o: o.order_id), 1):
            self.alias_o[o.order_id] = f"O{i}"

    def _discard(self, code: str, oids: Tuple[int, ...]):
        self.discards[code] = self.discards.get(code, 0) + 1
        for oid in oids:
            d = self.discards_by_order.setdefault(oid, {})
            d[code] = d.get(code, 0) + 1

    def _generate_candidates(self):
        """Annotated prefilters: every discard keeps a code (feeds explanations, épica §7)."""
        cfg = self.cfg
        routes = generate_store_routes(self.orders, cfg.max_bundle_size)
        for i, r in enumerate(routes, 1):
            self.alias_r[tuple(sorted(o.order_id for o in r))] = f"R{i}"

        # equity deficit per courier (decision 3C): d_c = max(0, mean earnings - earnings_c),
        # on the ACCUMULATED earnings of the day among the idle couriers of this round
        earn = {c.courier_id: c.history.earnings for c in self.couriers}
        mean_w = sum(earn.values()) / len(earn) if earn else 0.0
        deficit = {cid: round(max(0.0, mean_w - w), 4) for cid, w in earn.items()}
        self.mean_earnings = mean_w

        for route in routes:
            rkey = tuple(sorted(o.order_id for o in route))
            store_loc = route[0].store_loc
            ranked = sorted(self.couriers, key=lambda c: dist_km(c.location, store_loc))
            for rank, c in enumerate(ranked):
                if rank >= self.top_k:
                    self._discard('NOT_TOPK', rkey)
                    continue
                if any(c.courier_id in o.rejected_by for o in route):
                    self._discard('REJECTED', rkey)
                    continue
                res = route_feasibility(c, route, self.t, cfg)
                if res is None:
                    self._discard('SLA_INFEASIBLE', rkey)
                    continue
                self.candidates[(c.courier_id, rkey)] = {
                    'courier': c.courier_id, 'route': rkey, 'n_orders': len(rkey),
                    'lateness': round(res['lateness'], 4), 'total_tt': round(res['total_tt'], 4),
                    'deficit': deficit[c.courier_id],
                    'sequence': [o.order_id for o in res['sequence']],
                }
        covered_any = {oid for (_, rkey) in self.candidates for oid in rkey}
        self.impossible = [o.order_id for o in self.orders if o.order_id not in covered_any]
        for oid in self.impossible:
            self._discard('NO_CANDIDATE', (oid,))

    def _build_model(self):
        env = self._env
        m = gp.Model(f"MDRP_hier_{self.run_id}", env=env) if env else gp.Model(f"MDRP_hier_{self.run_id}")
        m.Params.OutputFlag = 0 if flag('HIER_NO_MESSAGE') else 1   # MESSAGE callbacks need output enabled...
        m.Params.LogToConsole = 0        # ...but nothing goes to the console
        if self.seed is not None and not flag('HIER_NO_SEED'):
            m.Params.Seed = int(self.seed)
        self.model = m

        # variables: registered in Python dicts by key (never getVarByName)
        for key, cand in self.candidates.items():
            cid, rkey = key
            self.x[key] = m.addVar(vtype=GRB.BINARY, name=f"x[{self.alias_c[cid]},{self.alias_r[rkey]}]")
        for o in self.orders:
            self.y[o.order_id] = m.addVar(vtype=GRB.BINARY, name=f"y[{self.alias_o[o.order_id]}]")

        # family Cover: y[o] == sum of candidates containing o   (what "covered" means, D3)
        by_order: Dict[int, List[gp.Var]] = {}
        by_courier: Dict[int, List[gp.Var]] = {}
        for (cid, rkey), var in self.x.items():
            by_courier.setdefault(cid, []).append(var)
            for oid in rkey:
                by_order.setdefault(oid, []).append(var)
        n = 0
        for oid, var_y in self.y.items():
            vs = by_order.get(oid)
            if vs:
                m.addConstr(var_y == gp.quicksum(vs), name=f"Cover[{self.alias_o[oid]}]")
                n += 1
        self.rows_by_family['Cover'] = n

        # family Impossible: orders with no candidate (annotated NO_CANDIDATE)
        n = 0
        for oid in self.impossible:
            m.addConstr(self.y[oid] == 0, name=f"Impossible[{self.alias_o[oid]}]")
            n += 1
        self.rows_by_family['Impossible'] = n

        # family CourierOnce: a courier takes at most one route this round
        n = 0
        for cid, vs in by_courier.items():
            m.addConstr(gp.quicksum(vs) <= 1, name=f"CourierOnce[{self.alias_c[cid]}]")
            n += 1
        self.rows_by_family['CourierOnce'] = n

        # family PrevSolution: reprocess -- what is already decided is fixed (== 1),
        # with the guard "never fix to 1 something another row fixes to 0"
        n = 0
        for cid, oids in self.prev_solution:
            key = (cid, tuple(sorted(oids)))
            if key not in self.x:
                self.log(f"PrevSolution {key} is not a candidate any more -> ignored (would be IIS)")
                continue
            if any(oid in self.impossible for oid in key[1]):
                self.log(f"PrevSolution {key} clashes with Impossible -> ignored")
                continue
            m.addConstr(self.x[key] == 1, name=f"PrevSolution[{self.alias_c[cid]},{self.alias_r[key[1]]}]")
            self.fixed.append(key)
            n += 1
        self.rows_by_family['PrevSolution'] = n
        m.update()

    def _objectives(self):
        m = self.model
        ctx_info = {'candidates': list(self.candidates.values())}
        all_specs = resolve_order(self.order_names)
        self.specs = [s for s in all_specs if s.exists(ctx_info)]
        self.specs_absent = [s.name for s in all_specs if s.name not in {q.name for q in self.specs}]
        self.settings = resolve_settings(self.specs, self.settings_in)
        m.ModelSense = GRB.MAXIMIZE
        if not self.specs or flag('HIER_SINGLE_OBJ'):
            m.setObjective(gp.quicksum(self.y.values()), GRB.MAXIMIZE)
            self.specs = self.specs[:1]
            return
        # IMPORTANT (épica §3.4 gotcha): never set NumObj = 0 on a mono-objective model
        for pos, spec in enumerate(self.specs):
            st = self.settings[spec.name]
            if spec.name == 'coverage':
                expr = gp.quicksum(self.y.values())
            else:
                expr = gp.quicksum(spec.coef(c) * self.x[k] for k, c in self.candidates.items())
            m.setObjectiveN(expr, index=pos, priority=spec.priority, weight=1.0,
                            abstol=st.lock_abs_tol or 0.0, reltol=st.lock_rel_tol or 0.0,
                            name=spec.name)
        m.update()
        # per-pass parameters on each multi-objective environment (épica §3.5)
        self._multiobj_envs = False
        for pos, spec in enumerate(self.specs):
            st = self.settings[spec.name]
            if st.time_limit is None and st.mip_gap is None:
                continue
            self._multiobj_envs = True
            env_i = m.getMultiobjEnv(pos)
            if st.time_limit is not None:
                env_i.setParam('TimeLimit', float(st.time_limit))
            if st.mip_gap is not None:
                env_i.setParam('MIPGap', float(st.mip_gap))

    # -- 4 optimize() ---------------------------------------------------------------------------

    def optimize(self, skip: Optional[List[str]] = None) -> 'HierContext':
        m = self.model
        if m is None:
            raise RuntimeError("configure() first")
        self.cb = HierCallback(self, self.specs, self.x, self.settings,
                               on_partial=self.on_partial, stop_after=self.stop_after)
        for name in (skip or []):            # skip requested before the pass opens (épica §5)
            self.cb.signal_skip(name)
        if self.write_model:
            self._write_lp()
        t0 = time.perf_counter()
        if self.x and not flag('HIER_NO_CALLBACK'):
            m.optimize(self.cb)
        else:
            m.optimize()
        self.solve_s = time.perf_counter() - t0
        self.status = m.Status
        self.inner_status = _status_name(m.Status)
        if self.cb.stop_requested:
            self.ended_by = self.cb.stop_reason
        self.cb.finalize(m, ended_by=self.ended_by)
        if self._multiobj_envs and not flag('HIER_NO_DISCARD'):
            try:
                m.discardMultiobjEnvs()
            except gp.GurobiError:
                pass
        if m.Status == GRB.INFEASIBLE:
            self.log("INFEASIBLE round -- only possible through PrevSolution; computing IIS")
            if self.compute_iis:
                self._write_iis()
            self.solution = []
            return self
        self._extract_solution()
        return self

    def _extract_solution(self):
        m = self.model
        self.solution = []
        if m.SolCount == 0:
            return
        vals = m.getAttr('X', list(self.x.values()))
        for (key, var), v in zip(self.x.items(), vals):
            if v > 0.5:
                cand = self.candidates[key]
                oids = list(cand['sequence'])
                self.solution.append((key[0], oids, self.cfg.pay_per_order * len(oids)))
        self.solution.sort(key=lambda a: a[0])

    # -- actions (en caliente) -------------------------------------------------------------------

    def signal_stop(self, reason: str = 'user_stop'):
        if self.cb:
            self.cb.signal_stop(reason)

    def signal_skip(self, name: str):
        if self.cb:
            self.cb.signal_skip(name)

    # -- indicators / details ----------------------------------------------------------------------

    def indicators(self) -> Dict[str, Any]:
        covered = {oid for (_, oids, _) in self.solution for oid in oids}
        lateness = sum(self.candidates[(cid, tuple(sorted(oids)))]['lateness'] for cid, oids, _ in self.solution)
        minutes = sum(self.candidates[(cid, tuple(sorted(oids)))]['total_tt'] for cid, oids, _ in self.solution)
        equity = sum(self.candidates[(cid, tuple(sorted(oids)))]['deficit'] * len(oids) for cid, oids, _ in self.solution)
        return {
            'orders_pending': len(self.orders),
            'orders_covered': len(covered),
            'orders_uncovered': len(self.orders) - len(covered),
            'couriers_available': len(self.couriers),
            'couriers_used': len(self.solution),
            'bundles': sum(1 for _, oids, _ in self.solution if len(oids) > 1),
            'lateness_min': round(lateness, 3),
            'courier_minutes': round(minutes, 3),
            'equity_score': round(equity, 4),
            'mean_earnings': round(getattr(self, 'mean_earnings', 0.0), 4),
        }

    def pass_table(self) -> List[Dict[str, Any]]:
        if not self.cb:
            return []
        rows = []
        for spec in self.specs:
            st = self.cb.stats[spec.name]
            d = st.to_dict()
            d['label'] = spec.label
            d['sense'] = spec.sense
            d['protected'] = spec.protected
            d['value_display'] = (-st.value if (st.value is not None and spec.sense == 'MIN') else st.value)
            rows.append(d)
        return rows

    def uncovered_report(self) -> Dict[str, Any]:
        """Hooks for explanations (épica §7): why an order stayed uncovered."""
        covered = {oid for (_, oids, _) in self.solution for oid in oids}
        out = {}
        for o in self.orders:
            if o.order_id in covered:
                continue
            if o.order_id in self.impossible:
                out[o.order_id] = {'reason': 'NO_CANDIDATE', 'discards': self.discards_by_order.get(o.order_id, {})}
            else:
                n_cand = sum(1 for (_, rkey) in self.candidates if o.order_id in rkey)
                out[o.order_id] = {'reason': 'NOT_SELECTED', 'candidates': n_cand,
                                   'discards': self.discards_by_order.get(o.order_id, {})}
        return out

    def details(self) -> Dict[str, Any]:
        m = self.model
        return {
            'run_id': self.run_id,
            'time': self.t,
            'status': self.inner_status,
            'ended_by': self.ended_by,
            'solve_s': round(self.solve_s or 0.0, 4),
            'configure_s': {k: round(v, 4) for k, v in self.configure_profile.items()},
            'objective_name': self.cb.objective_name_order if self.cb else [],
            'objectives_absent': getattr(self, 'specs_absent', []),
            'passes': self.pass_table(),
            'pct': round(self.cb.pct(), 2) if self.cb else None,
            'objective_progress_history': self.cb.progress_history if self.cb else [],
            'percentage_history': self.cb.percentage_history if self.cb else [],
            'indicators': self.indicators(),
            'prefilter': {'candidates': len(self.candidates), 'routes': len(self.alias_r),
                          'discards': self.discards, 'impossible': len(self.impossible)},
            'rows_by_family': self.rows_by_family,
            'model': {'vars': m.NumVars, 'rows': m.NumConstrs, 'nonzeros': m.NumNZs,
                      'num_obj': m.NumObj, 'fingerprint': self.fingerprint()} if m else {},
            'solver': {'name': 'gurobi', 'version': '.'.join(map(str, gp.gurobi.version())),
                       'threads': m.Params.Threads if m else None, 'machine': platform.node()},
            'uncovered': self.uncovered_report(),
            'n_message_events': self.cb.n_message if self.cb else 0,
        }

    # -- fingerprint (épica §8.1) -----------------------------------------------------------------

    def fingerprint(self) -> str:
        m = self.model
        if m is None:
            return ''
        h = hashlib.sha1()
        h.update(f"{m.NumVars}|{m.NumConstrs}|{m.NumNZs}|{m.NumObj}".encode())
        for v in sorted(m.getVars(), key=lambda v: v.VarName):
            h.update(f"{v.VarName}:{v.VType}".encode())
        for c in sorted(m.getConstrs(), key=lambda c: c.ConstrName):
            row = m.getRow(c)
            terms = sorted((row.getVar(i).VarName, round(row.getCoeff(i), 9)) for i in range(row.size()))
            h.update(f"{c.ConstrName}:{c.Sense}:{round(c.RHS, 9)}:{terms}".encode())
        for i in range(m.NumObj):
            m.params.ObjNumber = i
            coefs = m.getAttr('ObjN', m.getVars())
            h.update(f"obj{i}:{m.ObjNName}:{m.ObjNPriority}:{[round(c, 9) for c in coefs]}".encode())
        return h.hexdigest()

    # -- artifacts (épica §6) ------------------------------------------------------------------------

    def input_json(self) -> Dict[str, Any]:
        return round_to_json(self.couriers, self.orders, self.cfg, self.t, top_k=self.top_k,
                             order=[s.name for s in self.specs] if self.specs else self.order_names)

    def solution_json(self) -> Dict[str, Any]:
        return {
            'run_id': self.run_id,
            'status': 'FINISHED' if not self.ended_by else 'STOPPED',
            'inner_status': self.inner_status,
            'solution': [{'courier_id': cid, 'order_ids': oids, 'pay': pay} for cid, oids, pay in self.solution],
            'details': self.details(),
        }

    def write_artifacts(self, out_dir: str) -> Dict[str, str]:
        d = os.path.join(out_dir, self.run_id)
        os.makedirs(d, exist_ok=True)
        paths = {}
        p = os.path.join(d, f"{self.run_id}_input.json")
        with open(p, 'w', encoding='utf8') as f:
            json.dump(self.input_json(), f, indent=1)
        paths['input'] = p
        p = os.path.join(d, f"{self.run_id}_mapping.json")
        with open(p, 'w', encoding='utf8') as f:
            json.dump({'couriers': {v: k for k, v in self.alias_c.items()},
                       'orders': {v: k for k, v in self.alias_o.items()},
                       'routes': {v: list(k) for k, v in self.alias_r.items()}}, f, indent=1)
        paths['mapping'] = p
        if self.cb is not None:
            p = os.path.join(d, f"{self.run_id}_sol.json")
            with open(p, 'w', encoding='utf8') as f:
                json.dump(self.solution_json(), f, indent=1, default=_json_default)
            paths['sol'] = p
            for i, part in enumerate(self.cb.partials, 1):
                pp = os.path.join(d, f"{self.run_id}_partial{i}.json")
                with open(pp, 'w', encoding='utf8') as f:
                    json.dump(part, f, indent=1, default=_json_default)
        if self.write_model and self.model is not None:
            paths['lp'] = self._write_lp(d)
        return paths

    def _write_lp(self, d: Optional[str] = None) -> str:
        d = d or os.path.join('output', 'hier', self.run_id)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{self.run_id}.lp")
        self.model.write(p)
        return p

    def _write_iis(self):
        try:
            self.model.computeIIS()
            d = os.path.join('output', 'hier', self.run_id)
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, f"{self.run_id}_infeasible_model.ilp")
            self.model.write(p)
            self.log(f"IIS written to {p}")
        except gp.GurobiError as exc:
            self.log(f"IIS failed: {exc}")

    def dispose(self):
        """
        Free the Gurobi model. gurobipy Var/Constr objects must never outlive a
        disposed model (their deallocation touches freed memory: heap corruption,
        seen as random access violations in unrelated Python code), so every
        reference is dropped and collected BEFORE Model.dispose().
        """
        import gc
        m = self.model
        self.model = None
        self.x = {}
        self.y = {}
        if self.cb is not None:
            self.cb.x_list = []
            self.cb.x_keys = []
        gc.collect()
        if m is not None and not flag('HIER_NO_DISPOSE'):
            m.dispose()


def _status_name(code: int) -> str:
    names = {GRB.OPTIMAL: 'OPTIMAL', GRB.INFEASIBLE: 'INFEASIBLE', GRB.TIME_LIMIT: 'TIME_LIMIT',
             GRB.INTERRUPTED: 'INTERRUPTED', GRB.SUBOPTIMAL: 'SUBOPTIMAL', GRB.USER_OBJ_LIMIT: 'USER_OBJ_LIMIT',
             GRB.INF_OR_UNBD: 'INF_OR_UNBD', GRB.UNBOUNDED: 'UNBOUNDED', GRB.WORK_LIMIT: 'WORK_LIMIT'}
    return names.get(code, f'STATUS_{code}')


def _json_default(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, tuple):
        return list(o)
    return str(o)
