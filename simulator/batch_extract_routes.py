"""
Extracts route/solution data (for the dashboard's map + Gantt views) across
all 240 mdrplib instances for the 6 policies that don't yet have any route
data: our own greedy/fair_greedy, plus the 4 mdrp-sim ports. The existing
'ilp_<objective>' route data (route_data/*.json, 240 at max_coverage + 4 more
for the single representative instance 2o100t75s1p100) is untouched.

Same config as every other batch in this project (seed=42, bundle=3,
acceptance=auto, solver never time-limited for the mip/graph policies).
Resumable: each (instance, policy) result is cached to its own JSON file
under --out-dir and skipped on a later run if already present.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from extract_routes import extract_one, safe_id
from loader import list_instances
from run import DEFAULT_INSTANCES_DIR

POLICIES = ['greedy', 'fair_greedy', 'mdrpsim_greedy', 'mdrpsim_mip',
           'mdrpsim_graph', 'mdrpsim_graph_prospects']


def _worker(inst: str, instances_dir: str, policy: str, seed: int, bundle: int, out_path: str):
    t0 = time.time()
    rec = extract_one(inst, instances_dir, policy, objective='max_coverage', seed=seed, bundle=bundle)
    wall = time.time() - t0
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, separators=(',', ':'))
    size_kb = os.path.getsize(out_path) / 1024
    return inst, policy, rec['n_delivered'], rec['n_routes'], rec['wall_clock_sec'], wall, size_kb


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', type=str, default='route_data')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--policies', type=str, nargs='+', default=POLICIES)
    parser.add_argument('--instances', type=str, nargs='*', default=None)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    instances = args.instances or list_instances(DEFAULT_INSTANCES_DIR)

    jobs = []
    cached = 0
    for inst in instances:
        for pol in args.policies:
            out_path = os.path.join(args.out_dir, safe_id(inst, pol) + '.json')
            if os.path.exists(out_path):
                cached += 1
                continue
            jobs.append((inst, pol, out_path))

    total = cached + len(jobs)
    print(f"{total} total (instance,policy) pairs -- {cached} cached, {len(jobs)} to run, "
         f"workers={args.workers}")

    done = cached
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_worker, inst, DEFAULT_INSTANCES_DIR, pol, 42, 3, path): (inst, pol)
               for inst, pol, path in jobs}
        for fut in as_completed(futs):
            inst, pol = futs[fut]
            done += 1
            try:
                _, _, n_delivered, n_routes, sim_wc, wall, size_kb = fut.result()
                print(f"[{done}/{total}] {inst:>16} . {pol:<24} -> "
                     f"{n_delivered:,} delivered . {n_routes:,} routes . "
                     f"sim={sim_wc:.2f}s (outer {wall:.1f}s) . {size_kb:.1f} KB")
            except Exception as exc:
                print(f"[{done}/{total}] {inst:>16} . {pol:<24} FAILED: {exc}")

    print(f"\nDone. {total} result files in {args.out_dir}")
