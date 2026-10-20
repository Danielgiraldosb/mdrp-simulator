"""
Shared single-restaurant bundle construction and feasibility check.

Every assignment policy (Greedy, FairGreedy, ILP) imports from this module
instead of each having its own copy, so that cfg.max_bundle_size is a single
transversal parameter: changing it changes behaviour consistently no matter
which policy is in effect. Previously Greedy/FairGreedy ignored it entirely
(always single-order) and the ILP's max_equity objective ignored it too
(hard-coded singleton-only) -- this module is the fix for both.
"""
from __future__ import annotations

from typing import List, Tuple, Dict, Any, Optional

from config import Config
from models import Order, Courier
from distance import dist_km, dist_m, travel_time_min, speed_of


def store_key(order: Order) -> Tuple[float, float]:
    """Group orders by restaurant location (rounded to the nearest meter)."""
    return (round(order.store_loc.x), round(order.store_loc.y))


def sequence_stops(route: Tuple[Order, ...]) -> List[Order]:
    """Order a route's drop-offs by nearest-neighbour from the store outward."""
    if len(route) == 1:
        return [route[0]]
    remaining = list(route)
    cursor = route[0].store_loc
    sequence = []
    while remaining:
        nxt = min(remaining, key=lambda o: dist_km(cursor, o.user_loc))
        sequence.append(nxt)
        cursor = nxt.user_loc
        remaining.remove(nxt)
    return sequence


def route_feasibility(courier: Courier, route: Tuple[Order, ...], t: float,
                      cfg: Config) -> Optional[Dict[str, Any]]:
    """
    Cumulative feasibility across the whole sequenced route (bundle or
    singleton): every stop must meet its OWN maximum click-to-door (plus
    cfg.late_tolerance_min grace) given its position in the delivery
    sequence. Returns None if infeasible, else
    {'lateness', 'total_tt', 'sequence'}.
    """
    mpm = speed_of(courier, cfg)
    store_loc = route[0].store_loc

    tt_to_store = travel_time_min(courier.location, store_loc, mpm)
    ready_ok = max(o.ready_time for o in route)
    pickup_done = max(t + tt_to_store, ready_ok) + cfg.pickup_service_min

    sequence = sequence_stops(route)

    cursor_loc = store_loc
    cursor_t = pickup_done
    total_tt = tt_to_store + cfg.pickup_service_min
    total_lateness = 0.0

    for o in sequence:
        tt = travel_time_min(cursor_loc, o.user_loc, mpm)
        cursor_t += tt + cfg.dropoff_service_min
        total_tt += tt + cfg.dropoff_service_min

        c2d = cursor_t - o.placement_time
        if c2d > o.max_click_to_door + cfg.late_tolerance_min:
            return None

        total_lateness += max(0.0, c2d - o.target_click_to_door)
        cursor_loc = o.user_loc

    return {'lateness': total_lateness, 'total_tt': total_tt, 'sequence': sequence}


def generate_store_routes(orders: List[Order], max_bundle_size: int) -> List[Tuple[Order, ...]]:
    """
    Group pending orders into candidate routes, one per restaurant. Every
    order also gets its own singleton route; a store with more than one
    pending order additionally gets ONE bundle candidate (its
    max_bundle_size most urgent orders, by absolute deadline), so a solver
    can fall back to one-at-a-time delivery when the bundle isn't jointly
    feasible or isn't picked. Used by the ILP's route-based objectives.
    """
    if max_bundle_size <= 1:
        return [(o,) for o in orders]

    routes: List[Tuple[Order, ...]] = []
    by_store: Dict[Tuple[float, float], List[Order]] = {}
    for o in orders:
        by_store.setdefault(store_key(o), []).append(o)

    for store_orders in by_store.values():
        for o in store_orders:
            routes.append((o,))
        if len(store_orders) > 1:
            by_urgency = sorted(store_orders, key=lambda o: o.placement_time + o.max_click_to_door)
            bundle = tuple(by_urgency[:max_bundle_size])
            if len(bundle) > 1:
                routes.append(bundle)

    return routes


def best_route_for_courier(courier: Courier,
                           pending_by_store: Dict[Tuple[float, float], List[Order]],
                           t: float, cfg: Config) -> Optional[List[Order]]:
    """
    Greedy helper: "nearest feasible order", generalised to bundles.

    Among every store with at least one pending order not already rejected
    by this courier, return the sequenced route at the NEAREST such store:
    a bundle of up to cfg.max_bundle_size of that store's most urgent
    orders when more than one is pending there and the whole bundle is
    jointly feasible, otherwise the single most urgent feasible order from
    that store. Returns None if no store has any feasible route at all.
    """
    # Stores sorted by distance: the first store with a feasible route IS the nearest
    # feasible one, so feasibility is evaluated at a handful of stores instead of all.
    # Plus an exact necessary condition (earliest possible drop-off vs latest deadline)
    # that skips stores no route from which can be feasible. Same result as the
    # original scan; Etapa 4 finding H7 (greedy took 35 min on the Bogota zone because
    # 2,650 couriers each evaluated every pending store).
    stores = []
    for orders_here in pending_by_store.values():
        candidates = [o for o in orders_here if courier.courier_id not in o.rejected_by]
        if candidates:
            stores.append((dist_km(courier.location, candidates[0].store_loc), candidates))
    stores.sort(key=lambda item: item[0])
    mpm = speed_of(courier, cfg)
    overhead = cfg.pickup_service_min + cfg.dropoff_service_min

    for dist, candidates in stores:
        # Exact necessary condition per order: even served alone and first, the drop-off
        # cannot happen before max(arrival, ready) + pickup + store->user + drop-off.
        # Orders that fail it (typically "dead on arrival": ready time already past the
        # hard SLA) are what made every courier scan every store on the Bogota zone.
        if mpm > 0:
            t_arrive = t + dist * 1000.0 / mpm
            ok = [o for o in candidates
                  if max(t_arrive, o.ready_time) + overhead + dist_m(o.store_loc, o.user_loc) / mpm
                  <= o.placement_time + o.max_click_to_door + cfg.late_tolerance_min]
            if not ok:
                continue
        else:
            ok = candidates
        ok_ids = {o.order_id for o in ok}

        seq = None
        if cfg.max_bundle_size > 1 and len(candidates) > 1:
            by_urgency = sorted(candidates, key=lambda o: o.placement_time + o.max_click_to_door)
            bundle = tuple(by_urgency[:cfg.max_bundle_size])
            # a bundle with a member that fails its own bound is infeasible: skip the check
            if all(o.order_id in ok_ids for o in bundle):
                result = route_feasibility(courier, bundle, t, cfg)
                if result is not None:
                    seq = result['sequence']

        if seq is None:
            feasible_singles = [
                o for o in ok
                if route_feasibility(courier, (o,), t, cfg) is not None
            ]
            if feasible_singles:
                seq = [min(feasible_singles, key=lambda o: o.placement_time + o.max_click_to_door)]

        if seq is not None:
            return seq

    return None
