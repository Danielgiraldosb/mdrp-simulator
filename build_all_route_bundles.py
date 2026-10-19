"""
Flattens ALL route/solution data (route_data_v2/, 1,684 instance x model
combos -- 244 ILP + 1,440 from the other 7 models) into one-row-per-stop
records, now including 'assignment_time_min' (when the dispatcher actually
assigned the order, not just when it was picked up/delivered) so the
dashboard's map can filter by 2-minute dispatch round instead of always
showing the whole day at once.

Supersedes the two-tier bundles_flat2 (old ILP-only) + build_new_route_bundles
(the 7 other models) split from before this field existed: everything is
re-extracted into route_data_v2 with the new field, so this script rebuilds
the COMPLETE bundle set and manifest from scratch in one pass.

Output: build_all_route_bundles_out/bundle_<NN>.json and _manifest.json
(one row per instance x model: {instance, model, bundle, n_orders,
n_delivered, n_routes, n_couriers_active}).
"""
from __future__ import annotations

import json
import os

from batch_extract_routes import POLICIES as OTHER_POLICIES
from loader import list_instances
from run import DEFAULT_INSTANCES_DIR

SRC_DIR = 'route_data_v2'
OUT_DIR = 'build_all_route_bundles_out'
CAP_BYTES = 7 * 1024 * 1024

ILP_OBJECTIVES = ['max_coverage', 'max_equity', 'max_throughput', 'min_cost', 'min_lateness']
ILP_MULTI_OBJ_INSTANCE = '2o100t75s1p100'


def flatten_one(rec: dict) -> list:
    instance, model = rec['instance'], rec['model']
    rows = []
    for route in rec['routes']:
        sx, sy = route['store']
        for s in route['stops']:
            rows.append({
                'instance': instance, 'model': model,
                'courier_id': route['courier_id'],
                'pickup_time_min': route['pickup_time_min'],
                'assignment_time_min': route.get('assignment_time_min', s.get('assignment_time_min')),
                'store_x': sx, 'store_y': sy,
                'order_id': s['order_id'], 'x': s['x'], 'y': s['y'],
                'delivery_time_min': s['delivery_time_min'],
                'overage_min': s['overage_min'], 'c2d_min': s['c2d_min'],
            })
    return rows


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    instances = list_instances(DEFAULT_INSTANCES_DIR)

    jobs = []  # (instance, tag) where tag is either an ILP objective or a policy name
    for inst in instances:
        jobs.append((inst, 'max_coverage'))
    for obj in ILP_OBJECTIVES:
        if obj == 'max_coverage':
            continue
        jobs.append((ILP_MULTI_OBJ_INSTANCE, obj))
    for inst in instances:
        for pol in OTHER_POLICIES:
            jobs.append((inst, pol))

    combos = []
    missing = []
    for inst, tag in jobs:
        path = os.path.join(SRC_DIR, f"{inst}__{tag}.json")
        if not os.path.exists(path):
            missing.append(path)
            continue
        with open(path, encoding='utf-8') as f:
            rec = json.load(f)
        rows = flatten_one(rec)
        blob = json.dumps(rows, separators=(',', ':'))
        combos.append((inst, rec['model'], rows, len(blob.encode('utf-8')),
                      rec['n_orders'], rec['n_delivered'], rec['n_routes'], rec['n_couriers_active']))

    print(f"{len(combos)} (instance,model) combos found, {len(missing)} missing")
    if missing:
        for m in missing[:20]:
            print(f"  MISSING: {m}")
        if len(missing) > 20:
            print(f"  ... and {len(missing)-20} more")

    combos.sort(key=lambda c: -c[3])
    bins = []
    for combo in combos:
        placed = False
        for b in bins:
            if b['size'] + combo[3] <= CAP_BYTES:
                b['combos'].append(combo)
                b['size'] += combo[3]
                placed = True
                break
        if not placed:
            bins.append({'size': combo[3], 'combos': [combo]})

    print(f"\nPacked into {len(bins)} bundles (cap {CAP_BYTES/1024/1024:.1f} MB)")

    manifest = []
    for i, b in enumerate(bins):
        bundle_id = f"{i:02d}"
        fname = f"bundle_{bundle_id}.json"
        all_rows = []
        for (inst, model, rows, size, n_orders, n_delivered, n_routes, n_couriers_active) in b['combos']:
            all_rows.extend(rows)
            manifest.append({'instance': inst, 'model': model, 'bundle': bundle_id,
                             'n_orders': n_orders, 'n_delivered': n_delivered,
                             'n_routes': n_routes, 'n_couriers_active': n_couriers_active})
        out_path = os.path.join(OUT_DIR, fname)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(all_rows, f, separators=(',', ':'))
        actual_kb = os.path.getsize(out_path) / 1024
        print(f"  bundle_{bundle_id}: {len(b['combos'])} combos, {len(all_rows)} rows, {actual_kb:.0f} KB")

    with open(os.path.join(OUT_DIR, '_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(manifest)} manifest rows to {OUT_DIR}/_manifest.json ({len(bins)} bundles)")
