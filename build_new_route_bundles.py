"""
Flattens the newly-extracted route data (route_data/<instance>__<policy>.json
for the 6 policies in batch_extract_routes.py's POLICIES, 240 instances each)
into one-row-per-delivery-stop records -- same flat schema the dashboard's
route map/Gantt already consume for the 244 ILP combos in bundles_flat2 --
and bin-packs them into new ~7 MB bundle files that sit ALONGSIDE (not
replacing) the existing route_bundle_00..09 assets.

Each stop row carries 'model' (e.g. 'greedy', 'mdrpsim_mip') instead of the
old 'objective' field, so the dashboard's buildRouteRecord() can resolve a
row's model id as `r.model || ('ilp_' + r.objective)` and treat old and new
bundles uniformly without re-uploading the untouched old data.

Output: build_new_route_bundles_out/bundle_<NN>.json (NN continuing from 10)
and build_new_route_bundles_out/_new_manifest.json (one row per
instance x model: {instance, model, bundle, n_orders, n_delivered, n_routes,
n_couriers_active, file}), ready to be merged with the existing
route_manifest and uploaded.
"""
from __future__ import annotations

import json
import os

from batch_extract_routes import POLICIES
from loader import list_instances
from run import DEFAULT_INSTANCES_DIR

SRC_DIR = 'route_data'
OUT_DIR = 'build_new_route_bundles_out'
START_BUNDLE_IDX = 10
CAP_BYTES = 7 * 1024 * 1024


def flatten_one(rec: dict) -> list:
    instance, model = rec['instance'], rec['model']
    rows = []
    for route in rec['routes']:
        sx, sy = route['store']
        for s in route['stops']:
            rows.append({
                'instance': instance, 'model': model,
                'courier_id': route['courier_id'], 'pickup_time_min': route['pickup_time_min'],
                'store_x': sx, 'store_y': sy,
                'order_id': s['order_id'], 'x': s['x'], 'y': s['y'],
                'delivery_time_min': s['delivery_time_min'],
                'overage_min': s['overage_min'], 'c2d_min': s['c2d_min'],
            })
    return rows


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    instances = list_instances(DEFAULT_INSTANCES_DIR)

    combos = []  # (instance, model, rows, json_byte_len, n_orders, n_delivered, n_routes, n_couriers_active)
    missing = []
    for inst in instances:
        for pol in POLICIES:
            path = os.path.join(SRC_DIR, f"{inst}__{pol}.json")
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
        for m in missing[:10]:
            print(f"  MISSING: {m}")
        if len(missing) > 10:
            print(f"  ... and {len(missing)-10} more")

    # First-fit-decreasing bin packing by combo byte size.
    combos.sort(key=lambda c: -c[3])
    bins = []  # list of {'size': int, 'combos': [combo,...]}
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
        idx = START_BUNDLE_IDX + i
        bundle_id = f"{idx:02d}"
        fname = f"bundle_{bundle_id}.json"
        all_rows = []
        for (inst, model, rows, size, n_orders, n_delivered, n_routes, n_couriers_active) in b['combos']:
            all_rows.extend(rows)
            manifest.append({'instance': inst, 'model': model, 'bundle': bundle_id,
                             'n_orders': n_orders, 'n_delivered': n_delivered,
                             'n_routes': n_routes, 'n_couriers_active': n_couriers_active,
                             'file': fname})
        out_path = os.path.join(OUT_DIR, fname)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(all_rows, f, separators=(',', ':'))
        actual_kb = os.path.getsize(out_path) / 1024
        print(f"  bundle_{bundle_id}: {len(b['combos'])} combos, {len(all_rows)} rows, {actual_kb:.0f} KB")

    with open(os.path.join(OUT_DIR, '_new_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(manifest)} manifest rows to {OUT_DIR}/_new_manifest.json")
