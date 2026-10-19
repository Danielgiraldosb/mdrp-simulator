"""
Runs the 4 mdrp-sim-ported policies across all 240 mdrplib instances, same
config as the rest of this project's batches (seed=42, bundle=3,
acceptance=auto, full day, solver NEVER time-limited) -- for comparison
against our own ilp_max_coverage results already in
resultados/ilp_all_objectives_240.csv (not re-run here; same config, so
directly comparable).

mdrpsim_mip and mdrpsim_graph are mdrp-sim's own "no candidate filter"
formulations (full cross-product of idle couriers x candidate routes every
dispatch round) -- deliberately NOT capped to a nearest-K subset the way our
own ILPPolicy is, to stay faithful to the original and show their true cost
at this benchmark's scale, however long that takes.

Resumable: each (instance, policy) result is cached to its own JSON file
under --out-dir immediately after it finishes, and skipped on a later run if
already present -- an interrupted batch loses no completed work.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from batch_sensitivity import run_one, DEFAULT_INSTANCES_DIR
from loader import list_instances

POLICIES = ['mdrpsim_greedy', 'mdrpsim_mip', 'mdrpsim_graph', 'mdrpsim_graph_prospects']


def _job_path(out_dir: str, instance: str, policy: str) -> str:
    return os.path.join(out_dir, f"{instance}__{policy}.json")


def _worker(instance: str, policy: str, out_path: str):
    t0 = time.time()
    m = run_one(instance, DEFAULT_INSTANCES_DIR, policy,
               objective='max_coverage', acceptance_mode='auto', seed=42, bundle=3)
    wall = time.time() - t0
    m['policy_label'] = policy
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(m, f, default=str)
    return instance, policy, m['coverage_rate'], m['wall_clock_sec'], m['solve_max'], wall


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', type=str, default='resultados/mdrpsim_240')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--policies', type=str, nargs='+', default=POLICIES)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    instances = list_instances(DEFAULT_INSTANCES_DIR)

    jobs = []
    cached = 0
    for inst in instances:
        for pol in args.policies:
            out_path = _job_path(args.out_dir, inst, pol)
            if os.path.exists(out_path):
                cached += 1
                continue
            jobs.append((inst, pol, out_path))

    total = cached + len(jobs)
    print(f"{total} total (instance,policy) pairs -- {cached} cached, {len(jobs)} to run, "
         f"workers={args.workers}")

    done = cached
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_worker, inst, pol, path): (inst, pol) for inst, pol, path in jobs}
        for fut in as_completed(futs):
            inst, pol = futs[fut]
            done += 1
            try:
                _, _, cov, wc, sm, wall = fut.result()
                print(f"[{done}/{total}] {inst:>16} . {pol:<24} -> "
                     f"coverage={cov:.3f}  wall_clock={wc:.2f}s  solve_max={sm:.3f}s  "
                     f"(outer {wall:.1f}s)")
            except Exception as exc:
                print(f"[{done}/{total}] {inst:>16} . {pol:<24} FAILED: {exc}")

    print(f"\nDone. {total} result files in {args.out_dir}")
