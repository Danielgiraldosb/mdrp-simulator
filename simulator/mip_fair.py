"""
MIPFairPolicy -- MIP-Fair of the thesis (Phase 4, l. 891): the per-window
assignment MIP with the Gini fairness constraint (eq:fair_const) evaluated on
the projected equity history H_t.

Same candidate set as ILP / Hier / BRKGA (brkga_policy.build_candidates:
routing.generate_store_routes x routing.route_feasibility, K nearest idle
couriers per route, rejected_by honoured) and the same assignment
constraints as ilp_policy (each order <= 1 route, each courier <= 1 route).

Projected earnings. Because a courier takes at most one route per round, his
projected earnings after the round are LINEAR in the binaries:

    w_c = w_c^0 * (1 - sum_r x_cr) + sum_r x_cr * w_c(r)

with, per cfg.mipfair_basis,
    hourly: w_c^0 = earn_c / (active_c/60),  w_c(r) = (earn_c + pay_r) / ((active_c + tt_r)/60)
    total : w_c^0 = earn_c,                  w_c(r) =  earn_c + pay_r
and pay_r = cfg.pay_per_order * |r| (flat tariff; eq:tariff is an author
decision still open). (earn_c, active_c) come from state['H_t'].

Gini linearisation. G(w) = sum_{i,j}|w_i - w_j| / (2 n sum w) <= alpha is
equivalent to sum_{i<j} d_ij - alpha * n * sum_c w_c <= 0 with
d_ij >= w_i - w_j and d_ij >= w_j - w_i (d is only bounded below, so at the
optimum of a constraint of this direction it equals |w_i - w_j|). The
constraint is made ELASTIC with one slack v >= 0, scaled by n * W_ref so it is
a dimensionless "Gini excess":

    sum_{i<j} d_ij - alpha * n * sum_c w_c <= v * n * W_ref,
    W_ref = sum_c max(w_c^0, max_r w_c(r))

A round is therefore never infeasible; v* > 0 says the window could not meet
alpha and by how much.

Lexicographic solve (cfg.mipfair_priority), pinning each stage at its optimum
before the next one:
    'fairness' : min v  >  max coverage  >  min (lambda*tt + mu*lateness)
    'coverage' : max coverage  >  min v  >  min tie-break
'fairness' is the faithful reading of eq:fair_const as a hard constraint;
'coverage' is the "within the coverage constraint" reading used by BRKGA-Fair.

Scope (cfg.mipfair_scope): 'all' takes the Gini over every logged-on courier
(state['H_all']; busy couriers enter with fixed earnings), 'idle' over the
round's idle couriers only (state['H_t']). Without H_all both coincide.
eq:minwage and eq:routebalance are not implemented yet. Falls back to
GreedyPolicy when PuLP is missing or the solver fails.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from models import Courier, Order
from policies import Policy, GreedyPolicy
from ilp_policy import _try_import_pulp, get_solver, _LAMBDA_COST, _MU_DELAY
from brkga_policy import build_candidates, CandKey

logger = logging.getLogger(__name__)

_EPS_V = 1e-7


def projected_earnings(cands: Dict[CandKey, Dict[str, Any]], histories: Dict[int, Any],
                       basis: str, pay_per_order: float
                       ) -> Tuple[Dict[int, float], Dict[CandKey, float]]:
    """w_c^0 per courier and w_c(r) per candidate, under the given basis."""
    if basis not in ('hourly', 'total'):
        raise ValueError(f"mipfair_basis must be 'hourly' or 'total', got {basis!r}")
    w0: Dict[int, float] = {}
    for cid, h in histories.items():
        w0[cid] = float(h.hourly_earnings) if basis == 'hourly' else float(h.earnings)
    w_opt: Dict[CandKey, float] = {}
    for (cid, rkey), cand in cands.items():
        h = histories[cid]
        pay = pay_per_order * len(rkey)
        if basis == 'hourly':
            hours = (h.active_time + cand['total_tt']) / 60.0
            w_opt[(cid, rkey)] = (h.earnings + pay) / hours if hours > 0 else 0.0
        else:
            w_opt[(cid, rkey)] = h.earnings + pay
    return w0, w_opt


def gini_excess(w: Dict[int, float], alpha: float, w_ref: float) -> float:
    """The model's slack v for a realised earnings vector: max(0, sum_{i<j}|w_i-w_j|
    - alpha*n*sum w) / (n*W_ref). 0 when the vector meets alpha."""
    ids = sorted(w)
    n = len(ids)
    if n <= 1 or w_ref <= 0:
        return 0.0
    mad = sum(abs(w[ids[i]] - w[ids[j]]) for i in range(n) for j in range(i + 1, n))
    return max(0.0, mad - alpha * n * sum(w.values())) / (n * w_ref)


class MIPFairPolicy(Policy):
    def __init__(self, cfg: Config, base_greedy: Optional[Policy] = None):
        super().__init__(cfg)
        self._greedy = base_greedy or GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)
        self._pulp = _try_import_pulp()
        if self._pulp is None:
            logger.warning("PuLP not found -- MIPFairPolicy falls back to GreedyPolicy")
        self.alpha = float(cfg.mipfair_alpha)
        if not 0.0 <= self.alpha <= 1.0:
            raise ValueError("mipfair_alpha must be in [0, 1]")
        self.priority = cfg.mipfair_priority
        if self.priority not in ('fairness', 'coverage'):
            raise ValueError(f"mipfair_priority must be 'fairness' or 'coverage', got {self.priority!r}")
        self.basis = cfg.mipfair_basis
        projected_earnings({}, {}, self.basis, 0.0)        # validates the basis early
        self.cand_top_k = max(1, int(cfg.mipfair_cand_top_k))
        self.scope = cfg.mipfair_scope
        if self.scope not in ('all', 'idle'):
            raise ValueError(f"mipfair_scope must be 'all' or 'idle', got {self.scope!r}")
        self.rounds: List[Dict[str, Any]] = []

    # -- Policy contract -------------------------------------------------------------------

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        if self._pulp is None:
            return self._greedy.assign(state)
        couriers = [c for c in state['L_t'].values() if c.is_available]
        orders = list(state['O_t'].values())
        t: float = state['time']
        if not couriers or not orders:
            return []
        cands = build_candidates(couriers, orders, t, self.cfg, self.cand_top_k)
        if not cands:
            return []
        hist = state.get('H_t') or {}
        histories = {c.courier_id: hist.get(c.courier_id, c.history) for c in couriers}
        if self.scope == 'all':
            # busy couriers enter the Gini with fixed earnings (no candidates, so w_c = w_c^0)
            for cid, h in (state.get('H_all') or {}).items():
                histories.setdefault(cid, h)
        try:
            return self._solve(cands, histories, t)
        except Exception as exc:
            logger.warning(f"MIP-Fair solver error ({exc}), falling back to greedy for this round")
            return self._greedy.assign(state)

    # -- Model -----------------------------------------------------------------------------

    def _solve(self, cands: Dict[CandKey, Dict[str, Any]], histories: Dict[int, Any], t: float
               ) -> List[Tuple[int, List[int], float]]:
        pulp = self._pulp
        cfg = self.cfg
        t0 = time.perf_counter()
        w0, w_opt = projected_earnings(cands, histories, self.basis, cfg.pay_per_order)
        cids = sorted(histories)
        n = len(cids)
        w_ref = sum(max(w0[c], max((w_opt[k] for k in cands if k[0] == c), default=0.0)) for c in cids)
        if w_ref <= 0:
            w_ref = 1.0

        prob = pulp.LpProblem("MIPFair", pulp.LpMinimize)
        x = {k: pulp.LpVariable(f"x_{k[0]}_{'_'.join(map(str, k[1]))}", cat='Binary') for k in cands}
        v = pulp.LpVariable("v", lowBound=0.0)

        by_order: Dict[int, list] = {}
        by_courier: Dict[int, list] = {c: [] for c in cids}
        for (cid, rkey), var in x.items():
            by_courier[cid].append(var)
            for oid in rkey:
                by_order.setdefault(oid, []).append(var)
        for oid, vs in by_order.items():
            prob += pulp.lpSum(vs) <= 1, f"order_{oid}"
        for cid, vs in by_courier.items():
            if vs:
                prob += pulp.lpSum(vs) <= 1, f"courier_{cid}"

        # projected earnings, linear in x
        w = {}
        for c in cids:
            terms = [x[k] * (w_opt[k] - w0[c]) for k in cands if k[0] == c]
            w[c] = w0[c] + pulp.lpSum(terms) if terms else w0[c]

        # |w_i - w_j| bounds and the elastic Gini constraint
        d = {}
        for i in range(n):
            for j in range(i + 1, n):
                ci, cj = cids[i], cids[j]
                d[ci, cj] = pulp.LpVariable(f"d_{ci}_{cj}", lowBound=0.0)
                prob += d[ci, cj] >= w[ci] - w[cj], f"dpos_{ci}_{cj}"
                prob += d[ci, cj] >= w[cj] - w[ci], f"dneg_{ci}_{cj}"
        if n > 1:
            prob += (pulp.lpSum(d.values()) - self.alpha * n * pulp.lpSum(w[c] for c in cids)
                     <= v * n * w_ref), "gini_elastic"
        else:
            prob += v == 0.0, "gini_trivial"

        coverage = pulp.lpSum(var * len(k[1]) for k, var in x.items())
        tiebreak = pulp.lpSum(var * (_LAMBDA_COST * cands[k]['total_tt'] + _MU_DELAY * cands[k]['lateness'])
                              for k, var in x.items())
        if self.priority == 'fairness':
            stages = [('min', v, 'v'), ('max', coverage, 'coverage'), ('min', tiebreak, 'tiebreak')]
        else:
            stages = [('max', coverage, 'coverage'), ('min', v, 'v'), ('min', tiebreak, 'tiebreak')]

        solver = get_solver(pulp, cfg)
        stage_values: Dict[str, float] = {}
        for i, (sense, expr, name) in enumerate(stages):
            prob.sense = pulp.LpMinimize if sense == 'min' else pulp.LpMaximize
            prob.setObjective(expr)
            prob.solve(solver)
            if prob.status != pulp.LpStatusOptimal:
                raise RuntimeError(f"stage {name}: status {pulp.LpStatus.get(prob.status, prob.status)}")
            val = float(pulp.value(prob.objective) or 0.0)
            stage_values[name] = val
            if i < len(stages) - 1:
                if name == 'coverage':
                    prob += coverage >= val - 0.5, "pin_coverage"
                elif name == 'v':
                    prob += v <= val + _EPS_V, "pin_v"

        chosen = [k for k, var in x.items() if (pulp.value(var) or 0.0) > 0.5]
        w_after = dict(w0)
        for cid, rkey in chosen:
            w_after[cid] = w_opt[(cid, rkey)]
        self.rounds.append({
            'time': t, 'n_couriers': n, 'candidates': len(cands),
            'coverage': int(round(stage_values.get('coverage', 0.0))),
            'v': stage_values.get('v', 0.0),
            'gini_before': _gini(list(w0.values())), 'gini_after': _gini(list(w_after.values())),
            'excess_after': gini_excess(w_after, self.alpha, w_ref), 'w_ref': w_ref,
            'solve_s': time.perf_counter() - t0,
        })
        return [(cid, list(cands[(cid, rkey)]['sequence']), cfg.pay_per_order * len(rkey))
                for cid, rkey in chosen]


def _gini(values: List[float]) -> float:
    from metrics import gini
    return gini(values)
