"""
eligibility_thresholds.py -- P37 (2): sensitivity of the end-of-day Gini coefficient of Eq. (gini) to the
eligibility threshold (connected at least 0.5, 1 or 2 hours; idle couriers at zero), recomputed from the
per-courier tables of the runs (output/paper/couriers/<run_id>.csv). No new runs.

Configurations: those of tab:benchmark (X1, main.csv, ten complete seeds) plus Greedy-Arrival (review.csv,
same seeds). With threshold 1 h it reproduces the F_G column of tab:benchmark (check printed).

  python eligibility_thresholds.py [--out output/paper/eligibility_thresholds.csv] [--tex output/paper/tables/eligibility.tex]
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from analyze_couriers import gini
from tables_paper import CONFIGS, display_name

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(THIS_DIR, 'output', 'paper')
THRESHOLDS = (0.5, 1.0, 2.0)


def runs() -> pd.DataFrame:
    main = pd.read_csv(os.path.join(O, 'main.csv'))
    cnt = main.groupby('seed')['run_id'].count()
    main = main[main['seed'].isin(cnt[cnt == cnt.max()].index)]
    rev = pd.read_csv(os.path.join(O, 'review.csv'))
    rev = rev[(rev.method == 'greedy_arrival') & rev.seed.isin(main.seed.unique())]
    df = pd.concat([main[main.method.isin(CONFIGS)], rev], ignore_index=True)
    return df[['run_id', 'regime', 'method', 'instance', 'seed']]


def per_run(path: str) -> dict:
    t = pd.read_csv(path, usecols=['shift_h', 'payment'])
    out = {}
    for thr in THRESHOLDS:
        e = t[t['shift_h'] >= thr]
        out[f'gini_{thr:g}h'] = gini(e['payment'] / e['shift_h'].clip(lower=1e-9))
        out[f'active_{thr:g}h'] = float((e['payment'] > 0).mean()) if len(e) else np.nan
        out[f'n_{thr:g}h'] = len(e)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(O, 'eligibility_thresholds.csv'))
    ap.add_argument('--tex', default=os.path.join(O, 'tables', 'eligibility.tex'))
    a = ap.parse_args()
    df = runs()
    rows = [{'run_id': r.run_id, **per_run(os.path.join(O, 'couriers', f'{r.run_id}.csv'))} for r in df.itertuples()]
    df = df.merge(pd.DataFrame(rows), on='run_id')
    df.to_csv(a.out, index=False)
    order = CONFIGS[:1] + ['greedy_arrival'] + CONFIGS[1:]
    cols = [f'gini_{t:g}h' for t in THRESHOLDS]
    tab = df.groupby(['regime', 'method'])[cols + [f'active_{t:g}h' for t in THRESHOLDS]].mean()
    print(f'runs {len(df)}; seeds {sorted(df.seed.unique())}; instances {df.instance.nunique()}')
    lines = []
    for reg, name in (('manual', 'Manual regime'), ('autoaccept', 'Auto-accept regime')):
        t = tab.loc[reg].reindex([m for m in order if m in tab.loc[reg].index])
        print(f'\n== {reg}\n' + t.round(3).to_string())
        others = t.drop(index=['greedy'])
        for c in cols:
            print(f'{c}: Greedy {t.loc["greedy", c]:.3f} < min of the others {others[c].min():.3f} '
                  f'({others[c].idxmin()}): {t.loc["greedy", c] < others[c].min()}')
        lines.append(f'\\multicolumn{{7}}{{l}}{{\\textit{{{name}}}}} \\\\')
        for m, r in t.iterrows():
            lines.append(display_name(m) + ' & ' + ' & '.join(f'{r[c]:.3f}' for c in cols) + ' & '
                         + ' & '.join(f'{r[f"active_{x:g}h"]:.2f}' for x in THRESHOLDS) + r' \\')
        lines.append(r'\hline')
    os.makedirs(os.path.dirname(a.tex), exist_ok=True)
    open(a.tex, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('wrote', a.tex)


if __name__ == '__main__':
    main()
