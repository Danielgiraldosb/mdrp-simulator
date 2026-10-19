"""
Loader for grubhub/mdrplib instances -- native format, no unit conversion.

Format (tab-separated .txt files, time in MINUTES, coordinates in METERS):
  orders.txt      : order  x  y  placement_time  restaurant  ready_time
  couriers.txt    : courier  x  y  on_time  off_time
  restaurants.txt : restaurant  x  y
  instance_parameters.txt: meters_per_minute  pickup service minutes
                            dropoff service minutes  target click-to-door
                            maximum click-to-door  pay per order
                            guaranteed pay per hour

The 240 instances are named by seed + 4 design factors, e.g.:
  0o100t100s1p100   seed=0, full scale,      original speed, hist. shifts, orig. prep
  3o50t75s2p125     seed=3, 50% orders,      -25% travel time, opt. shifts, +25% prep
  9r50t100s1p100    seed=9, 50% restaurants, original speed, hist. shifts, orig. prep

This loader keeps coordinates in their native (x, y) meters and keeps the
clock in native minutes -- no projection to lat/lon, no seconds conversion.
That is what lets travel time respect each instance's own meters_per_minute
(see distance.py), which is the parameter the 't100'/'t75' factor varies.
"""
from __future__ import annotations

import os
import random
import re
from typing import Dict, Any, List

import pandas as pd

from config import Config
from models import Order, Courier, Location


def load_instance(name: str, instances_dir: str, cfg: Config) -> Dict[str, Any]:
    """
    Load one mdrplib instance by folder name (e.g. '0o100t100s1p100').

    Parameters
    ----------
    name          : folder name inside instances_dir
    instances_dir : path to the mdrplib public_instances/ folder
    cfg           : Config -- sim_start_clock_min/sim_end select the time
                    window to load; the instance's own economic and speed
                    parameters are written back into cfg (mutated in place)

    Returns
    -------
    dict with keys 'stores', 'orders', 'couriers', 'config'
    """
    base = os.path.join(instances_dir, name)
    if not os.path.isdir(base):
        raise FileNotFoundError(f"mdrplib instance folder not found: {base}")

    # -- Instance parameters --------------------------------------------------
    params = pd.read_table(os.path.join(base, 'instance_parameters.txt'))
    cfg.meters_per_minute       = float(params.at[0, 'meters_per_minute'])
    cfg.pickup_service_min      = float(params.at[0, 'pickup service minutes'])
    cfg.dropoff_service_min     = float(params.at[0, 'dropoff service minutes'])
    cfg.target_click_to_door    = float(params.at[0, 'target click-to-door'])
    cfg.max_click_to_door       = float(params.at[0, 'maximum click-to-door'])
    cfg.pay_per_order           = float(params.at[0, 'pay per order'])
    cfg.guaranteed_pay_per_hour = float(params.at[0, 'guaranteed pay per hour'])

    t0 = cfg.sim_start_clock_min
    t1 = t0 + cfg.sim_end

    # -- Restaurants (stores) --------------------------------------------------
    rest_df = pd.read_table(os.path.join(base, 'restaurants.txt')).set_index('restaurant')
    stores_map: Dict[str, Location] = {
        rid: Location(x=float(row['x']), y=float(row['y']))
        for rid, row in rest_df.iterrows()
    }

    # -- Orders ------------------------------------------------------------------
    ord_df = pd.read_table(os.path.join(base, 'orders.txt'))
    orders: List[Order] = []
    for _, row in ord_df.iterrows():
        placement = float(row['placement_time'])
        if placement < t0 or placement >= t1:
            continue
        store_loc = stores_map.get(str(row['restaurant']))
        if store_loc is None:
            continue
        orders.append(Order(
            order_id=int(str(row['order']).lstrip('o')),
            placement_time=placement - t0,
            store_loc=store_loc,
            user_loc=Location(x=float(row['x']), y=float(row['y'])),
            ready_time=float(row['ready_time']) - t0,
            target_click_to_door=cfg.target_click_to_door,
            max_click_to_door=cfg.max_click_to_door,
        ))

    # -- Couriers ------------------------------------------------------------------
    cur_df = pd.read_table(os.path.join(base, 'couriers.txt'))
    rng = random.Random(cfg.seed)
    couriers: List[Courier] = []
    for _, row in cur_df.iterrows():
        on_t, off_t = float(row['on_time']), float(row['off_time'])
        if off_t <= t0 or on_t >= t1:
            continue
        on_rel = max(0.0, on_t - t0)
        off_rel = min(cfg.sim_end, off_t - t0)
        if off_rel <= on_rel:
            continue
        couriers.append(Courier(
            courier_id=int(str(row['courier']).lstrip('c')),
            on_time=on_rel,
            off_time=off_rel,
            home_loc=Location(x=float(row['x']), y=float(row['y'])),
            acceptance_rate=rng.uniform(cfg.min_acceptance_rate, cfg.max_acceptance_rate),
        ))

    stores = list(stores_map.values())
    print(f"  mdrplib '{name}': {len(orders):,} orders . {len(couriers):,} couriers . "
          f"{len(stores):,} restaurants  [speed={cfg.meters_per_minute:.0f} m/min]")

    return {'stores': stores, 'orders': orders, 'couriers': couriers, 'config': cfg}


def list_instances(instances_dir: str) -> List[str]:
    """Return sorted list of mdrplib instance names found in instances_dir."""
    return sorted(
        n for n in os.listdir(instances_dir)
        if os.path.isdir(os.path.join(instances_dir, n))
    )


# -- Factorial-design helpers (for sensitivity analysis) ------------------------

_PATTERN = re.compile(
    r'^(?P<seed>\d+)(?P<sizeletter>[or])(?P<size>\d+)t(?P<speed>\d+)s(?P<sched>\d+)p(?P<prep>\d+)$'
)


def parse_instance_name(name: str) -> Dict[str, Any]:
    """
    Decompose an mdrplib instance name into its 5 design factors, e.g.
      '3o50t75s2p125' -> {seed: 3, size: 'o50', speed: 't75',
                          schedule: 's2', prep: 'p125'}
      '9r50t100s1p100' -> {seed: 9, size: 'r50', speed: 't100',
                           schedule: 's1', prep: 'p100'}
    """
    m = _PATTERN.match(name)
    if not m:
        raise ValueError(f"Unrecognized mdrplib instance name: {name}")
    g = m.groupdict()
    return {
        'seed': int(g['seed']),
        'size': f"{g['sizeletter']}{g['size']}",
        'speed': f"t{g['speed']}",
        'schedule': f"s{g['sched']}",
        'prep': f"p{g['prep']}",
    }
