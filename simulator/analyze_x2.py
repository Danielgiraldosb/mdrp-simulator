"""Read of X2 (threshold): the five selected configurations at the ends of the 95 % CI of the behavioural threshold
(theta = 615 and 1,242 COP/km), manual regime, five seeds, paired on (instance, seed) with the same configurations at
theta = 903 (X1 main.csv for greedy / hier / paybrkga_l05, X3 gen2.csv for the k_d = 25 variants). Works on a partial
threshold.csv. Prints per configuration and theta: coverage (mean, relative difference over theta = 903 in %),
lateness, F_Gini over the eligible couriers (mean, paired delta with 95 % CI), active share, payment (% of tariff),
compliance with alpha in {0.40, 0.45}, and the ranking of the configurations by coverage and by F_Gini at each theta.
Writes the theta cells of Table tab:sensitivity (coverage, relative %) and its Gini companion to
output/paper/tables/threshold.txt.

    python analyze_couriers.py output/paper/threshold.csv --out output/paper/threshold_couriers.csv
    python analyze_x2.py > output/paper/x2_analysis.txt
"""
import os

import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
COLS = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig', 'p25_elig_hourly']
KEY = ['instance', 'seed']
SRC903 = {'greedy': 'main', 'hier': 'main', 'paybrkga_l05': 'main', 'brkga_fair_w40_xk25': 'gen2', 'mipfair_a030_xk25_e000': 'gen2'}
LABEL = {'greedy': 'Greedy', 'hier': 'Hierarchical', 'brkga_fair_w40_xk25': 'BRKGA-Fair (w=40, k_d=25)',
         'mipfair_a030_xk25_e000': 'MIP-Fair (a=0.30, k_d=25)', 'paybrkga_l05': 'Pay-BRKGA (l=0.5)'}
THETAS = [615.0, 903.0, 1242.0]


def ci(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) < 2:
        return 'n/a'
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'{x.mean():+.3f} [{x.mean() - h:+.3f},{x.mean() + h:+.3f}]'


def load(name: str) -> pd.DataFrame:
    d = pd.read_csv(OUT + f'{name}.csv')
    cp = OUT + f'{name}_couriers.csv'
    if os.path.exists(cp):
        d = d.merge(pd.read_csv(cp)[COLS], on='run_id', how='left')
    else:
        for c in COLS[1:]:
            d[c] = np.nan
    d['pay_pct'] = 100.0 * d['total_payment'] / (d['n_delivered'] * 2200.0)
    d['wall_min'] = d['wall_clock_sec'] / 60.0
    return d


def main() -> None:
    x2 = load('threshold')
    x2 = x2[x2.regime == 'manual']
    src = {'main': load('main'), 'gen2': load('gen2')}
    seeds = sorted(x2.seed.unique())
    print(f'threshold rows {len(x2)} ({x2.method.nunique()} configs, {x2.instance.nunique()} zones, seeds {seeds}, '
          f'thetas {sorted(x2.ppk_threshold.unique())}); rows per config x theta:')
    print(x2.groupby(['method', 'ppk_threshold']).size().unstack(fill_value=0).to_string())
    pd.set_option('display.width', 250)
    rows, cells = [], {}
    by_theta = {}
    for meth, sname in SRC903.items():
        base = src[sname]
        b = base[(base.regime == 'manual') & (base.method == meth) & (base.seed.isin(seeds))].set_index(KEY)
        for th in THETAS:
            if th == 903.0:
                d = b
            else:
                d = x2[(x2.method == meth) & (x2.ppk_threshold == th)].set_index(KEY)
                if d.empty:
                    continue
            bb = b.reindex(d.index)
            rel = 100.0 * (d.coverage_rate.mean() / bb.coverage_rate.mean() - 1.0)
            rel_g = 100.0 * (d.gini_elig_hourly.mean() / bb.gini_elig_hourly.mean() - 1.0) if d.gini_elig_hourly.notna().any() else np.nan
            rows.append({'config': meth, 'theta': int(th), 'n': len(d), 'coverage': round(d.coverage_rate.mean(), 3),
                         'cov rel %': round(rel, 1), 'dCov [CI]': ci(d.coverage_rate - bb.coverage_rate) if th != 903 else '0',
                         'late min': round(d.overage_mean.mean(), 1), 'F_Gini': round(d.gini_elig_hourly.mean(), 3),
                         'Gini rel %': round(rel_g, 1), 'dGini [CI]': ci(d.gini_elig_hourly - bb.gini_elig_hourly) if th != 903 else '0',
                         'active': round(d.share_active_elig.mean(), 2), 'pay %': round(d.pay_pct.mean(), 0),
                         '<=0.40': f'{(d.gini_elig_hourly <= 0.40).mean():.2f}', '<=0.45': f'{(d.gini_elig_hourly <= 0.45).mean():.2f}',
                         'min/run': round(d.wall_min.mean(), 1)})
            cells[(meth, int(th))] = (rel, rel_g)
            by_theta.setdefault(int(th), {})[meth] = (d.coverage_rate.mean(), d.gini_elig_hourly.mean())
    print()
    print(pd.DataFrame(rows).to_string(index=False))
    print('\n-- ranking by coverage (desc) and by F_Gini (asc) at each theta --')
    for th, dd in sorted(by_theta.items()):
        cov = sorted(dd.items(), key=lambda kv: -kv[1][0])
        gin = sorted(dd.items(), key=lambda kv: kv[1][1])
        print(f'  theta={th}: coverage ' + ' > '.join(f'{LABEL[k]} {v[0]:.3f}' for k, v in cov))
        print(f'  theta={th}: F_Gini   ' + ' < '.join(f'{LABEL[k]} {v[1]:.3f}' for k, v in gin))
    # table cells
    lines = ['theta cells of tab:sensitivity (relative difference of coverage over theta = 903, %), and Gini companion',
             'config, 615, 903, 1242  (coverage) | 615, 903, 1242 (F_Gini)']
    for meth in SRC903:
        c = [cells.get((meth, th), (np.nan, np.nan)) for th in (615, 903, 1242)]
        lines.append(f'{LABEL[meth]:28s} ' + ' & '.join(f'{v[0]:+.1f}' if not np.isnan(v[0]) else '' for v in c) + '  |  '
                     + ' & '.join(f'{v[1]:+.1f}' if not np.isnan(v[1]) else '' for v in c))
    os.makedirs(OUT + 'tables', exist_ok=True)
    open(OUT + 'tables/threshold.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n' + '\n'.join(lines))


if __name__ == '__main__':
    main()
