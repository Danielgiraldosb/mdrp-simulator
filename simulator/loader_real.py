"""
Loader for the 24 real Colombian instances in real_instancies/Instancia_k/
(couriers.csv, orders.csv, stores.csv), producing the SAME dict that
loader.load_instance() builds for mdrplib -- so every policy, the SimPy
engine and metrics.py run unchanged on both datasets.

The folders were labelled "Bogota" in the thesis material, but the
coordinates place them in several cities (Bogota, Pereira, Bucaramanga,
Barranquilla, ...). This loader therefore centres everything on the
instance itself: the projection origin is the median store location and
rows farther than cfg.real_max_radius_km from it are dropped. meta['city']
names the nearest known city for reporting.

File formats (all times are wall-clock 'H:MM:SS' of one operating day)
----------------------------------------------------------------------
couriers.csv  courier_id, vehicle, on_lat, on_lng, on_time, off_time
orders.csv    order_id, store_id, drop_off_lat, drop_off_lng, placement_time,
              preparation_time, ready_time, expected_drop_off_time
stores.csv    store_id, pick_up_lat, pick_up_lng

What this loader decides (every item is a Config field, see config.py)
----------------------------------------------------------------------
* Coordinates: lat/lng -> planar meters by an equirectangular projection
  around the instance centre (error < 0.1 % over a 40 km box), times
  cfg.real_circuity. distance.py's Euclidean formula then applies as is:
  circuity 1.0 reproduces haversine, ~1.3 approximates street distance.
* Speed: per courier from cfg.real_speeds_kmh[vehicle] (Courier.speed_m_per_min);
  cfg.meters_per_minute is set to the fleet mean only for display.
* SLA: soft = expected_drop_off_time - placement_time (per order, from the
  data); hard = soft + cfg.real_max_ctd_extra_min.
* Economics (COP): flat pay cfg.real_pay_per_order_cop per order; no
  guaranteed hourly true-up (the platform has none -> guaranteed_pay_per_hour
  = 0); cfg.min_wage_hourly = SMMLV/hour for the F_Deficit metric.
* Service times and decision window from the Bogota survey/interviews
  (config.py). For non-Bogota instances this is a transfer assumption.
* Rows farther than cfg.real_max_radius_km from the centre are dropped and
  counted in meta['dropped'].
"""
from __future__ import annotations

import math
import os
import random
import re
import statistics
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import Config
from models import Courier, Location, Order

EARTH_RADIUS_M = 6_371_000.0
_INST = re.compile(r'^Instancia_(\d+)$')

# Reference centres (lat, lng) used only to label meta['city'].
CITIES: Dict[str, Tuple[float, float]] = {
    'Bogota': (4.65, -74.10), 'Medellin': (6.25, -75.57), 'Cali': (3.45, -76.53),
    'Barranquilla': (10.96, -74.80), 'Cartagena': (10.40, -75.50), 'Bucaramanga': (7.12, -73.12),
    'Pereira': (4.81, -75.69), 'Manizales': (5.07, -75.52), 'Cucuta': (7.89, -72.50),
    'Ibague': (4.44, -75.23), 'Santa Marta': (11.24, -74.20), 'Villavicencio': (4.15, -73.63),
    'Armenia': (4.53, -75.68), 'Monteria': (8.75, -75.88), 'Pasto': (1.21, -77.28),
    'Neiva': (2.93, -75.28), 'Valledupar': (10.47, -73.25),
}


# -- Helpers ---------------------------------------------------------------------

def hms_to_min(s: str) -> float:
    """'H:MM:SS' (or 'H:MM') -> minutes from midnight."""
    parts = str(s).strip().split(':')
    h, m = int(parts[0]), int(parts[1])
    sec = float(parts[2]) if len(parts) > 2 else 0.0
    return h * 60.0 + m + sec / 60.0


def project(lat: float, lng: float, center: Tuple[float, float],
            circuity: float = 1.0) -> Location:
    """Equirectangular projection to planar meters around `center` (lat, lng)."""
    lat0, lng0 = center
    x = math.radians(lng - lng0) * math.cos(math.radians(lat0)) * EARTH_RADIUS_M
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return Location(x=x * circuity, y=y * circuity)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def nearest_city(lat: float, lng: float, max_km: float = 60.0) -> str:
    name, d = min(((n, haversine_m(lat, lng, *xy)) for n, xy in CITIES.items()), key=lambda t: t[1])
    return name if d <= max_km * 1000 else 'unknown'


def speed_m_per_min(vehicle: str, cfg: Config) -> float:
    kmh = cfg.real_speeds_kmh.get(str(vehicle).strip().lower())
    if kmh is None:
        raise ValueError(f"No speed configured for vehicle '{vehicle}'. "
                         f"Known: {sorted(cfg.real_speeds_kmh)} (use --speeds VEH=KMH)")
    return kmh * 1000.0 / 60.0


def parse_speeds(items: List[str]) -> Dict[str, float]:
    """['bicycle=15', 'motorcycle=25'] -> {'bicycle': 15.0, 'motorcycle': 25.0}"""
    out: Dict[str, float] = {}
    for it in items:
        if '=' not in it:
            raise ValueError(f"--speeds expects VEH=KMH, got '{it}'")
        k, v = it.split('=', 1)
        out[k.strip().lower()] = float(v)
    return out


def _id_int(s: str, prefix: str) -> int:
    s = str(s).strip()
    return int(s[len(prefix):]) if s.startswith(prefix) else int(s)


# -- Discovery -----------------------------------------------------------------

def is_real_instance(name: str, instances_dir: str) -> bool:
    return os.path.isfile(os.path.join(instances_dir, name, 'couriers.csv'))


def is_real_dir(instances_dir: str) -> bool:
    if not os.path.isdir(instances_dir):
        return False
    return any(is_real_instance(n, instances_dir) for n in os.listdir(instances_dir))


def list_real_instances(instances_dir: str) -> List[str]:
    names = [n for n in os.listdir(instances_dir) if is_real_instance(n, instances_dir)]

    def key(n: str):
        m = _INST.match(n)
        return (0, int(m.group(1))) if m else (1, n)
    return sorted(names, key=key)


# -- Loader ----------------------------------------------------------------------

def load_real_instance(name: str, instances_dir: str, cfg: Config,
                       center: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
    """
    Load real_instancies/<name>/ into {'stores', 'orders', 'couriers',
    'config', 'meta'}. cfg is mutated in place like loader.load_instance():
    speed (display), service times, pay, wage reference, decision window.
    `center` overrides the data-driven (median store) projection origin.
    """
    base = os.path.join(instances_dir, name)
    for f in ('couriers.csv', 'orders.csv', 'stores.csv'):
        if not os.path.isfile(os.path.join(base, f)):
            raise FileNotFoundError(f"Real instance file not found: {os.path.join(base, f)}")

    t0 = cfg.sim_start_clock_min
    t1 = t0 + cfg.sim_end
    k = cfg.real_circuity
    r_max = cfg.real_max_radius_km * 1000.0
    dropped = {'couriers_far': 0, 'stores_far': 0, 'orders_far': 0,
               'orders_no_store': 0, 'orders_window': 0, 'couriers_window': 0}

    # -- Stores and centre ---------------------------------------------------------
    st_df = pd.read_csv(os.path.join(base, 'stores.csv'))
    if center is None:
        center = (float(statistics.median(st_df['pick_up_lat'])),
                  float(statistics.median(st_df['pick_up_lng'])))

    def near(lat: float, lng: float) -> bool:
        return haversine_m(lat, lng, center[0], center[1]) <= r_max

    stores_map: Dict[str, Location] = {}
    for row in st_df.itertuples(index=False):
        if not near(row.pick_up_lat, row.pick_up_lng):
            dropped['stores_far'] += 1
            continue
        stores_map[str(row.store_id)] = project(row.pick_up_lat, row.pick_up_lng, center, k)

    # -- Orders ------------------------------------------------------------------
    o_df = pd.read_csv(os.path.join(base, 'orders.csv'))
    orders: List[Order] = []
    for row in o_df.itertuples(index=False):
        placement = hms_to_min(row.placement_time)
        if placement < t0 or placement >= t1:
            dropped['orders_window'] += 1
            continue
        store_loc = stores_map.get(str(row.store_id))
        if store_loc is None:
            dropped['orders_no_store'] += 1
            continue
        if not near(row.drop_off_lat, row.drop_off_lng):
            dropped['orders_far'] += 1
            continue
        ready = hms_to_min(row.ready_time)
        expected = hms_to_min(row.expected_drop_off_time)
        target = max(1.0, expected - placement)
        orders.append(Order(
            order_id=_id_int(row.order_id, 'o'),
            placement_time=placement - t0,
            store_loc=store_loc,
            user_loc=project(row.drop_off_lat, row.drop_off_lng, center, k),
            ready_time=max(ready, placement) - t0,
            target_click_to_door=target,
            max_click_to_door=target + cfg.real_max_ctd_extra_min,
        ))

    # -- Couriers ------------------------------------------------------------------
    c_df = pd.read_csv(os.path.join(base, 'couriers.csv'))
    rng = random.Random(cfg.seed)
    couriers: List[Courier] = []
    veh_counts: Dict[str, int] = {}
    for row in c_df.itertuples(index=False):
        if not near(row.on_lat, row.on_lng):
            dropped['couriers_far'] += 1
            continue
        on_t, off_t = hms_to_min(row.on_time), hms_to_min(row.off_time)
        if off_t <= t0 or on_t >= t1:
            dropped['couriers_window'] += 1
            continue
        on_rel = max(0.0, on_t - t0)
        off_rel = min(cfg.sim_end, off_t - t0)
        if off_rel <= on_rel:
            dropped['couriers_window'] += 1
            continue
        veh = str(row.vehicle).strip().lower()
        veh_counts[veh] = veh_counts.get(veh, 0) + 1
        couriers.append(Courier(
            courier_id=_id_int(row.courier_id, 'c'),
            on_time=on_rel,
            off_time=off_rel,
            home_loc=project(row.on_lat, row.on_lng, center, k),
            acceptance_rate=rng.uniform(cfg.min_acceptance_rate, cfg.max_acceptance_rate),
            vehicle=veh,
            speed_m_per_min=speed_m_per_min(veh, cfg),
        ))

    # -- Config written back (same contract as loader.load_instance) --------------
    if couriers:
        cfg.meters_per_minute = sum(c.speed_m_per_min for c in couriers) / len(couriers)
    cfg.pickup_service_min = cfg.real_pickup_service_min
    cfg.dropoff_service_min = cfg.real_dropoff_service_min
    cfg.pay_per_order = cfg.real_pay_per_order_cop
    cfg.guaranteed_pay_per_hour = 0.0
    if cfg.min_wage_hourly is None:
        cfg.min_wage_hourly = cfg.real_min_wage_cop_per_hour
    cfg.decision_mean_min = cfg.real_decision_mean_min
    cfg.decision_std_min = cfg.real_decision_std_min
    if orders:
        cfg.target_click_to_door = sum(o.target_click_to_door for o in orders) / len(orders)
        cfg.max_click_to_door = cfg.target_click_to_door + cfg.real_max_ctd_extra_min

    city = nearest_city(*center)
    stores = list(stores_map.values())
    print(f"  Real '{name}' ({city}): {len(orders):,} orders . {len(couriers):,} couriers . "
          f"{len(stores):,} stores  [fleet mean speed={cfg.meters_per_minute:.0f} m/min, "
          f"circuity={k}, dropped={sum(dropped.values())}]")

    return {'stores': stores, 'orders': orders, 'couriers': couriers, 'config': cfg,
            'meta': {'dropped': dropped, 'vehicles': veh_counts, 'source': 'real',
                     'name': name, 'city': city, 'center': center}}
