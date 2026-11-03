"""Read of the review level-2 batch (output/paper/review.csv + review_couriers.csv), paired by (instance, seed, regime):

  A. ILP on MIP-Fair's candidate pairs (ilp_k8) against the ILP of X1 (k = 25) and against MIP-Fair at alpha = 1
     and alpha = 0.30 (k = 8): does the coverage gap between ILP and MIP-Fair come from the candidate set, and does
     the Gini constraint matter once the candidate set is the same?
  B. Courier-centric dispatcher in arrival order (greedy_arrival) against the least-served-first Greedy of X1 and
     the order-centric policies: how much of Greedy's equity is the courier-centric structure and how much the
     least-served priority?
  C. Fleet thinned to the field ratio (keep 1/3): Greedy, BRKGA-Fair (gamma = 40) and its second-generation variant
     (k_d = 25), against the same configurations with the full fleet on seeds 1-5: does the gap survive?

    python analyze_couriers.py output/paper/review.csv --out output/paper/review_couriers.csv
    python analyze_review2.py > output/paper/review_analysis.txt      (also writes tables/review2_*.tex)
"""
import os

import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
TAB = OUT + 'tables/'
COLS = ['run_id', 'gini_elig_hourly', 'share_active_elig', 'p25_elig_hourly', 'median_hourly']
KEY = ['instance', 'seed']
MET = ['coverage_rate', 'gini_elig_hourly', 'share_active_elig', 'overage_mean', 'F_Deficit', 'wall_clock_sec']
pd.set_option('display.width', 250)


def load(stem):
    d = pd.read_csv(OUT + stem + '.csv', low_memory=False)
    c = pd.read_csv(OUT + stem + '_couriers.csv')[COLS]
    return d.merge(c, on='run_id', how='inner')


def ci(x: pd.Series) -> str:
    x = x.dropna()
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'{x.mean():+.3f} [{x.mean() - h:+.3f}, {x.mean() + h:+.3f}]'


def tex_ci(x: pd.Series) -> str:
    x = x.dropna()
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'${x.mean():+.3f}$ [{x.mean() - h:+.3f}, {x.mean() + h:+.3f}]'


def paired(a: pd.DataFrame, b: pd.DataFrame, col: str) -> pd.Series:
    a = a.set_index(KEY)[col]
    b = b.set_index(KEY)[col].reindex(a.index)
    return a - b


def means(d: pd.DataFrame) -> pd.Series:
    inst = d.groupby('instance')[MET].mean()
    r = inst.mean()
    r['n'] = len(d)
    return r


def main() -> None:
    rv = load('review')
    x1 = load('main')
    g2 = load('gen2')
    print(f'review rows {len(rv)} ({rv.method.nunique()} configs); failed rows excluded by the inner merge')
    lines = {'A': [], 'B': [], 'C': []}
    for reg, title in (('manual', 'Manual regime'), ('autoaccept', 'Auto-accept regime')):
        R, X, G = rv[rv.regime == reg], x1[x1.regime == reg], g2[g2.regime == reg]
        # ---------------- A
        k8 = R[R.method == 'ilp_k8']
        print(f'\n===== {reg} =====\n-- A. ILP with k = 8 (n = {len(k8)}) --')
        rows = []
        for ref, lab in (('ilp', r'\textbf{ILP} ($k = 25$)'), ('mipfair_a100', r'\textbf{MIP-Fair} ($\alpha = 1$, $k = 8$)'),
                         ('mipfair_a030', r'\textbf{MIP-Fair} ($\alpha = 0.30$, $k = 8$)')):
            b = X[X.method == ref]
            dcov, dg = paired(k8, b, 'coverage_rate'), paired(k8, b, 'gini_elig_hourly')
            dl = paired(k8, b, 'overage_mean')
            print(f'  ilp_k8 - {ref:14s}: coverage {ci(dcov)}  F_G {ci(dg)}  lateness {dl.mean():+.2f}')
            rows.append(f'{lab} & {tex_ci(dcov)} & {tex_ci(dg)} & ${dl.mean():+.2f}$ \\\\')
        m = means(k8)
        print(f'  ilp_k8 means: coverage {m.coverage_rate:.3f}  F_G {m.gini_elig_hourly:.3f}  active {m.share_active_elig:.2f}  '
              f'late {m.overage_mean:.1f}  min/run {m.wall_clock_sec / 60:.1f}')
        lines['A'].append((title, m, rows))
        # ---------------- B
        ga = R[R.method == 'greedy_arrival']
        gr = X[X.method == 'greedy']
        print(f'-- B. Greedy in arrival order (n = {len(ga)}) --')
        dcov, dg = paired(ga, gr, 'coverage_rate'), paired(ga, gr, 'gini_elig_hourly')
        da, dl = paired(ga, gr, 'share_active_elig'), paired(ga, gr, 'overage_mean')
        print(f'  arrival - least-served: coverage {ci(dcov)}  F_G {ci(dg)}  active {ci(da)}  lateness {dl.mean():+.2f}')
        ma, mg = means(ga), means(gr)
        oc = X[X.method.isin(['ilp', 'hier', 'brkga', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05'])]
        oc_g = oc.groupby('method').apply(lambda d: d.groupby('instance').gini_elig_hourly.mean().mean())
        gap = (oc_g.min() - ma.gini_elig_hourly) / (oc_g.min() - mg.gini_elig_hourly)
        comp = {al: ((ga.gini_elig_hourly <= al).mean(), (gr.gini_elig_hourly <= al).mean()) for al in (0.30, 0.35, 0.40, 0.45)}
        print(f'  means: arrival F_G {ma.gini_elig_hourly:.3f} active {ma.share_active_elig:.2f} cov {ma.coverage_rate:.3f} | '
              f'least-served F_G {mg.gini_elig_hourly:.3f} active {mg.share_active_elig:.2f} | best order-centric F_G {oc_g.min():.3f}')
        print(f'  share of the Greedy advantage kept in arrival order: {gap:.2f}')
        print('  compliance arrival / least-served: ' + ', '.join(f'{al:.2f}: {a:.0%}/{b:.0%}' for al, (a, b) in comp.items()))
        lines['B'].append((title, ma, mg, oc_g.min(), dcov, dg, da, dl, comp))
        # ---------------- C
        print('-- C. fleet thinned to 1/3 (seeds 1-5) --')
        X5 = X[X.seed <= 5]
        pairs = (('greedy_thin', X5[X5.method == 'greedy'], r'\textbf{Greedy}'),
                 ('brkga_fair_w40_thin', X5[X5.method == 'brkga_fair_w40'], r'\textbf{BRKGA-Fair} ($\gamma = 40$)'),
                 ('brkga_fair_w40_xk25_thin', G[G.method == 'brkga_fair_w40_xk25'], r'\textbf{BRKGA-Fair} ($\gamma = 40$, $k_d = 25$)'))
        rowsC = []
        thin_g = {}
        for meth, full, lab in pairs:
            th = R[R.method == meth]
            keys = set(map(tuple, th[KEY].values))
            full = full[[k in keys for k in map(tuple, full[KEY].values)]]   # same (instance, seed) pairs
            mt, mf = means(th), means(full)
            thin_g[meth] = (mt.gini_elig_hourly, mf.gini_elig_hourly)
            print(f'  {meth:26s} n={len(th):3d}  cov {mf.coverage_rate:.3f} -> {mt.coverage_rate:.3f}   F_G {mf.gini_elig_hourly:.3f} -> '
                  f'{mt.gini_elig_hourly:.3f}   active {mf.share_active_elig:.2f} -> {mt.share_active_elig:.2f}   '
                  f'F_D {mf.F_Deficit:.3f} -> {mt.F_Deficit:.3f}   median COP/h {full.median_hourly.mean():.0f} -> {th.median_hourly.mean():.0f}   '
                  f'late {mf.overage_mean:.1f} -> {mt.overage_mean:.1f}')
            rowsC.append(f'{lab} & {mf.coverage_rate:.3f} & {mt.coverage_rate:.3f} & {mf.gini_elig_hourly:.3f} & {mt.gini_elig_hourly:.3f} & '
                         f'{mf.share_active_elig:.2f} & {mt.share_active_elig:.2f} & {full.median_hourly.mean():.0f} & {th.median_hourly.mean():.0f} & '
                         f'{mf.F_Deficit:.3f} & {mt.F_Deficit:.3f} \\\\')
        g_t, g_f = thin_g['greedy_thin']
        p_t, p_f = thin_g['brkga_fair_w40_thin']
        x_t, x_f = thin_g['brkga_fair_w40_xk25_thin']
        print(f'  gap order-centric - Greedy: full fleet {p_f - g_f:.3f}, thinned {p_t - g_t:.3f}; '
              f'gap closed by k_d = 25: full {1 - (x_f - g_f) / (p_f - g_f):.2f}, thinned {1 - (x_t - g_t) / (p_t - g_t):.2f}')
        lines['C'].append((title, rowsC, (g_f, g_t, p_f, p_t, x_f, x_t)))

    os.makedirs(TAB, exist_ok=True)
    with open(TAB + 'review2_ilp.tex', 'w', encoding='utf-8') as f:
        for title, m, rows in lines['A']:
            f.write(r'\multicolumn{4}{l}{\textit{' + title + r'}} \\' + '\n' + '\n'.join(rows) + '\n')
            if title.startswith('Manual'):
                f.write(r'\hline' + '\n')
    with open(TAB + 'review2_thin.tex', 'w', encoding='utf-8') as f:
        for title, rowsC, _ in lines['C']:
            f.write(r'\multicolumn{11}{l}{\textit{' + title + r'}} \\' + '\n' + '\n'.join(rowsC) + '\n')
            if title.startswith('Manual'):
                f.write(r'\hline' + '\n')
    with open(TAB + 'review2_arrival.tex', 'w', encoding='utf-8') as f:
        for title, ma, mg, ocmin, dcov, dg, da, dl, comp in lines['B']:
            f.write(f"{title} & {mg.gini_elig_hourly:.3f} & {ma.gini_elig_hourly:.3f} & {tex_ci(dg)} & {mg.share_active_elig:.2f} & "
                    f"{ma.share_active_elig:.2f} & {tex_ci(dcov)} & ${dl.mean():+.1f}$ & {100 * comp[0.40][1]:.0f} & {100 * comp[0.40][0]:.0f} & {ocmin:.3f} \\\\\n")
    print('\nwrote tables/review2_{ilp,arrival,thin}.tex')


if __name__ == '__main__':
    main()
