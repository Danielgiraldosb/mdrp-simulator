"""
Matching policies ported from mdrp-sim-master (Sebastian Quintero Rojas) for
direct, like-for-like comparison against our own 7 policies (Greedy,
FairGreedy, 5 ILP objectives) on the SAME mdrplib instances and the SAME
metrics pipeline. Coverage, cost, lateness and equity are read off
identically regardless of which policy produced the assignments (see
policies.py's module docstring) -- so this file does not reinterpret
mdrp-sim's own objective to fit our "coverage is the shared primary
objective" design; it reproduces mdrp-sim's actual throughput-vs-lateness
objective FAITHFULLY, and lets the comparison speak for itself.

Ported from mdrp-sim-master's policies/dispatcher/matching/{greedy,myopic}.py
and the DISPATCHER_MATCHING_POLICIES_MAP in its actors/dispatcher.py:
  mdrpsim_greedy          <- GreedyMatchingPolicy        (numpy nearest-ETA, no bundling)
  mdrpsim_mip             <- MyopicMatchingPolicy('mdrp'):                mip_matcher=True,  prospects=False
  mdrpsim_graph           <- MyopicMatchingPolicy('mdrp_graph'):          mip_matcher=False, prospects=False
  mdrpsim_graph_prospects <- MyopicMatchingPolicy('mdrp_graph_prospects'): mip_matcher=False, prospects=True

NOT ported: 'modified_mdrp' (assignment_updates=True). In mdrp-sim this lets
an already-"picking_up" courier receive MORE bundled orders mid-route --
their own Dispatcher._dispatch_event widens its candidate pool to
idle ∪ picking_up(with room) *before* calling the policy. Our own
Dispatcher._dispatch_event (simulator.py) only ever offers routes to
self.idle_couriers, and a courier accepted into a bundle is fully committed
to it until it finishes (no "append to my active route" event exists in the
shared courier engine). Porting assignment_updates faithfully means
widening the candidate pool AND adding a mid-route-append capability shared
by every policy, not just adding one more Policy subclass here -- left as a
deliberate, separate decision rather than something this file quietly
half-implements.

Deliberate adaptations (documented, not silent):
  - Bundling groups orders by ACTUAL restaurant (routing.store_key), not a
    geohash proxy -- mdrp-sim resorts to geohash only because its own order
    data carries no restaurant id, a limitation mdrplib's instances don't
    share (orders.txt already names the restaurant).
  - Candidate-route feasibility and lateness reuse routing.route_feasibility
    (our existing hard maximum-click-to-door cutoff + soft target-click-to-
    door lateness), instead of leaving routes unconstrained the way
    mdrp-sim's own prospect filter does -- otherwise these policies could
    "win" by building bundles no courier in this benchmark could legally
    finish. `total_tt`/`lateness` from the SAME feasibility check feed the
    cost function below, in place of mdrp-sim's OSRM-estimated
    time-to-first-stop and first-stop-only lateness.
  - The 'graph' / LP-relaxation formulations (mdrpsim_graph*) are built as
    the continuous-variable relaxation of the EXACT SAME assignment LP the
    MIP solves (x in [0, 1] instead of Binary), rather than mdrp-sim's
    hand-built min-cost-flow incidence matrix -- mathematically the same
    relaxation of the same transportation polytope (both integral, by total
    unimodularity), reusing one model instead of a second graph engine.
  - Solved with NO time limit (ilp_policy.get_solver), exactly like every
    one of our 5 ILP objectives: a genuine optimum (or genuine LP optimum)
    every time, never a value capped by a clock. mdrp-sim's own
    prospects=False variants (mdrpsim_mip, mdrpsim_graph) use the FULL
    cross-product of idle couriers x candidate routes with no top-K cap --
    faithful to the original, so expect them to run much slower than
    mdrpsim_graph_prospects (or our own ILPPolicy, which caps at the 25
    nearest couriers per route) on the larger mdrplib instances. That
    slowdown is itself part of what this comparison is for.
"""
from __future__ import annotations

import logging
import math
from typing import List, Tuple, Dict, Any, Optional

from config import Config
from models import Order, Courier
from distance import dist_km
from policies import Policy, GreedyPolicy
from routing import store_key, sequence_stops, route_feasibility
from ilp_policy import _try_import_pulp, get_solver

logger = logging.getLogger(__name__)


# -- Shared bundle construction (mdrp-sim's _generate_group_routes, adapted) ------

def _target_bundle_size(n_ready_orders: int, n_idle_couriers: int, cfg: Config) -> int:
    """
    mdrp-sim's load-adaptive bundle size: ceil(ready orders / idle couriers),
    so busier moments pack bigger bundles automatically (settings.py's
    _calculate_target_bundle_size). Capped by cfg.max_bundle_size so this
    still respects the one transversal bundling knob every other policy in
    this project uses (mdrp-sim's own cap is DISPATCHER_PROSPECTS_MAX_ORDERS).
    """
    if n_idle_couriers <= 0:
        return cfg.max_bundle_size
    return max(1, min(cfg.max_bundle_size, math.ceil(n_ready_orders / n_idle_couriers)))


def _route_internal_distance(seq: List[Order]) -> float:
    total = 0.0
    cursor = seq[0].store_loc
    for o in seq:
        total += dist_km(cursor, o.user_loc)
        cursor = o.user_loc
    return total


def _generate_bundles(orders: List[Order], target_size: int) -> List[Tuple[Order, ...]]:
    """
    Bin-pack pending orders into same-restaurant bundles up to target_size,
    cheapest-insertion by resulting intra-bundle travel distance, processing
    orders in ready_time order -- mdrp-sim's _generate_group_routes, grouped
    by actual restaurant instead of geohash (see module docstring).
    """
    by_store: Dict[Tuple[float, float], List[Order]] = {}
    for o in orders:
        by_store.setdefault(store_key(o), []).append(o)

    routes: List[Tuple[Order, ...]] = []
    for store_orders in by_store.values():
        if target_size <= 1:
            routes.extend((o,) for o in store_orders)
            continue

        bins: List[List[Order]] = []
        for o in sorted(store_orders, key=lambda od: od.ready_time):
            open_bins = [b for b in bins if len(b) < target_size]
            if not open_bins:
                bins.append([o])
                continue
            best_bin, best_dist = None, float('inf')
            for b in open_bins:
                dist = _route_internal_distance(sequence_stops(tuple(b + [o])))
                if dist < best_dist:
                    best_bin, best_dist = b, dist
            best_bin.append(o)
        routes.extend(tuple(b) for b in bins)

    return routes


# -- mdrpsim_greedy: numpy-free port of GreedyMatchingPolicy ----------------------

class MDRPSimGreedyPolicy(Policy):
    """
    Faithful port of mdrp-sim-master's GreedyMatchingPolicy
    (policies/dispatcher/matching/greedy.py): one order at a time, assigned
    to its single nearest not-yet-used idle courier by estimated completion
    time -- no bundling, no optimizer. Distinct from our own GreedyPolicy
    (policies.py), which orders couriers by fewest orders delivered today
    rather than orders by nearest-ETA courier.
    """

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        cfg = self.cfg
        available: Dict[int, Courier] = state['L_t']
        pending:   Dict[int, Order]   = state['O_t']
        t: float = state['time']

        couriers = [c for c in available.values() if c.is_available]
        orders = list(pending.values())
        if not couriers or not orders:
            return []

        used_couriers = set()
        assignments = []
        for o in orders:
            best_c, best_time = None, float('inf')
            for c in couriers:
                if c.courier_id in used_couriers or c.courier_id in o.rejected_by:
                    continue
                result = route_feasibility(c, (o,), t, cfg)
                if result is None:
                    continue
                if result['total_tt'] < best_time:
                    best_c, best_time = c, result['total_tt']
            if best_c is not None:
                used_couriers.add(best_c.courier_id)
                assignments.append((best_c.courier_id, [o.order_id], cfg.pay_per_order))

        return assignments


# -- mdrpsim_mip / mdrpsim_graph / mdrpsim_graph_prospects ------------------------

class MDRPSimMatchingPolicy(Policy):
    """
    Faithful port of mdrp-sim-master's MyopicMatchingPolicy
    (policies/dispatcher/matching/myopic.py): restaurant-grouped, load-
    adaptive bundle construction, then an exact binary-assignment MIP or its
    continuous LP relaxation over (courier, route) prospects, maximizing a
    throughput-density-minus-lateness-penalty cost -- NOT our coverage-
    primary objective. See this module's own docstring for every adaptation.

    Parameters
    ----------
    mip_matcher : True  -> exact binary assignment MIP (mdrp-sim's 'mdrp')
                  False -> continuous [0, 1] LP relaxation of the same
                          problem (mdrp-sim's 'mdrp_graph'/'mdrp_graph_prospects')
    prospects   : True  -> pre-filter (courier, route) pairs by
                          cfg.mdrpsim_prospects_max_distance_km before
                          scoring/solving (mdrp-sim's 'mdrp_graph_prospects')
                  False -> full cross-product of idle couriers x candidate
                          routes (mdrp-sim's 'mdrp'/'mdrp_graph') -- expect
                          this to be much slower on large instances.
    """

    def __init__(self, cfg: Config, mip_matcher: bool, prospects: bool,
                base_greedy: Optional[Policy] = None):
        super().__init__(cfg)
        self._mip_matcher = mip_matcher
        self._prospects = prospects
        self._greedy = base_greedy or GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)
        self._pulp = _try_import_pulp()
        if self._pulp is None:
            logger.warning(
                "PuLP not found -- MDRPSimMatchingPolicy falls back to GreedyPolicy. "
                "Install with: pip install pulp"
            )

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        if self._pulp is None:
            return self._greedy.assign(state)

        available: Dict[int, Courier] = state['L_t']
        pending:   Dict[int, Order]   = state['O_t']
        t: float = state['time']

        couriers = [c for c in available.values() if c.is_available]
        orders = list(pending.values())
        if not couriers or not orders:
            return []

        try:
            return self._solve(couriers, orders, t)
        except Exception as exc:
            logger.warning(f"mdrp-sim matcher error ({exc}), falling back to greedy")
            return self._greedy.assign(state)

    # -- Internals --------------------------------------------------------------------

    def _solve(self, couriers: List[Courier], orders: List[Order],
              t: float) -> List[Tuple[int, List[int], float]]:
        cfg = self.cfg
        pulp = self._pulp

        target_size = _target_bundle_size(len(orders), len(couriers), cfg)
        routes = _generate_bundles(orders, target_size)

        prospects, costs, sequences = self._build_prospects(couriers, routes, t)
        if not prospects:
            return []

        cat = 'Binary' if self._mip_matcher else 'Continuous'
        route_keys = sorted(set(rkey for _, rkey in prospects))

        x = {
            (cid, rkey): pulp.LpVariable(f"x_{cid}_{'_'.join(map(str, rkey))}", 0, 1, cat=cat)
            for cid, rkey in prospects
        }
        supply = {
            rkey: pulp.LpVariable(f"supply_{'_'.join(map(str, rkey))}", 0, 1, cat=cat)
            for rkey in route_keys
        }

        prob = pulp.LpProblem("mdrpsim_matching", pulp.LpMaximize)
        prob += pulp.lpSum(x[k] * costs[k] for k in prospects)

        # Each courier gets at most one route (CourierAssignmentConstraint).
        by_courier: Dict[int, list] = {}
        for cid, rkey in prospects:
            by_courier.setdefault(cid, []).append(x[(cid, rkey)])
        for vs in by_courier.values():
            prob += pulp.lpSum(vs) <= 1

        # Each route goes to exactly one courier, or to its supply slack
        # (RouteAssignmentConstraint) -- this is what lets a route legally
        # go unmatched in a given dispatch cycle.
        by_route: Dict[Tuple[int, ...], list] = {}
        for cid, rkey in prospects:
            by_route.setdefault(rkey, []).append(x[(cid, rkey)])
        for rkey, vs in by_route.items():
            prob += pulp.lpSum(vs) + supply[rkey] == 1

        prob.solve(get_solver(pulp, cfg))
        if pulp.value(prob.status) < 0:
            return []

        # mdrp-sim's own SOLUTION_VALUE threshold, needed because the LP
        # relaxation can return near-1 fractional values rather than exact 1.
        assignments = []
        for (cid, rkey), var in x.items():
            val = pulp.value(var)
            if val is not None and val >= 0.99:
                seq = sequences[(cid, rkey)]
                oids = [o.order_id for o in seq]
                assignments.append((cid, oids, cfg.pay_per_order * len(oids)))

        return assignments

    def _build_prospects(self, couriers: List[Courier], routes: List[Tuple[Order, ...]],
                         t: float):
        cfg = self.cfg
        prospects = []
        costs: Dict[Tuple[int, Tuple[int, ...]], float] = {}
        sequences: Dict[Tuple[int, Tuple[int, ...]], List[Order]] = {}

        for route in routes:
            store_loc = route[0].store_loc
            candidate_couriers = couriers
            if self._prospects:
                candidate_couriers = [
                    c for c in couriers
                    if dist_km(c.location, store_loc) <= cfg.mdrpsim_prospects_max_distance_km
                ]
                if not candidate_couriers:
                    continue

            rkey = tuple(sorted(o.order_id for o in route))
            for c in candidate_couriers:
                result = route_feasibility(c, route, t, cfg)
                if result is None:
                    continue

                total_tt = result['total_tt']
                lateness = result['lateness']
                # mdrp-sim's own cost (myopic.py._generate_matching_costs):
                # orders-per-unit-time (throughput density) minus a
                # delay-penalty-weighted lateness term. Here total_tt/lateness
                # are the whole bundle's (routing.route_feasibility), not just
                # the first stop's, since that's what the shared feasibility
                # check already computes.
                cost = len(route) / max(total_tt, 1e-6) - cfg.mdrpsim_delay_penalty * lateness

                key = (c.courier_id, rkey)
                prospects.append(key)
                costs[key] = cost
                sequences[key] = result['sequence']

        return prospects, costs, sequences


def build_mdrpsim_policy(name: str, cfg: Config) -> Policy:
    if name == 'mdrpsim_greedy':
        return MDRPSimGreedyPolicy(cfg)
    if name == 'mdrpsim_mip':
        return MDRPSimMatchingPolicy(cfg, mip_matcher=True, prospects=False)
    if name == 'mdrpsim_graph':
        return MDRPSimMatchingPolicy(cfg, mip_matcher=False, prospects=False)
    if name == 'mdrpsim_graph_prospects':
        return MDRPSimMatchingPolicy(cfg, mip_matcher=False, prospects=True)
    raise ValueError(
        f"Unknown mdrp-sim policy '{name}'. Choices: mdrpsim_greedy | mdrpsim_mip | "
        f"mdrpsim_graph | mdrpsim_graph_prospects."
    )
