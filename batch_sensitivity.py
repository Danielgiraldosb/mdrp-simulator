"""
Batch runner for a sensitivity analysis across mdrplib's own factorial
design (seed x size x schedule x speed x prep), this simulator's dispatch
policies, and its acceptance criteria.

The 240 public instances already form a controlled experiment: for a fixed
seed, only one factor changes at a time between e.g. '0o100t100s1p100' and
'0o100t75s1p100' (speed only). select_instances() lets you hold every other
factor fixed and sweep just the one you want to study.

Policy (assignment logic) and acceptance mode (whether a notified courier
takes the route) are independent, transversal axes -- any policy can be
crossed with any acceptance mode (see policies.py / acceptance.py).

Examples
--------
  # Full sweep: all seeds, 2 policies, default acceptance (auto) -> 10 x 24 x 2 = 480 runs
  python batch_sensitivity.py --policies greedy fair_greedy --out sensitivity_results.csv

  # Isolate the effect of travel speed only (t100 vs t75), seed 0, o100, s1, p100:
  python batch_sensitivity.py --seeds 0 --sizes o100 --schedules s1 --preps p100 \\
         --speeds t100 t75 --policies greedy --out speed_only.csv

  # ILP under every objective, size factor only:
  python batch_sensitivity.py --seeds 0 1 2 --policies ilp \\
         --objectives max_coverage max_throughput min_lateness max_equity min_cost \\
         --out ilp_objectives.csv

  # Cross every policy with every acceptance mode (auto / fixed@0.7 / logistic):
  python batch_sensitivity.py --seeds 0 --policies greedy fair_greedy ilp \\
         --acceptance-modes auto fixed logistic --acceptance-range 0.7 0.7 \\
         --out acceptance_sweep.csv
"""
from __future__ import annotations

import argparse
import time
from typing import List, Dict, Any, Optional

import simpy
import pandas as pd

from config import Config
from loader import load_instance, list_instances, parse_instance_name
from simulator import MDRPSimulator
from metrics import compute_metrics
from run import build_policy, DEFAULT_INSTANCES_DIR


def select_instances(instances_dir: str,
                     seeds: Optional[List[int]] = None,
                     sizes: Optional[List[str]] = None,
                     schedules: Optional[List[str]] = None,
                     speeds: Optional[List[str]] = None,
                     preps: Optional[List[str]] = None) -> List[str]:
    """Filter the 240 mdrplib instances by any subset of its 5 design factors."""
    names = []
    for n in list_instances(instances_dir):
        try:
            tags = parse_instance_name(n)
        except ValueError:
            continue
        if seeds     and tags['seed']     not in seeds:     continue
        if sizes     and tags['size']     not in sizes:     continue
        if schedules and tags['schedule'] not in schedules: continue
        if speeds    and tags['speed']    not in speeds:    continue
        if preps     and tags['prep']     not in preps:     continue
        names.append(n)
    return names


def run_one(instance_name: str, instances_dir: str, policy_name: str,
           objective: str = 'max_coverage', acceptance_mode: str = 'auto',
           seed: int = 42, bundle: int = 3, **cfg_overrides) -> Dict[str, Any]:
    """Run a single (instance, policy[, ilp objective], acceptance mode) combination end to end."""
    cfg = Config(seed=seed, objective=objective, max_bundle_size=bundle,
                acceptance_mode=acceptance_mode, **cfg_overrides)
    instance = load_instance(instance_name, instances_dir, cfg)
    policy = build_policy(policy_name, cfg)

    env = simpy.Environment()
    sim = MDRPSimulator(env, instance, policy, cfg)
    sim.start()

    t0 = time.perf_counter()
    env.run(until=cfg.sim_end)
    wall_clock_sec = time.perf_counter() - t0

    m = compute_metrics(sim.get_results(), cfg, wall_clock_sec=wall_clock_sec)
    m.update(parse_instance_name(instance_name))
    m['instance']        = instance_name
    m['policy']          = policy_name
    m['objective']       = objective if policy_name == 'ilp' else ''
    m['acceptance_mode'] = acceptance_mode
    return m


def run_batch(instances: List[str], instances_dir: str, policies: List[str],
             objectives: Optional[List[str]] = None,
             acceptance_modes: Optional[List[str]] = None,
             seed: int = 42, bundle: int = 3, out_csv: Optional[str] = None,
             **cfg_overrides) -> pd.DataFrame:
    """Run every (instance x policy[x ilp objective] x acceptance mode) combination."""
    objectives = objectives or ['max_coverage']
    acceptance_modes = acceptance_modes or ['auto']
    rows = []
    total = (len(instances)
            * sum(len(objectives) if p == 'ilp' else 1 for p in policies)
            * len(acceptance_modes))
    done = 0

    for instance_name in instances:
        for policy_name in policies:
            objs = objectives if policy_name == 'ilp' else ['max_coverage']
            for obj in objs:
                for mode in acceptance_modes:
                    done += 1
                    tag = f" ({obj})" if policy_name == 'ilp' else ''
                    print(f"[{done}/{total}] {instance_name}  .  {policy_name}{tag}  .  accept={mode}")
                    try:
                        rows.append(run_one(instance_name, instances_dir, policy_name,
                                            objective=obj, acceptance_mode=mode,
                                            seed=seed, bundle=bundle, **cfg_overrides))
                    except Exception as exc:
                        print(f"    FAILED: {exc}")

    df = pd.DataFrame(rows)
    if out_csv:
        df.to_csv(out_csv, index=False)
        print(f"\nSaved {len(df):,} rows to {out_csv}")
    return df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='mdrplib sensitivity-analysis batch runner')
    parser.add_argument('--instances-dir', type=str, default=DEFAULT_INSTANCES_DIR)
    parser.add_argument('--seeds',     type=int, nargs='*', default=None, help='e.g. 0 1 2')
    parser.add_argument('--sizes',     type=str, nargs='*', default=None, help='e.g. o100 o50 r50')
    parser.add_argument('--schedules', type=str, nargs='*', default=None, help='e.g. s1 s2')
    parser.add_argument('--speeds',    type=str, nargs='*', default=None, help='e.g. t100 t75')
    parser.add_argument('--preps',     type=str, nargs='*', default=None, help='e.g. p100 p125')

    parser.add_argument('--policies', type=str, nargs='+', default=['greedy'],
                        choices=['greedy', 'fair_greedy', 'ilp', 'mdrpsim_greedy',
                                'mdrpsim_mip', 'mdrpsim_graph', 'mdrpsim_graph_prospects'])
    parser.add_argument('--objectives', type=str, nargs='*', default=['max_coverage'],
                        choices=['max_coverage', 'max_throughput', 'min_lateness',
                                'max_equity', 'min_cost'],
                        help='Only used when --policies includes ilp')

    parser.add_argument('--acceptance-modes', type=str, nargs='+', default=['auto'],
                        choices=['auto', 'fixed', 'logistic'],
                        help='Transversal to --policies: crossed with every policy/objective')
    parser.add_argument('--acceptance-range', type=float, nargs=2, default=[1.0, 1.0],
                        metavar=('MIN', 'MAX'), help='Used when --acceptance-modes includes fixed')

    parser.add_argument('--bundle', type=int, default=3)
    parser.add_argument('--seed', type=int, default=42, help='RNG seed for acceptance sampling')
    parser.add_argument('--out', type=str, default='sensitivity_results.csv')

    args = parser.parse_args()
    instances = select_instances(args.instances_dir, seeds=args.seeds, sizes=args.sizes,
                                 schedules=args.schedules, speeds=args.speeds, preps=args.preps)
    print(f"{len(instances)} instance(s) selected.")
    if not instances:
        raise SystemExit("No instances matched the given filters -- check --sizes/--schedules/"
                         "--speeds/--preps/--seeds against the actual folder names (--list in run.py).")

    run_batch(instances, args.instances_dir, args.policies, args.objectives,
             acceptance_modes=args.acceptance_modes, seed=args.seed, bundle=args.bundle,
             out_csv=args.out,
             min_acceptance_rate=args.acceptance_range[0],
             max_acceptance_rate=args.acceptance_range[1])
