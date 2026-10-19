"""
Head-to-head comparison: our 3 representative policies (greedy, fair_greedy,
ilp/max_coverage) vs. the 4 mdrp-sim-master ports (mdrpsim_greedy,
mdrpsim_mip, mdrpsim_graph, mdrpsim_graph_prospects), on the SAME instances,
SAME seed/bundle/acceptance config, run through the SAME run_one()/metrics
pipeline as the rest of this project's sensitivity batches.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from batch_sensitivity import run_one, DEFAULT_INSTANCES_DIR

INSTANCES = [
    '2o100t75s1p100',
    '0o100t100s1p100',
    '0o50t100s1p100',
    '0o50t75s1p100',
    '0r50t100s1p100',
    '0r50t75s1p100',
]

POLICIES = [
    'greedy', 'fair_greedy', 'ilp',
    'mdrpsim_greedy', 'mdrpsim_mip', 'mdrpsim_graph', 'mdrpsim_graph_prospects',
]


def _worker(instance: str, policy_name: str):
    t0 = time.time()
    m = run_one(instance, DEFAULT_INSTANCES_DIR, policy_name,
               objective='max_coverage', acceptance_mode='auto', seed=42, bundle=3)
    wall = time.time() - t0
    m['policy_label'] = 'ilp_max_coverage' if policy_name == 'ilp' else policy_name
    m['outer_wall_sec'] = round(wall, 3)
    return m


if __name__ == '__main__':
    jobs = [(inst, p) for inst in INSTANCES for p in POLICIES]
    results = []
    print(f"{len(jobs)} runs: {len(INSTANCES)} instances x {len(POLICIES)} policies")

    with ProcessPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(_worker, inst, p): (inst, p) for inst, p in jobs}
        done = 0
        for fut in as_completed(futs):
            inst, p = futs[fut]
            done += 1
            try:
                m = fut.result()
                print(f"[{done}/{len(jobs)}] {inst:>16} . {p:<24} -> "
                     f"coverage={m['coverage_rate']:.3f}  wall={m['wall_clock_sec']:.2f}s  "
                     f"solve_max={m['solve_max']:.3f}s")
                results.append(m)
            except Exception as exc:
                print(f"[{done}/{len(jobs)}] {inst:>16} . {p:<24} FAILED: {exc}")

    out_path = 'mdrpsim_compare.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, default=str, indent=2)
    print(f"\nWrote {len(results)} rows to {out_path}")
