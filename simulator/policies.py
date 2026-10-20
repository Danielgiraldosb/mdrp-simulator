"""
Pluggable assignment policies -- adapted to mdrplib's single instance-wide
travel speed (meters_per_minute) and its two click-to-door SLAs (target =
soft, used for lateness; maximum = hard, used as the feasibility cutoff).

Shared objective: GreedyPolicy and FairGreedyPolicy are both classic greedy
heuristics for the SAME objective the ILP's 5 formulations all share --
maximize coverage (ilp_policy.py's module docstring). Neither has a formal
objective function or compares candidate solutions; each applies one rule,
once per courier, with no guarantee of reaching the coverage-maximal
solution an ILP run would find. They differ from each other, and from the
ILP, only in HOW they get there: Greedy asks couriers in order of fewest
orders delivered today, FairGreedy in order of lowest hourly earnings (plus
a pay bonus) -- analogous to how the ILP's cfg.objective only picks a
secondary tie-break among coverage-maximal solutions. A run's actual
coverage (how many orders it covered) is always readable from its results
as the n_delivered / coverage_rate metrics (metrics.py), computed the same
way regardless of which of the 7 policies produced them -- so a
sensitivity study can compare all 7 on that common ground and still read
off cost, lateness and equity as outcomes, not as what each one targeted.

Bundling: GreedyPolicy and FairGreedyPolicy share the exact same route
construction and feasibility logic as the ILP (routing.py), gated by the
one transversal cfg.max_bundle_size -- changing that single parameter
changes bundling behaviour consistently across every policy.

Acceptance: whether a notified courier actually takes the route is a
SEPARATE, transversal concern (acceptance.py), selected once via
cfg.acceptance_mode ('auto' | 'fixed' | 'logistic') and shared by every
policy through the Policy base class below -- so any assignment logic
(Greedy, FairGreedy, or any ILP objective) can be combined with any of the
3 acceptance criteria without touching assignment code. There used to be a
separate LogisticAcceptancePolicy that only worked by wrapping Greedy's
own assign(); it is gone, replaced by cfg.acceptance_mode='logistic',
which now works with every policy.

Each policy implements:
  assign(state) -> List[(courier_id, [order_ids], pay_offer)]
acceptance_prob() is implemented once, in the Policy base class.

The simulator calls assign() at every rolling-horizon trigger, then draws
Bernoulli(acceptance_prob) for each (courier, route) pair.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Any

from config import Config
from models import Order, Courier
from routing import store_key, best_route_for_courier
from acceptance import build_acceptance_model


# -- Base class --------------------------------------------------------------------

class Policy:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.acceptance_model = build_acceptance_model(cfg.acceptance_mode)

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        raise NotImplementedError

    def acceptance_prob(self, courier: Courier, orders: List[Order],
                        pay_offer: float, state: Dict[str, Any]) -> float:
        """Delegates to cfg.acceptance_mode's model -- same for every policy."""
        return self.acceptance_model.prob(courier, orders, pay_offer, self.cfg)


def _group_by_store(pending: Dict[int, Order]) -> Dict[Tuple[float, float], List[Order]]:
    by_store: Dict[Tuple[float, float], List[Order]] = {}
    for o in pending.values():
        by_store.setdefault(store_key(o), []).append(o)
    return by_store


def _remove_from_groups(by_store: Dict[Tuple[float, float], List[Order]], route: List[Order]) -> None:
    """Drop the orders of an assigned route from the store groups (keeps insertion order)."""
    for o in route:
        key = store_key(o)
        group = by_store.get(key)
        if group is None:
            continue
        group[:] = [p for p in group if p.order_id != o.order_id]
        if not group:
            del by_store[key]


# -- Greedy (corporate baseline) -----------------------------------------------------

class GreedyPolicy(Policy):
    """
    For each available courier (sorted by equity deficit so the least-served
    courier gets first pick), take the best route at the nearest store: a
    bundle of up to cfg.max_bundle_size orders from that store when more
    than one is pending there and the whole bundle is jointly feasible,
    otherwise the single nearest feasible order (cfg.max_bundle_size <= 1
    disables bundling entirely). Pay is the instance's flat pay_per_order
    times the number of orders served in that route.
    """

    def __init__(self, pay_per_order: float = 10.0, *, cfg: Config):
        super().__init__(cfg)
        self.pay_per_order = pay_per_order

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        available: Dict[int, Courier] = state['L_t']
        pending:   Dict[int, Order]   = dict(state['O_t'])
        now = state['time']

        sorted_couriers = sorted(available.values(), key=lambda c: c.history.orders_delivered)

        assignments = []
        by_store = _group_by_store(pending)       # maintained incrementally (was rebuilt per courier)
        for courier in sorted_couriers:
            if not pending:
                break
            if not courier.is_available:
                continue

            route = best_route_for_courier(courier, by_store, now, self.cfg)
            if route is None:
                continue

            assignments.append((
                courier.courier_id,
                [o.order_id for o in route],
                self.pay_per_order * len(route),
            ))
            for o in route:
                del pending[o.order_id]
            _remove_from_groups(by_store, route)

        return assignments


# -- Fair Greedy -------------------------------------------------------------------------

class FairGreedyPolicy(GreedyPolicy):
    """
    Same route selection as GreedyPolicy (bundling included), with an
    equity-adjustment: couriers with lower-than-average hourly earnings get
    priority (asked first) and a pay bonus added once per route, regardless
    of how many orders it bundles.
    """

    def __init__(self, pay_per_order: float = 10.0, equity_bonus: float = 3.0,
                 *, cfg: Config):
        super().__init__(pay_per_order, cfg=cfg)
        self.equity_bonus = equity_bonus

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        available: Dict[int, Courier] = state['L_t']
        now = state['time']

        earnings = [c.history.hourly_earnings for c in available.values()
                   if c.history.active_time > 0]
        mean_w = sum(earnings) / len(earnings) if earnings else 0.0

        pending = dict(state['O_t'])
        sorted_couriers = sorted(available.values(), key=lambda c: c.history.hourly_earnings)

        assignments = []
        by_store = _group_by_store(pending)
        for courier in sorted_couriers:
            if not pending or not courier.is_available:
                continue

            route = best_route_for_courier(courier, by_store, now, self.cfg)
            if route is None:
                continue

            bonus = self.equity_bonus if courier.history.hourly_earnings < mean_w else 0.0
            pay = self.pay_per_order * len(route) + bonus

            assignments.append((courier.courier_id, [o.order_id for o in route], pay))
            for o in route:
                del pending[o.order_id]
            _remove_from_groups(by_store, route)

        return assignments
