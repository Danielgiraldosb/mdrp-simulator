"""
analyze_couriers.py -- analysis A1: alternative scopes of the end-of-day Gini coefficient, computed
ex post from the per-courier tables written by batch_paper.py (output/paper/couriers/<run_id>.csv).

metrics.py's F_Gini is the Gini of earnings per connected hour over the couriers with at least one
delivery ("active"). Policies can lower it by concentrating work on fewer couriers. Decision E9 (ratified
2026-10-21): the statistic of the paper is gini_elig_hourly, over the ELIGIBLE couriers (connected
>= MIN_SHIFT_H hours, idle ones at zero); analyze_paper.py --gini elig and figures_paper.py read it from
the --out table. Also reported:

  gini_all_hourly    earnings per connected hour over ALL loaded couriers (idle ones count as zero)
  gini_active_total  total earnings over active couriers
  gini_all_total     total earnings over all loaded couriers
  gini_active_perh   earnings per ACTIVE hour over active couriers (productivity, not exposure)
  share_active       active / loaded
  share_single       active couriers with exactly one order / active
  p10_hourly, median_hourly  of earnings per connected hour over active couriers

  python analyze_couriers.py output/paper/main.csv [--couriers output/paper/couriers]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

pd.set_option('display.width', 250)
pd.set_option('display.max_rows', 200)

MIN_SHIFT_H = 1.0   # eligible courier: connected at least one hour


def gini(v) -> float:
    v = np.asarray(sorted(float(x) for x in v))
    n = len(v)
    if n == 0 or v.sum() <= 0:
        return 0.0
    i = np.arange(1, n + 1)
    return float((2.0 * (i * v).sum()) / (n * v.sum()) - (n + 1.0) / n)


def per_run(path: str) -> dict:
    t = pd.read_csv(path)
    act = t[t['orders'] > 0]
    hourly_all = t['payment'] / t['shift_h'].clip(lower=1e-9)
    hourly_act = act['payment'] / act['shift_h'].clip(lower=1e-9)
    perh_act = act['payment'] / act['active_h'].clip(lower=1e-9)
    # eligible couriers: connected at least MIN_SHIFT_H hours (decision E9 candidate); zeros included
    elig = t[t['shift_h'] >= MIN_SHIFT_H]
    elig_act = elig[elig['orders'] > 0]
    hourly_elig = elig['payment'] / elig['shift_h'].clip(lower=1e-9)
    return {
        'gini_active_hourly': gini(hourly_act),
        'gini_all_hourly': gini(hourly_all),
        'gini_active_total': gini(act['payment']),
        'gini_all_total': gini(t['payment']),
        'gini_active_perh': gini(perh_act),
        'gini_elig_hourly': gini(hourly_elig),
        'gini_elig_active_hourly': gini(elig_act['payment'] / elig_act['shift_h'].clip(lower=1e-9)),
        'gini_elig_total': gini(elig['payment']),
        'share_elig': len(elig) / max(len(t), 1),
        'share_active_elig': len(elig_act) / max(len(elig), 1),
        'p10_elig_hourly': float(np.percentile(hourly_elig, 10)) if len(elig) else 0.0,
        'p25_elig_hourly': float(np.percentile(hourly_elig, 25)) if len(elig) else 0.0,
        'share_active': len(act) / max(len(t), 1),
        'share_single': float((act['orders'] == 1).mean()) if len(act) else 0.0,
        'p10_hourly': float(np.percentile(hourly_act, 10)) if len(act) else 0.0,
        'median_hourly': float(np.median(hourly_act)) if len(act) else 0.0,
        'n_loaded': len(t), 'n_active': len(act),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv')
    ap.add_argument('--couriers', default=None)
    ap.add_argument('--out', default=None, help='write the per-run table here (csv)')
    args = ap.parse_args()
    runs = pd.read_csv(args.csv)
    cdir = args.couriers or os.path.join(os.path.dirname(args.csv), 'couriers')
    rows = []
    for _, r in runs.iterrows():
        p = os.path.join(cdir, f"{r['run_id']}.csv")
        if not os.path.exists(p):
            continue
        d = per_run(p)
        d.update({'run_id': r['run_id'], 'instance': r['instance'], 'city': r['city'], 'method': r['method'],
                  'regime': r['regime'], 'seed': r['seed'], 'F_Gini': r['F_Gini'], 'coverage': r['coverage_rate']})
        rows.append(d)
    df = pd.DataFrame(rows)
    print(f"{len(df)} runs with courier tables ({len(runs)} in {args.csv})")
    chk = (df['gini_active_hourly'] - df['F_Gini']).abs().max()
    print(f"max |gini_active_hourly - F_Gini| = {chk:.4f} (should be ~0)")
    if args.out:
        df.to_csv(args.out, index=False)
    cols = ['F_Gini', 'gini_all_hourly', 'gini_active_total', 'gini_all_total', 'gini_active_perh',
            'gini_elig_hourly', 'gini_elig_active_hourly', 'gini_elig_total', 'share_elig', 'share_active_elig',
            'p10_elig_hourly', 'p25_elig_hourly', 'share_active', 'share_single', 'p10_hourly', 'median_hourly',
            'coverage']
    inst = df.groupby(['regime', 'method', 'instance'])[cols].mean().reset_index()
    print("\n== mean over instances (seeds averaged inside) ==")
    print(inst.groupby(['regime', 'method'])[cols].mean().round(3).to_string())
    print("\n== paired differences vs greedy (same instance), mean and 95% bootstrap CI ==")
    rng = np.random.default_rng(1)
    out = []
    for reg in sorted(inst.regime.unique()):
        base = inst[(inst.regime == reg) & (inst.method == 'greedy')].set_index('instance')
        for meth in sorted(inst.method.unique()):
            if meth == 'greedy':
                continue
            x = inst[(inst.regime == reg) & (inst.method == meth)].set_index('instance').loc[base.index]
            row = {'regime': reg, 'method': meth}
            for c in ['F_Gini', 'gini_elig_hourly', 'gini_elig_active_hourly', 'gini_elig_total', 'share_active_elig', 'p25_elig_hourly']:
                dlt = (x[c] - base[c]).to_numpy()
                boots = [rng.choice(dlt, len(dlt), replace=True).mean() for _ in range(2000)]
                row[c] = f"{dlt.mean():+.3f} [{np.percentile(boots, 2.5):+.3f},{np.percentile(boots, 97.5):+.3f}]"
            out.append(row)
    print(pd.DataFrame(out).to_string(index=False))


if __name__ == '__main__':
    main()
