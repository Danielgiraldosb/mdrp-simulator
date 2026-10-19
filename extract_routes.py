"""
Extract per-instance route/solution data (restaurant and drop-off coordinates,
plus each courier's actual sequence of stops) for the route-map visualization
in the results dashboard.

This does NOT change any metric: it runs the exact same (instance, objective)
simulation as batch_sensitivity.run_one() (same seed=42, bundle=3,
acceptance_mode='auto', no ILP time limit) and additionally mines
sim.get_results()['delivery_log'] -- which already carries store/user (x, y)
and pickup/delivery timestamps per delivered order (simulator.py's
CourierActor._execute_route) -- into compact per-courier route polylines.

Output: one small JSON file per (instance, objective) under --out-dir, named
"<instance>__<objective>.json".
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, List

import simpy

from config import Config
from loader import load_instance, list_instances
from run import build_policy, DEFAULT_INSTANCES_DIR
from simulator import MDRPSimulator


def extract_one(instance_name: str, instances_dir: str, policy_name: str = 'ilp',
                objective: str = 'max_coverage',
                seed: int = 42, bundle: int = 3) -> Dict[str, Any]:
    cfg = Config(seed=seed, objective=objective, max_bundle_size=bundle, acceptance_mode='auto')
    instance = load_instance(instance_name, instances_dir, cfg)
    policy = build_policy(policy_name, cfg)

    env = simpy.Environment()
    sim = MDRPSimulator(env, instance, policy, cfg)
    sim.start()

    t0 = time.perf_counter()
    env.run(until=cfg.sim_end)
    wall_clock_sec = time.perf_counter() - t0

    log = sim.get_results()['delivery_log']

    # Group delivered orders into the bundle/trip they were actually picked up
    # in together: same courier + same pickup_time_min -> one store visit,
    # dropoffs ordered by delivery_time_min (the route's visiting sequence).
    trips: Dict[tuple, List[dict]] = {}
    for row in log:
        key = (row['courier_id'], row['pickup_time_min'])
        trips.setdefault(key, []).append(row)

    routes = []
    restaurants = {}
    for (courier_id, pickup_t), rows in trips.items():
        rows.sort(key=lambda r: r['delivery_time_min'])
        sx, sy = rows[0]['store_x'], rows[0]['store_y']
        restaurants[(sx, sy)] = True
        routes.append({
            'courier_id': courier_id,
            'pickup_time_min': pickup_t,
            'store': [sx, sy],
            'stops': [
                {
                    'order_id': r['order_id'],
                    'x': r['user_x'], 'y': r['user_y'],
                    'delivery_time_min': r['delivery_time_min'],
                    'overage_min': r['overage_min'],
                    'c2d_min': r['c2d_min'],
                }
                for r in rows
            ],
        })

    xs = [r['store_x'] for r in log] + [r['user_x'] for r in log]
    ys = [r['store_y'] for r in log] + [r['user_y'] for r in log]
    bbox = [min(xs), min(ys), max(xs), max(ys)] if log else [0, 0, 0, 0]

    model_id = ('ilp_' + objective) if policy_name == 'ilp' else policy_name
    return {
        'instance': instance_name,
        'objective': objective if policy_name == 'ilp' else None,
        'model': model_id,
        'n_orders': len(instance['orders']),
        'n_delivered': len(log),
        'n_couriers_active': len(set(r['courier_id'] for r in log)),
        'n_routes': len(routes),
        'bbox': bbox,
        'restaurants': [[x, y] for (x, y) in restaurants.keys()],
        'routes': routes,
        'wall_clock_sec': round(wall_clock_sec, 3),
    }


def safe_id(instance_name: str, tag: str) -> str:
    return f"{instance_name}__{tag}"


def _worker(inst: str, instances_dir: str, policy_name: str, obj: str, seed: int, bundle: int, out_path: str):
    rec = extract_one(inst, instances_dir, policy_name, obj, seed=seed, bundle=bundle)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, separators=(',', ':'))
    return inst, rec['model'], rec['n_orders'], rec['n_delivered'], rec['n_routes'], rec['wall_clock_sec'], os.path.getsize(out_path) / 1024


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract route/solution data for the dashboard map')
    parser.add_argument('--instances-dir', type=str, default=DEFAULT_INSTANCES_DIR)
    parser.add_argument('--instances', type=str, nargs='*', default=None,
                        help='Specific instance names; default: all in instances-dir')
    parser.add_argument('--policy', type=str, default='ilp',
                        help="ilp | greedy | fair_greedy | mdrpsim_greedy | mdrpsim_mip | "
                             "mdrpsim_graph | mdrpsim_graph_prospects")
    parser.add_argument('--objectives', type=str, nargs='+', default=['max_coverage'],
                        help='Only used when --policy ilp; one route file per objective')
    parser.add_argument('--out-dir', type=str, default='route_data')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--bundle', type=int, default=3)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    instances = args.instances or list_instances(args.instances_dir)
    tags = args.objectives if args.policy == 'ilp' else [args.policy]

    jobs = []
    manifest = []
    for inst in instances:
        for tag in tags:
            obj = tag if args.policy == 'ilp' else 'max_coverage'
            out_path = os.path.join(args.out_dir, safe_id(inst, tag) + '.json')
            if os.path.exists(out_path):
                with open(out_path, encoding='utf-8') as f:
                    rec = json.load(f)
                manifest.append({'instance': inst, 'model': rec.get('model', tag),
                                 'n_orders': rec['n_orders'], 'n_routes': rec['n_routes'],
                                 'file': os.path.basename(out_path)})
                continue
            jobs.append((inst, tag, obj, out_path))

    total = len(manifest) + len(jobs)
    print(f"{len(manifest)} cached, {len(jobs)} to run, workers={args.workers}")
    done = len(manifest)

    if args.workers <= 1:
        for inst, tag, obj, out_path in jobs:
            done += 1
            print(f"[{done}/{total}] {inst} . {tag}")
            try:
                _, model_id, n_orders, n_delivered, n_routes, wc, size_kb = _worker(
                    inst, args.instances_dir, args.policy, obj, args.seed, args.bundle, out_path)
            except Exception as exc:
                print(f"    FAILED: {exc}")
                continue
            print(f"    {n_delivered:,} delivered . {n_routes:,} routes . {wc:.2f}s . {size_kb:.1f} KB")
            manifest.append({'instance': inst, 'model': model_id, 'n_orders': n_orders,
                             'n_routes': n_routes, 'file': os.path.basename(out_path)})
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(_worker, inst, args.instances_dir, args.policy, obj, args.seed, args.bundle, out_path): (inst, tag)
                   for inst, tag, obj, out_path in jobs}
            for fut in as_completed(futs):
                inst, tag = futs[fut]
                done += 1
                try:
                    _, model_id, n_orders, n_delivered, n_routes, wc, size_kb = fut.result()
                except Exception as exc:
                    print(f"[{done}/{total}] {inst} . {tag}  FAILED: {exc}")
                    continue
                print(f"[{done}/{total}] {inst} . {tag}  ->  {n_delivered:,} delivered . "
                     f"{n_routes:,} routes . {wc:.2f}s . {size_kb:.1f} KB")
                manifest.append({'instance': inst, 'model': model_id, 'n_orders': n_orders,
                                 'n_routes': n_routes, 'file': safe_id(inst, tag) + '.json'})

    with open(os.path.join(args.out_dir, '_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(manifest)} route files + manifest to {args.out_dir}")
