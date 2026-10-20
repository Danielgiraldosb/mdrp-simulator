"""
batch_hier_clusters.py -- decision 10A: greedy vs hier over the 240 mdrplib
instances, read by cluster (instance_clusters.csv).

Every (instance, policy) run executes in its OWN Python subprocess, with
retries. Reason: gurobipy 11.0.3 on this machine shows sporadic access
violations (heap corruption, random location, sometimes before the first
round) when one process runs many simulated days back to back; one process
per run plus a retry makes the batch finish and keeps a crash from costing
more than one run. Resume-safe: rows already in --out are skipped.

  python batch_hier_clusters.py --policies greedy hier --workers 3 --out output/hier_vs_greedy_240.csv
  python batch_hier_clusters.py --summary output/hier_vs_greedy_240.csv      # only the per-cluster tables
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import pandas as pd

from run import DEFAULT_INSTANCES_DIR
from loader import list_instances

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CLUSTER_LABELS = {0: 'Dispersas, con holgura', 1: 'Pequeñas y compactas',
                  2: 'Medianas y cargadas', 3: 'Grandes y saturadas'}
CHILD = (
    "import json, sys; sys.path.insert(0, %r); "
    "from batch_sensitivity import run_one; "
    "ov = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}; "
    "m = run_one(sys.argv[1], sys.argv[2], sys.argv[3], **ov); "
    "m.update(instance=sys.argv[1], policy=(sys.argv[5] if len(sys.argv) > 5 else sys.argv[3])); "
    "print('ROW' + json.dumps(m))"
) % THIS_DIR


def parse_variant(spec: str):
    """'hier' -> ('hier', {}, 'hier'); 'hier:coverage,lateness,cost,equity' -> ('hier', {'hier_order': [...]}, 'hier[cov,lat,cost,eq]')"""
    if ':' not in spec:
        return spec, {}, spec
    name, order = spec.split(':', 1)
    names = [o.strip() for o in order.split(',') if o.strip()]
    short = {'coverage': 'cov', 'lateness': 'lat', 'equity': 'eq', 'cost': 'cost'}
    return name, {'hier_order': names}, f"{name}[{','.join(short.get(n, n) for n in names)}]"


def run_isolated(instance: str, instances_dir: str, policy: str, retries: int = 3,
                 timeout: int = 1800) -> Dict:
    env = dict(os.environ, PYTHONIOENCODING='utf8')
    name, overrides, label = parse_variant(policy)
    last_err = ''
    for attempt in range(1, retries + 1):
        t0 = time.perf_counter()
        try:
            p = subprocess.run([sys.executable, '-c', CHILD, instance, instances_dir, name, json.dumps(overrides), label],
                               capture_output=True, text=True, encoding='utf8', errors='replace',
                               timeout=timeout, env=env, cwd=THIS_DIR)
        except subprocess.TimeoutExpired:
            last_err = f'timeout after {timeout}s'
            continue
        row = None
        for line in p.stdout.splitlines():
            if line.startswith('ROW'):
                row = json.loads(line[3:])
        if row is not None:
            row['attempts'] = attempt
            row['child_s'] = round(time.perf_counter() - t0, 2)
            return row
        last_err = f'exit {p.returncode}: ' + (p.stderr.strip().splitlines() or ['no output'])[-1][:200]
    return {'instance': instance, 'policy': label, 'failed': last_err, 'attempts': retries}


def summarize(df: pd.DataFrame) -> None:
    cl = pd.read_csv(os.path.join(THIS_DIR, 'instance_clusters.csv'))[['instance', 'cluster']]
    df = df.merge(cl, on='instance', how='left')
    df['cluster_label'] = df['cluster'].map(CLUSTER_LABELS)
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 40)
    if 'failed' in df.columns and df['failed'].notna().any():
        print('\nFAILED runs:')
        print(df[df['failed'].notna()][['instance', 'policy', 'failed']].to_string(index=False))
        df = df[df['failed'].isna()]
    cols = ['coverage_rate', 'c2d_mean', 'c2d_p90', 'overage_mean', 'overage_total_min', 'F_Gini', 'F_MaxMin', 'F_Deficit',
            'courier_active_min_total', 'total_payment', 'bundle_size_mean', 'wall_clock_sec']
    cols = [c for c in cols if c in df.columns]
    print('\n== mean by cluster x policy ==')
    print(df.groupby(['cluster', 'cluster_label', 'policy'])[cols].mean().round(4).to_string())
    print('\n== overall mean by policy ==')
    print(df.groupby('policy')[cols].mean().round(4).to_string())
    pols = sorted(df['policy'].unique())
    if 'greedy' in pols and 'hier' in pols:
        piv = df.pivot_table(index=['instance', 'cluster'], columns='policy',
                             values=['coverage_rate', 'overage_mean', 'F_Gini', 'c2d_mean', 'total_payment'])
        d = pd.DataFrame({
            'd_cov': piv['coverage_rate']['hier'] - piv['coverage_rate']['greedy'],
            'd_over': piv['overage_mean']['hier'] - piv['overage_mean']['greedy'],
            'd_gini': piv['F_Gini']['hier'] - piv['F_Gini']['greedy'],
            'd_c2d': piv['c2d_mean']['hier'] - piv['c2d_mean']['greedy'],
            'd_pay': piv['total_payment']['hier'] - piv['total_payment']['greedy'],
        }).reset_index()
        eps = 1e-9
        agg = d.groupby('cluster').agg(
            n=('d_cov', 'size'),
            d_cov=('d_cov', 'mean'), cov_better=('d_cov', lambda x: (x > eps).mean()), cov_worse=('d_cov', lambda x: (x < -eps).mean()),
            d_over=('d_over', 'mean'), over_better=('d_over', lambda x: (x < -eps).mean()), over_worse=('d_over', lambda x: (x > eps).mean()),
            d_gini=('d_gini', 'mean'), gini_better=('d_gini', lambda x: (x < -eps).mean()),
            d_c2d=('d_c2d', 'mean'), d_pay=('d_pay', 'mean'))
        print('\n== paired hier - greedy by cluster (negative d_over / d_gini = hier better) ==')
        print(agg.round(4).to_string())
        print('\n== paired overall ==')
        print(d[['d_cov', 'd_over', 'd_gini', 'd_c2d', 'd_pay']].mean().round(4).to_string())
        print('cov better / equal / worse:', round((d.d_cov > eps).mean(), 3), round((d.d_cov.abs() <= eps).mean(), 3), round((d.d_cov < -eps).mean(), 3))
        print('over better / equal / worse:', round((d.d_over < -eps).mean(), 3), round((d.d_over.abs() <= eps).mean(), 3), round((d.d_over > eps).mean(), 3))
        print('gini better / worse:', round((d.d_gini < -eps).mean(), 3), round((d.d_gini > eps).mean(), 3))
        d.to_csv(os.path.join(THIS_DIR, 'output', 'hier_vs_greedy_paired.csv'), index=False)
    out2 = os.path.splitext(args_out_global)[0] + '_clusters.csv'
    df.to_csv(out2, index=False)
    print(f'\nwrote {out2}')


args_out_global = 'output/hier_vs_greedy_240.csv'


def main(argv=None):
    global args_out_global
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--policies', nargs='+', default=['greedy', 'hier'],
                    help="policy names; a hier variant as hier:coverage,lateness,cost,equity")
    ap.add_argument('--instances-dir', default=DEFAULT_INSTANCES_DIR)
    ap.add_argument('--instances', nargs='*', default=None, help='subset; default all 240')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--retries', type=int, default=3)
    ap.add_argument('--timeout', type=int, default=1800, help='seconds per run before it is killed and retried')
    ap.add_argument('--out', default='output/hier_vs_greedy_240.csv')
    ap.add_argument('--summary', default=None, help='only summarise an existing CSV')
    args = ap.parse_args(argv)
    args_out_global = args.summary or args.out

    if args.summary:
        summarize(pd.read_csv(args.summary))
        return 0

    instances = args.instances or list_instances(args.instances_dir)
    done = set()
    rows: List[Dict] = []
    if os.path.exists(args.out):
        prev = pd.read_csv(args.out)
        rows = prev.to_dict(orient='records')
        done = {(r['instance'], r['policy']) for r in rows if not (isinstance(r.get('failed'), str) and r['failed'])}
    jobs = [(i, p) for i in instances for p in args.policies if (i, parse_variant(p)[2]) not in done]
    print(f'{len(instances)} instances x {args.policies} -> {len(jobs)} runs to do ({len(done)} already in {args.out}); workers={args.workers}', flush=True)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    t0 = time.perf_counter()
    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_isolated, i, args.instances_dir, p, args.retries, args.timeout): (i, p) for i, p in jobs}
        for f in as_completed(futs):
            i, p = futs[f]
            row = f.result()
            rows = [r for r in rows if not (r['instance'] == i and r['policy'] == row['policy'])]
            rows.append(row)
            n += 1
            status = 'FAILED ' + str(row.get('failed'))[:80] if row.get('failed') else \
                f"cov={row.get('coverage_rate')} over={row.get('overage_mean')} gini={row.get('F_Gini')} tries={row.get('attempts')}"
            print(f'[{n}/{len(jobs)}] {i:<18} {p:<7} {status}  ({time.perf_counter() - t0:,.0f}s)', flush=True)
            if n % 5 == 0 or n == len(jobs):
                pd.DataFrame(rows).to_csv(args.out, index=False)
    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f'\nSaved {len(rows)} rows to {args.out} in {time.perf_counter() - t0:,.0f}s')
    summarize(pd.DataFrame(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
