"""
ILP / MIP assignment policies using PuLP -- adapted to mdrplib's single
instance-wide travel speed and its two click-to-door SLAs (target = soft,
maximum = hard feasibility cutoff).

Install: pip install pulp
Gurobi:  pip install gurobipy  (requires a Gurobi license)

Five formulations (cfg.objective), ALL five sharing the same route/bundle
candidates, the same two hard constraints (each order at most one route,
each courier at most one route), AND -- this is the point -- the same
TRUE primary objective: maximize coverage. cfg.objective only picks the
secondary rule used to break ties among coverage-maximal solutions; none
of the five can trade away a coverable order for a "better" tie-break
score. This matches how Greedy/FairGreedy behave too (policies.py): a
classic greedy heuristic for the same maximum-coverage goal, just with no
formal guarantee of hitting it and a different priority rule for who asks
first. Coverage's own raw value (how many orders a solution actually
covers) is always available from a run's results as the `n_delivered` /
`coverage_rate` metrics (metrics.py) -- identically defined and computed
the same way for all 7 policies, independent of cfg.objective -- so a
sensitivity study can compare any of them on equal footing and still read
off cost, lateness and equity as outcomes rather than competing targets.
  max_coverage   -- maximize orders covered (weighted by bundle size)  [DEFAULT]
  max_throughput -- maximize coverage, tie-break by travel_min + lateness_min
                    combined (lambda/mu weighted)
  min_lateness   -- maximize coverage, tie-break by minimizing total lateness
  min_cost       -- maximize coverage, tie-break by minimizing total travel time
  max_equity     -- maximize coverage, tie-break by favouring low-earning couriers

max_throughput used to be the one exception: without an M-dominant term it
could leave an order uncovered whenever no feasible route for it scored
"worth it" under the lambda/mu weights -- the only one of the 5 NOT
sharing coverage as its true objective. Fixed below by giving it the same
M*len(rkey) dominant term the other three already had.

Falls back silently to GreedyPolicy if PuLP is not installed.

Bundling (routing.py): when cfg.max_bundle_size > 1, pending orders are
grouped by store into candidate ROUTES: each route serves exactly one
store, with 1 (singleton) or up to cfg.max_bundle_size orders from that
store, sequenced by nearest neighbour from the store outward. Feasibility
(each stop's own maximum click-to-door) is checked cumulatively across the
whole sequenced route. A courier picks at most one route (bundle or
singleton). This is the SAME route-construction and feasibility code
Greedy/FairGreedy use (policies.py) and applies to all five objectives
above -- including max_equity, which used to be hard-coded singleton-only
regardless of cfg.max_bundle_size. That made bundling a non-transversal
parameter (it worked for 4 of 7 policies, never for max_equity, never for
Greedy/FairGreedy); routing.py plus this file is the fix.
"""
from __future__ import annotations

import logging
from typing import List, Tuple, Dict, Any, Optional

from config import Config
from models import Order, Courier
from distance import dist_km
from policies import Policy, GreedyPolicy
from routing import sequence_stops, route_feasibility, generate_store_routes

logger = logging.getLogger(__name__)

# max_throughput's tie-break weights (per MINUTE -- see
# routing.route_feasibility for the shared feasibility model these costs are
# computed against). Now that coverage is the dominant term (M*len(rkey)),
# these only decide which coverage-maximal solution to prefer -- they can no
# longer affect HOW MANY orders get covered, only WHICH routes serve them.
# Kept at the same magnitude used before that fix (0.01 / 0.02, already a
# recalibration of a per-SECOND constant inherited from the original thesis
# simulator -- 0.06 / 0.12 -- that had been merely multiplied by 60 for the
# unit change to minutes) so the tie-break still meaningfully distinguishes
# a typical route (~15-25 min total_tt, ~0-2 min lateness) from an unusually
# long or late one, without either term swamping the other.
_LAMBDA_COST = 0.01   # penalty per minute of total travel
_MU_DELAY    = 0.02   # penalty per minute of expected lateness (vs. target click-to-door)

# Route-based path: cap the candidate search to the K nearest couriers per
# route. Without this, cost is O(|couriers| x |routes|) per dispatch call,
# which snowballs at scale. Applies uniformly to all five objectives.
_ROUTE_TOP_K = 25


def _try_import_pulp():
    try:
        import pulp
        return pulp
    except ImportError:
        return None


def get_solver(pulp, cfg: Config):
    """
    Shared no-time-limit solver factory -- used by ILPPolicy and by the
    mdrp-sim-ported matching policies (mdrpsim_policies.py) alike, so every
    MIP/LP solved anywhere in this project follows the same rule: None means
    no time limit at all, the solver runs until it proves optimality (or
    exhausts its own search), so every reported solution is a genuine
    optimum -- never a value silently capped or substituted because a clock
    ran out.
    """
    name = cfg.ilp_solver.upper()
    tl = cfg.ilp_time_limit_sec
    tl_int = int(tl) if tl is not None else None

    if name == 'GUROBI':
        # Prefer the in-process gurobipy backend (no LP file round trip per solve;
        # the file-based GUROBI_CMD dominated MIP-Fair's round time in the Etapa 4 pilot).
        try:
            api = pulp.GUROBI(msg=0, timeLimit=tl_int)
            if api.available():
                return api
        except Exception:
            pass
        try:
            return pulp.GUROBI_CMD(msg=0, timeLimit=tl_int)
        except Exception:
            logger.warning("Gurobi unavailable -- falling back to CBC")
    if name == 'CPLEX':
        try:
            return pulp.CPLEX_CMD(msg=0, timelimit=tl_int)
        except Exception:
            logger.warning("CPLEX unavailable -- falling back to CBC")

    return pulp.PULP_CBC_CMD(msg=0, timeLimit=tl_int)


class ILPPolicy(Policy):
    """
    Integer Programming assignment policy.

    Parameters
    ----------
    cfg        : Config -- reads objective, ilp_solver, ilp_time_limit_sec,
                 max_bundle_size, pay_per_order, pickup/dropoff service,
                 and each order's own target/maximum click-to-door
    base_greedy: fallback policy when PuLP is unavailable or the problem is empty
    """

    def __init__(self, cfg: Config, base_greedy: Optional[Policy] = None):
        super().__init__(cfg)
        self._greedy = base_greedy or GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)
        self._pulp = _try_import_pulp()

        if self._pulp is None:
            logger.warning(
                "PuLP not found -- ILPPolicy falls back to GreedyPolicy. "
                "Install with: pip install pulp"
            )

    # -- Public interface -----------------------------------------------------------

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
            return self._solve_routes(couriers, orders, t)
        except Exception as exc:
            logger.warning(f"ILP solver error ({exc}), falling back to greedy")
            return self._greedy.assign(state)

    # acceptance_prob() is inherited from Policy -- delegates to
    # cfg.acceptance_mode (acceptance.py), same as every other policy.

    # -- Route-based MIP, shared by all five objectives -------------------------------

    def _solve_routes(self, couriers: List[Courier], orders: List[Order],
                      t: float) -> List[Tuple[int, List[int], float]]:
        pulp = self._pulp
        cfg = self.cfg

        routes = generate_store_routes(orders, cfg.max_bundle_size)
        feasible_pairs, costs, sequences = self._precompute_routes(couriers, routes, t)

        if not feasible_pairs:
            return []

        x = {
            (cid, rkey): pulp.LpVariable(f"x_{cid}_{'_'.join(map(str, rkey))}", cat='Binary')
            for cid, rkey in feasible_pairs
        }

        prob = pulp.LpProblem("MDRP", pulp.LpMaximize)
        obj = cfg.objective

        if obj == 'max_coverage':
            # Weight by len(rkey): a route's contribution to coverage is the
            # number of orders it covers, not "1 route" -- otherwise bundling
            # would never be preferred over spreading orders across couriers.
            prob += pulp.lpSum(x[cid, rkey] * len(rkey) for cid, rkey in feasible_pairs)

        elif obj == 'max_throughput':
            # M-dominant, same as the other 3 tie-break objectives below: the
            # shared primary objective across all 5 ILP variants is coverage
            # (M always outweighs the combined travel+lateness penalty -- see
            # the _LAMBDA_COST/_MU_DELAY comment above for the bound). Before
            # this fix, max_throughput was the one objective that could leave
            # an order uncovered when no feasible route for it was "worth it"
            # -- the only one of the 5 NOT sharing coverage as the true
            # objective. λ/μ now only decide which of the coverage-optimal
            # solutions to prefer, exactly like min_lateness/min_cost/max_equity.
            M = cfg.max_click_to_door
            prob += pulp.lpSum(
                x[cid, rkey] * (
                    M * len(rkey)
                    - _LAMBDA_COST * costs[(cid, rkey)]['total_tt']
                    - _MU_DELAY    * costs[(cid, rkey)]['lateness']
                )
                for cid, rkey in feasible_pairs
            )

        elif obj == 'min_lateness':
            M = cfg.max_click_to_door
            prob += pulp.lpSum(
                x[cid, rkey] * (M * len(rkey) - costs[(cid, rkey)]['lateness'])
                for cid, rkey in feasible_pairs
            )

        elif obj == 'min_cost':
            M = cfg.max_click_to_door
            prob += pulp.lpSum(
                x[cid, rkey] * (M * len(rkey) - costs[(cid, rkey)]['total_tt'])
                for cid, rkey in feasible_pairs
            )

        elif obj == 'max_equity':
            # Same M-dominant coverage term as the other tie-break objectives;
            # the secondary term favours couriers with lower accumulated
            # earnings (MaxMin proxy), weighted by the courier alone (not the
            # specific order), scaled by route size for consistency with how
            # every other objective counts a bundle's contribution.
            M = cfg.max_click_to_door
            earnings_by_courier = {c.courier_id: c.history.earnings for c in couriers}
            prob += pulp.lpSum(
                x[cid, rkey] * len(rkey) * (M + 1.0 / (1.0 + earnings_by_courier.get(cid, 0.0)))
                for cid, rkey in feasible_pairs
            )

        else:
            logger.warning(f"Unknown objective '{obj}', using max_coverage")
            prob += pulp.lpSum(x.values())

        # Each order served by at most one route (bundle or singleton)
        order_pairs: Dict[int, list] = {}
        for cid, rkey in feasible_pairs:
            for oid in rkey:
                order_pairs.setdefault(oid, []).append(x[cid, rkey])
        for oid, vs in order_pairs.items():
            prob += pulp.lpSum(vs) <= 1

        # Each courier picks at most one route -- a bundle already packs up
        # to max_bundle_size orders from a single store inside itself.
        courier_pairs: Dict[int, list] = {}
        for cid, rkey in feasible_pairs:
            courier_pairs.setdefault(cid, []).append(x[cid, rkey])
        for cid, vs in courier_pairs.items():
            prob += pulp.lpSum(vs) <= 1

        prob.solve(self._get_solver())
        if pulp.value(prob.status) < 0:
            return []

        assignments = []
        for (cid, rkey), var in x.items():
            if pulp.value(var) is not None and pulp.value(var) > 0.5:
                seq = sequences[(cid, rkey)]
                oids = [o.order_id for o in seq]
                assignments.append((cid, oids, cfg.pay_per_order * len(oids)))

        return assignments

    # -- Helpers ----------------------------------------------------------------------

    def _precompute_routes(self, couriers: List[Courier],
                           routes: List[Tuple[Order, ...]], t: float):
        """
        For each (courier, candidate route) pair, check cumulative time
        feasibility and compute travel cost, expected lateness, and the
        nearest-neighbour delivery sequence (routing.route_feasibility).

        Bounds the search to the _ROUTE_TOP_K nearest couriers per route
        (straight-line distance to the store) instead of every idle
        courier, to keep dispatch calls fast at scale -- applies uniformly
        to all five objectives, including max_equity.
        """
        feasible = []
        costs = {}
        sequences = {}

        for route in routes:
            store_loc = route[0].store_loc
            nearest = sorted(couriers, key=lambda c: dist_km(c.location, store_loc))[:_ROUTE_TOP_K]

            for c in nearest:
                result = route_feasibility(c, route, t, self.cfg)
                if result is None:
                    continue
                route_key = tuple(sorted(o.order_id for o in route))
                key = (c.courier_id, route_key)
                feasible.append(key)
                costs[key] = {'lateness': result['lateness'], 'total_tt': result['total_tt']}
                sequences[key] = result['sequence']

        return feasible, costs, sequences

    def _get_solver(self):
        return get_solver(self._pulp, self.cfg)
