"""Review level 2 (2026-11-03): supply diagnostic of the 3-km zones against the full city day.

For every instance, loads the day twice with the paper's loader (zone radius 3 km, and 40 km = the whole city)
and reports orders, couriers, connected courier-hours and orders per connected courier-hour. The field reference is
the survey: median 2,622 COP per connected hour at 2,200 COP per order, i.e. about 1.19 orders per hour.

    python diag_supply.py            -> output/paper/supply.csv and a summary on stdout
"""
import os
import sys

import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)

from batch_paper import DEFAULT_INSTANCES_DIR, all_instances, read_instance_table as instance_cities  # noqa: E402
from config import Config  # noqa: E402
from loader_real import load_real_instance  # noqa: E402

FIELD_ORDERS_PER_HOUR = 2622 / 2200


def read(inst: str, radius: float):
    cfg = Config(seed=1, real_max_radius_km=radius, real_circuity=1.3, max_bundle_size=3)
    d = load_real_instance(inst, DEFAULT_INSTANCES_DIR, cfg)
    hours = sum(c.off_time - c.on_time for c in d['couriers']) / 60.0
    return len(d['orders']), len(d['couriers']), hours


def main() -> None:
    cities = instance_cities()
    rows = []
    for inst in all_instances(DEFAULT_INSTANCES_DIR):
        oz, cz, hz = read(inst, 3.0)
        oc, cc, hc = read(inst, 40.0)
        rows.append(dict(instance=inst, city=cities.get(inst, ''), orders_zone=oz, couriers_zone=cz, hours_zone=round(hz, 1),
                         opch_zone=oz / hz if hz else float('nan'), orders_city=oc, couriers_city=cc,
                         hours_city=round(hc, 1), opch_city=oc / hc if hc else float('nan')))
        print(f"{inst:13s} zone {oz:6d} o / {hz:8.0f} h = {oz / hz:.2f}   city {oc:6d} o / {hc:8.0f} h = {oc / hc:.2f}", flush=True)
    df = pd.DataFrame(rows)
    out = os.path.join(THIS_DIR, 'output', 'paper', 'supply.csv')
    df.to_csv(out, index=False)
    z = df.orders_zone.sum() / df.hours_zone.sum()
    c = df.orders_city.sum() / df.hours_city.sum()
    print(f"\npooled orders per connected courier-hour: zone {z:.3f}, city {c:.3f}, field {FIELD_ORDERS_PER_HOUR:.2f}")
    print(f"mean over instances: zone {df.opch_zone.mean():.3f}, city {df.opch_city.mean():.3f}")
    print(f"fleet fraction that would match the field in the zones: {z / FIELD_ORDERS_PER_HOUR:.2f} (pooled), "
          f"{(df.opch_zone / FIELD_ORDERS_PER_HOUR).median():.2f} (median instance)")
    print(df.groupby('city')[['opch_zone', 'opch_city']].mean().round(3).to_string())


if __name__ == '__main__':
    main()
