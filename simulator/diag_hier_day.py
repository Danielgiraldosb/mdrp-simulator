"""
diag_hier_day.py -- run a whole simulated day with HierPolicy and summarise the
rounds: candidates per round, solve time, end_reason per pass, how often each
objective existed, and the per-pass value distribution. Companion of
diag_hier_case.py (one round) for the observability sprint (épica S3).

  python diag_hier_day.py --instance 0o100t100s1p100 [--order coverage equity lateness cost] [--json out.json]
"""
import argparse, json, os, statistics, sys
from collections import Counter, defaultdict

from config import Config
from loader import load_instance
from run import run_simulation, DEFAULT_INSTANCES_DIR
from hier_policy import HierPolicy


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--instance', required=True)
    ap.add_argument('--instances-dir', default=DEFAULT_INSTANCES_DIR)
    ap.add_argument('--order', nargs='+', default=None)
    ap.add_argument('--bundle', type=int, default=3)
    ap.add_argument('--json', default=None)
    args = ap.parse_args(argv)

    cfg = Config(hier_order=args.order, max_bundle_size=args.bundle)
    inst = load_instance(args.instance, args.instances_dir, cfg)
    policy = HierPolicy(cfg)
    results, m = run_simulation(cfg, inst, policy=policy, policy_name='hier', verbose=False)
    rounds = policy.rounds

    n = len(rounds)
    solve = [r['solve_s'] for r in rounds]
    cands = [r['candidates'] for r in rounds]
    pend = [r['indicators']['orders_pending'] for r in rounds]
    cov = [r['indicators']['orders_covered'] for r in rounds]
    unc = sum(r['indicators']['orders_uncovered'] for r in rounds)
    present = Counter(p['name'] for r in rounds for p in r['passes'])
    reasons = Counter((p['name'], p['end_reason']) for r in rounds for p in r['passes'])
    values = defaultdict(list)
    for r in rounds:
        for p in r['passes']:
            if p['value'] is not None:
                values[p['name']].append(p['value'])
    summary = {
        'instance': args.instance, 'order': args.order or 'default', 'rounds': n,
        'solve_s': {'mean': statistics.mean(solve), 'p90': sorted(solve)[int(0.9 * (n - 1))], 'max': max(solve)},
        'candidates': {'mean': statistics.mean(cands), 'max': max(cands)},
        'orders_pending_per_round': {'mean': statistics.mean(pend), 'max': max(pend)},
        'orders_left_uncovered_in_round': unc,
        'rounds_with_all_covered': sum(1 for a, b in zip(pend, cov) if a == b),
        'objective_present_rounds': dict(present),
        'end_reasons': {f"{k[0]}:{k[1]}": v for k, v in reasons.items()},
        'pass_value_mean': {k: statistics.mean(v) for k, v in values.items()},
        'metrics': {k: m[k] for k in ('coverage_rate', 'c2d_mean', 'c2d_p90', 'overage_mean', 'bundle_size_mean',
                                      'total_payment', 'F_Gini', 'F_MaxMin', 'F_Orders', 'wall_clock_sec')},
    }
    print(json.dumps(summary, indent=1))
    if args.json:
        with open(args.json, 'w', encoding='utf8') as f:
            json.dump({'summary': summary, 'rounds': rounds}, f, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
