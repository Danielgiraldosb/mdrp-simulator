"""
analyze_paper.py -- summaries of batch_paper.py outputs (Etapa 5 tooling).

  python analyze_paper.py output/paper/pilot.csv                 # per instance x method table + timing
  python analyze_paper.py output/paper/main.csv --main           # X1: Pareto points, compliance, paired diffs
  python analyze_paper.py output/paper/main.csv --main --md out.md
  python analyze_paper.py output/paper/main.csv --main --gini elig --couriers-table output/paper/main_couriers.csv
      # decision E9 (2026-10-21, ratified): F_Gini in every table is the Gini over the ELIGIBLE couriers
      # (connected >= 1 h, idle ones at zero), from analyze_couriers.py --out; the active-courier Gini of
      # metrics.py is kept as F_Gini_active

Every comparison between methods is PAIRED by (instance, seed): common random numbers
(diseno-experimental.md section 6). Instances are the blocks; seeds are averaged inside.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

import numpy as np
import pandas as pd

KEY = ['coverage_rate', 'overage_mean', 'F_Gini', 'F_Deficit', 'total_payment',
       'n_couriers_active', 'solve_mean', 'wall_clock_sec']


def load(paths: List[str]) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    if 'failed' in df.columns:
        df = df[df['failed'].fillna(False).astype(str) != 'True']
    for c in ('alpha', 'weight', 'lambda_pay'):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def fmt(df: pd.DataFrame, cols: List[str]) -> str:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].map(lambda v: f'{v:.3f}' if isinstance(v, float) and abs(v) < 10
                                else (f'{v:,.0f}' if isinstance(v, (int, float)) else v))
    return out.to_string()


def pilot_tables(df: pd.DataFrame) -> str:
    lines = []
    cols = [c for c in KEY if c in df.columns]
    t = df.groupby(['city', 'instance', 'method'])[cols].mean().reset_index()
    lines.append('== per instance x method (mean over seeds) ==')
    lines.append(fmt(t, cols))
    if 'n_orders' in df.columns:
        df = df.assign(sec_per_order=df['wall_clock_sec'] / df['n_orders'].clip(lower=1),
                       min_per_run=df['wall_clock_sec'] / 60.0)
        tt = df.groupby('method').agg(runs=('run_id', 'count'), min_per_run_mean=('min_per_run', 'mean'),
                                      min_per_run_max=('min_per_run', 'max'),
                                      sec_per_order_median=('sec_per_order', 'median'))
        lines.append('\n== timing by method ==')
        lines.append(tt.round(3).to_string())
    corp = df[(df['method'] == 'greedy') & (df['regime'] == 'manual')]
    if len(corp):
        g = corp.groupby('city')['F_Gini'].mean()
        lines.append('\n== corporate (greedy, manual) end-of-day F_Gini by city ==')
        lines.append(g.round(3).to_string())
        gm = float(corp['F_Gini'].mean())
        lines.append(f'mean = {gm:.3f} -> alpha grid '
                     f"{'stays' if 0.35 <= gm <= 0.55 else 'MUST be recentred (diseno-experimental.md section 2)'}")
    return '\n'.join(lines)


def sweep_param(method: str) -> Optional[str]:
    if method.startswith('mipfair'):
        return 'alpha'
    if method.startswith('brkga_fair'):
        return 'weight'
    if method.startswith('paybrkga'):
        return 'lambda_pay'
    return None


def main_tables(df: pd.DataFrame, alpha_ref: float = 0.30) -> str:
    lines = []
    # 1. instance-level means (seeds averaged inside the block)
    cols = [c for c in KEY if c in df.columns]
    blk = df.groupby(['regime', 'method', 'instance'])[cols].mean().reset_index()
    # 2. Pareto points per method config and regime (mean +- sd over instances)
    pts = blk.groupby(['regime', 'method']).agg(
        coverage=('coverage_rate', 'mean'), coverage_sd=('coverage_rate', 'std'),
        overage=('overage_mean', 'mean'), gini=('F_Gini', 'mean'), gini_sd=('F_Gini', 'std'),
        deficit=('F_Deficit', 'mean'), payment=('total_payment', 'mean'),
        active=('n_couriers_active', 'mean'), sec_round=('solve_mean', 'mean')).reset_index()
    lines.append('== Pareto points: mean over 24 instances (seeds averaged inside) ==')
    lines.append(pts.round(3).to_string())
    # 3. compliance F_Gini <= alpha per (instance, seed), by method and alpha
    if 'alpha' in df.columns:
        alphas = sorted(set(a for a in df["alpha"].dropna().unique() if a < 1.0) | {0.45, 0.5, 0.55, 0.6}) or [alpha_ref]
        rows = []
        for (reg, m), g in df.groupby(['regime', 'method']):
            row = {'regime': reg, 'method': m}
            for a in alphas:
                row[f'P(Gini<={a:g})'] = float((g['F_Gini'] <= a).mean())
            rows.append(row)
        lines.append('\n== compliance share of (instance, seed) with end-of-day F_Gini <= alpha ==')
        lines.append(pd.DataFrame(rows).round(3).to_string())
    # 4. paired differences vs greedy on (instance, seed), bootstrap CI over instances
    ref = df[df['method'] == 'greedy'].set_index(['regime', 'instance', 'seed'])
    rows = []
    rng = np.random.default_rng(0)
    for (reg, m), g in df.groupby(['regime', 'method']):
        if m == 'greedy':
            continue
        j = g.set_index(['regime', 'instance', 'seed']).join(ref[['coverage_rate', 'F_Gini', 'overage_mean']],
                                                             rsuffix='_ref', how='inner')
        if j.empty:
            continue
        d = pd.DataFrame({'d_cov': j['coverage_rate'] - j['coverage_rate_ref'],
                          'd_gini': j['F_Gini'] - j['F_Gini_ref'],
                          'd_over': j['overage_mean'] - j['overage_mean_ref']}).reset_index()
        per_inst = d.groupby('instance')[['d_cov', 'd_gini', 'd_over']].mean()
        n = len(per_inst)
        boots = np.array([per_inst.sample(n, replace=True, random_state=int(rng.integers(1 << 30))).mean().values
                          for _ in range(1000)])
        lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
        mean = per_inst.mean().values
        rows.append({'regime': reg, 'method': m, 'n_inst': n,
                     'd_cov': mean[0], 'd_cov_lo': lo[0], 'd_cov_hi': hi[0],
                     'd_gini': mean[1], 'd_gini_lo': lo[1], 'd_gini_hi': hi[1],
                     'd_over': mean[2]})
    if rows:
        lines.append('\n== paired differences vs greedy (same instance & seed), 95% bootstrap CI over instances ==')
        lines.append(pd.DataFrame(rows).round(3).to_string())
    # 5. regime loss (manual - autoaccept) per method
    if set(df['regime'].unique()) >= {'manual', 'autoaccept'}:
        piv = blk.pivot_table(index=['method', 'instance'], columns='regime', values='coverage_rate')
        loss = (piv['manual'] - piv['autoaccept']).groupby('method').agg(['mean', 'std'])
        lines.append('\n== coverage loss manual - autoaccept, by method (mean, sd over instances) ==')
        lines.append(loss.round(3).to_string())
    # 6. knee per sweep (max distance to the chord between extremes, in normalised gini/coverage)
    knees = []
    for reg, g in pts.groupby('regime'):
        for fam in ('mipfair', 'brkga_fair', 'paybrkga'):
            s = g[g['method'].str.startswith(fam)].copy()
            if len(s) < 3:
                continue
            s = s.sort_values('gini')
            x = (s['gini'] - s['gini'].min()) / max(s['gini'].max() - s['gini'].min(), 1e-9)
            y = (s['coverage'] - s['coverage'].min()) / max(s['coverage'].max() - s['coverage'].min(), 1e-9)
            x0, y0, x1, y1 = x.iloc[0], y.iloc[0], x.iloc[-1], y.iloc[-1]
            dist = np.abs((y1 - y0) * x - (x1 - x0) * y + x1 * y0 - y1 * x0) / max(np.hypot(y1 - y0, x1 - x0), 1e-9)
            k = s.iloc[int(np.argmax(dist.values))]
            knees.append({'regime': reg, 'family': fam, 'knee': k['method'], 'gini': k['gini'], 'coverage': k['coverage']})
    if knees:
        lines.append('\n== knee of each sweep (max distance to chord, coverage vs gini) ==')
        lines.append(pd.DataFrame(knees).round(3).to_string())
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv', nargs='+')
    ap.add_argument('--main', action='store_true', help='X1-style summaries (Pareto, compliance, paired)')
    ap.add_argument('--md', default=None, help='also write the text to this file')
    ap.add_argument('--couriers-table', default=None,
                    help='per-run table from analyze_couriers.py --out (joined on run_id)')
    ap.add_argument('--gini', default='active', choices=['active', 'elig'],
                    help="which Gini is F_Gini in the tables: 'active' (metrics.py) or 'elig' (E9: eligible "
                         "couriers, zeros included; needs --couriers-table)")
    ap.add_argument('--complete-seeds', action='store_true', help='keep only seeds present for every cell')
    args = ap.parse_args()
    df = load(args.csv)
    if args.couriers_table:
        ct = pd.read_csv(args.couriers_table)
        keep = [c for c in ct.columns if c.startswith('gini_') or c.startswith('share_') or c.startswith('p25_')]
        df = df.merge(ct[['run_id'] + keep], on='run_id', how='left')
    if args.gini == 'elig':
        if 'gini_elig_hourly' not in df.columns:
            sys.exit('--gini elig needs --couriers-table (analyze_couriers.py --out)')
        df['F_Gini_active'] = df['F_Gini']
        df['F_Gini'] = df['gini_elig_hourly']
        print('F_Gini = Gini over eligible couriers (connected >= 1 h, zeros included), decision E9')
    if args.complete_seeds:
        full = df.groupby('seed')['run_id'].count()
        full = full[full == full.max()].index
        df = df[df['seed'].isin(full)]
        print(f'complete seeds: {sorted(int(x) for x in full)}')
    print(f'{len(df)} runs, {df["instance"].nunique()} instances, {df["method"].nunique()} methods, '
          f'regimes {sorted(df["regime"].unique())}')
    text = main_tables(df) if args.main else pilot_tables(df)
    print(text)
    if args.md:
        with open(args.md, 'w', encoding='utf-8') as fh:
            fh.write('```\n' + text + '\n```\n')


if __name__ == '__main__':
    main()
