"""
Runs our own 'greedy' and 'fair_greedy' policies across all 240 mdrplib
instances, same config as every other batch in this project (seed=42,
bundle=3, acceptance=auto, full day) -- so the dashboard can show all 7 of
our own policies (not just the 5 ILP objectives) alongside the 4 mdrp-sim
ports, on equal footing. Resumable, same caching pattern as batch_mdrpsim.py.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from batch_sensitivity import run_one, DEFAULT_INSTANCES_DIR
from loader import list_instances

POLICIES = ['greedy', 'fair_greedy']
OUT_DIR = 'resultados/greedy_fair_240'


def _job_path(instance: str, policy: str) -> str:
    return os.path.join(OUT_DIR, f"{instance}__{policy}.json")


def _worker(instance: str, policy: str, out_path: str):
    t0 = time.time()
    m = run_one(instance, DEFAULT_INSTANCES_DIR, policy,
               acceptance_mode='auto', seed=42, bundle=3)
    wall = time.time() - t0
    m['policy_label'] = policy
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(m, f, default=str)
    return instance, policy, m['coverage_rate'], m['wall_clock_sec'], wall


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    instances = list_instances(DEFAULT_INSTANCES_DIR)

    jobs = []
    cached = 0
    for inst in instances:
        for pol in POLICIES:
            out_path = _job_path(inst, pol)
            if os.path.exists(out_path):
                cached += 1
                continue
            jobs.append((inst, pol, out_path))

    total = cached + len(jobs)
    print(f"{total} total -- {cached} cached, {len(jobs)} to run")

    done = cached
    with ProcessPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_worker, inst, pol, path): (inst, pol) for inst, pol, path in jobs}
        for fut in as_completed(futs):
            inst, pol = futs[fut]
            done += 1
            try:
                _, _, cov, wc, wall = fut.result()
                print(f"[{done}/{total}] {inst:>16} . {pol:<12} -> coverage={cov:.3f}  wall_clock={wc:.2f}s")
            except Exception as exc:
                print(f"[{done}/{total}] {inst:>16} . {pol:<12} FAILED: {exc}")

    print(f"\nDone. {total} result files in {OUT_DIR}")
