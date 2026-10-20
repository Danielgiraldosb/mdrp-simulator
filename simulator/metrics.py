"""
Performance and fairness metrics for the mdrplib-adapted simulator.

Two blocks:
  - Order/economic block mirrors the OFFICIAL evaluator's own vocabulary
    (MDRP_code/compute_performance_summary.py): click-to-door, ready-to-door,
    ready-to-pickup, click-to-door overage, bundle size, total payment, and
    the guaranteed-pay "true-up" mechanic from instance_parameters.txt
    (a courier whose order-based earnings fall short of
    shift_hours * guaranteed_pay_per_hour is topped up to that amount).
  - Fairness block (F_Gini, F_MaxMin, F_Orders, F_Deficit, F_Dist) mirrors
    the thesis's own equity framework, computed on POST-true-up payment --
    i.e. what a courier actually takes home, guarantee included.
    F_Deficit compares against cfg.min_wage_hourly, an EXTERNAL statutory
    threshold independent of the platform's own guaranteed_pay_per_hour
    (defaults to guaranteed_pay_per_hour when not set explicitly).
"""
from __future__ import annotations
import math
from typing import Dict, List, Any

from config import Config
from models import Courier, Order


# -- Gini / dispersion -------------------------------------------------------------

def gini(values: List[float]) -> float:
    """G = sum_ij |xi-xj| / (2*n*sum(x)). 0 for <=1 value or when all values are equal."""
    n = len(values)
    if n <= 1:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    numerator = sum(abs(values[i] - values[j]) for i in range(n) for j in range(n))
    return numerator / (2.0 * n * total)


def coeff_variation(values: List[float]) -> float:
    """Coefficient of variation (std/mean). 0 if mean = 0."""
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    if mean == 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var) / mean


def _describe(values: List[float], prefix: str, ndigits: int = 2) -> Dict[str, float]:
    """mean/std/min/p10/median/p90/max -- same percentiles compute_performance_summary.py reports."""
    keys = ('mean', 'std', 'min', 'p10', 'median', 'p90', 'max')
    if not values:
        return {f'{prefix}_{k}': 0.0 for k in keys}

    s = sorted(values)
    n = len(s)

    def pct(p):
        idx = p * (n - 1)
        lo, hi = int(math.floor(idx)), int(math.ceil(idx))
        if lo == hi:
            return s[lo]
        frac = idx - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    mean = sum(s) / n
    var = sum((v - mean) ** 2 for v in s) / n
    return {
        f'{prefix}_mean':   round(mean, ndigits),
        f'{prefix}_std':    round(math.sqrt(var), ndigits),
        f'{prefix}_min':    round(s[0], ndigits),
        f'{prefix}_p10':    round(pct(0.10), ndigits),
        f'{prefix}_median': round(pct(0.50), ndigits),
        f'{prefix}_p90':    round(pct(0.90), ndigits),
        f'{prefix}_max':    round(s[-1], ndigits),
    }


# -- Throughput cost model ------------------------------------------------------------

def throughput_cost(delivery_log: List[Dict[str, Any]]) -> float:
    """
    len(delivered) / total_route_time_h - total_overage_h.
    Returns 0 if no deliveries or zero route time.
    """
    n = len(delivery_log)
    if n == 0:
        return 0.0
    total_route_h   = sum(ev.get('route_time_min', 0.0) for ev in delivery_log) / 60.0
    total_overage_h = sum(ev.get('overage_min',    0.0) for ev in delivery_log) / 60.0
    if total_route_h <= 0:
        return 0.0
    return n / total_route_h - total_overage_h


# -- Main metrics function -------------------------------------------------------------

def compute_metrics(results: Dict[str, Any], cfg: Config,
                    wall_clock_sec: float = None) -> Dict[str, Any]:
    """
    wall_clock_sec: optional REAL (wall-clock) seconds the caller measured for
    the whole env.run() call -- not read from `results`, since nothing inside
    the simulation measures its own total runtime. Folded into the returned
    dict as-is for cross-policy comparison (run.py / batch_sensitivity.py).
    """
    orders: Dict[int, Order]     = results['orders']
    couriers: Dict[int, Courier] = results['couriers']
    delivery_log: List[dict]     = results.get('delivery_log', [])
    bundle_sizes: List[int]      = results.get('bundle_sizes', [])
    dispatch_times: List[float]  = results.get('dispatch_times', [])

    all_orders = list(orders.values())
    n_total     = len(all_orders)
    n_delivered = sum(1 for o in all_orders if o.is_delivered)
    n_canceled  = sum(1 for o in all_orders if o.is_canceled)
    coverage    = n_delivered / n_total if n_total > 0 else 0.0

    c2d     = [o.click_to_door         for o in all_orders if o.click_to_door is not None]
    r2d     = [o.ready_to_door         for o in all_orders if o.ready_to_door is not None]
    r2p     = [o.ready_to_pickup       for o in all_orders if o.ready_to_pickup is not None]
    overage = [o.click_to_door_overage for o in all_orders if o.click_to_door_overage is not None]

    m: Dict[str, Any] = {
        'n_orders':        n_total,
        'n_delivered':     n_delivered,
        'n_canceled':      n_canceled,
        'coverage_rate':   round(coverage, 4),
        'throughput_cost': round(throughput_cost(delivery_log), 4),
    }
    m.update(_describe(c2d, 'c2d'))
    m.update(_describe(r2d, 'r2d'))
    m.update(_describe(r2p, 'r2p'))
    m.update(_describe(overage, 'overage'))
    m.update(_describe([float(b) for b in bundle_sizes], 'bundle_size'))

    # Real (wall-clock) computation cost -- how long this policy actually took
    # to decide, independent of what it decided. solve_* is per dispatch round
    # (seconds); compare solve_max against cfg.rolling_horizon*60 (seconds) to
    # check whether a policy could plausibly be re-run that often for real.
    m.update(_describe(dispatch_times, 'solve', ndigits=5))
    m['solve_calls'] = len(dispatch_times)
    if wall_clock_sec is not None:
        m['wall_clock_sec'] = round(wall_clock_sec, 4)

    active_couriers = [c for c in couriers.values() if c.history.active_time > 0]
    if not active_couriers:
        m.update({
            'n_couriers_active': 0, 'total_payment': 0.0, 'proportion_trueup': 1.0,
            'mean_hourly_earn': 0.0,
            'F_Gini': 0.0, 'F_MaxMin': 0.0, 'F_Orders': 0.0, 'F_Deficit': 1.0, 'F_Dist': 0.0,
        })
        return m

    min_wage = cfg.min_wage_hourly if cfg.min_wage_hourly is not None else cfg.guaranteed_pay_per_hour

    order_earnings = {c.courier_id: c.history.earnings for c in active_couriers}
    hours          = {c.courier_id: c.shift_duration / 60.0 for c in active_couriers}
    guaranteed     = {cid: hours[cid] * cfg.guaranteed_pay_per_hour for cid in order_earnings}
    payment        = {cid: max(order_earnings[cid], guaranteed[cid]) for cid in order_earnings}

    w               = [payment[cid] / hours[cid] for cid in payment if hours[cid] > 0]
    orders_per_hour = [c.history.orders_delivered / hours[c.courier_id]
                       for c in active_couriers if hours[c.courier_id] > 0]
    dist_per_hour   = [c.history.dist_traveled / hours[c.courier_id]
                       for c in active_couriers if hours[c.courier_id] > 0]

    proportion_trueup = (sum(1 for cid in payment if order_earnings[cid] < guaranteed[cid])
                         / len(payment))

    # Day-level totals of the hierarchical model's objectives (hier/): minutes
    # of courier time committed (objective 'cost') and total overage minutes
    # (objective 'lateness'), so every policy can be read on the same four
    # objectives -- coverage_rate, overage_total_min, F_Gini/F_Deficit,
    # courier_active_min_total -- whatever it optimised internally.
    m['overage_total_min'] = round(sum(overage), 2)
    m['courier_active_min_total'] = round(sum(c.history.active_time for c in active_couriers), 2)
    m['courier_dist_km_total'] = round(sum(c.history.dist_traveled for c in active_couriers), 2)

    m.update({
        'n_couriers_active':  len(active_couriers),
        'total_payment':      round(sum(payment.values()), 2),
        'proportion_trueup':  round(proportion_trueup, 4),
        'mean_hourly_earn':   round(sum(w) / len(w), 2) if w else 0.0,
        'F_Gini':    round(gini(w), 4),
        'F_MaxMin':  round(min(w), 2) if w else 0.0,
        'F_Orders':  round(gini(orders_per_hour), 4),
        'F_Deficit': round(sum(1 for wi in w if wi < min_wage) / len(w), 4) if w else 1.0,
        'F_Dist':    round(coeff_variation(dist_per_hour), 4),
    })
    return m


# -- Per-courier summary table ---------------------------------------------------------

def courier_table(couriers: Dict[int, Courier], cfg: Config) -> List[Dict[str, Any]]:
    rows = []
    for c in sorted(couriers.values(), key=lambda x: x.courier_id):
        h = c.history
        shift_h = c.shift_duration / 60.0
        util = h.active_time / c.shift_duration if c.shift_duration > 0 else 0.0
        guaranteed = shift_h * cfg.guaranteed_pay_per_hour
        payment = max(h.earnings, guaranteed)
        rows.append({
            'courier_id':          c.courier_id,
            'vehicle':             c.vehicle or '',
            'shift_h':             round(shift_h, 2),
            'active_h':            round(h.active_time / 60.0, 2),
            'utilization':         round(util, 3),
            'orders':              h.orders_delivered,
            'order_earnings':      round(h.earnings, 2),
            'guaranteed_earnings': round(guaranteed, 2),
            'payment':             round(payment, 2),
            'earn_per_hr':         round(payment / shift_h, 2) if shift_h > 0 else 0.0,
            'orders_per_hr':       round(h.orders_delivered / shift_h, 2) if shift_h > 0 else 0.0,
            'dist_km':             round(h.dist_traveled, 2),
            'dist_per_hr_km':      round(h.dist_traveled / shift_h, 2) if shift_h > 0 else 0.0,
        })
    return rows


def delivery_detail_table(delivery_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(ev) for ev in delivery_log]


def cancellation_table(cancellation_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(ev) for ev in cancellation_log]


def rejection_table(rejection_log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(ev) for ev in rejection_log]


def snapshot_table(state_snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(ev) for ev in state_snapshots]
