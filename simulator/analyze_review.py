"""Appendix tables added after the referee-style review (2026-10-31): paired read of the second generation
against its parent (Delta F_G and Delta coverage with 95% intervals, gap closed as a ratio of means, compliance),
the metrics recorded but not reported in the main tables (max-min fairness, order-count Gini, click-to-door,
solve time per round) and the emissions diagnostic behind Figure F8 (km and kg per delivered order, vehicle shares).

    python analyze_review.py            -> output/paper/tables/review_{gen2,metrics,emissions}.tex

Intervals are 95% intervals of the paired mean (1.96 x SE over the (instance, seed) pairs), as in analyze_gen2_final.
"""
import os
import sys

import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
TAB = OUT + 'tables/'
FIG = r'C:/MDRP/docs/paper-cmdp/paper/figures/'
COLS = ['run_id', 'gini_elig_hourly', 'share_active_elig']
KEY = ['instance', 'seed']
PARENT = {'brkga_fair_w20_x': 'brkga_fair_w20', 'brkga_fair_w20_xk': 'brkga_fair_w20',
          'brkga_fair_w40_xk25': 'brkga_fair_w40', 'paybrkga_l05_xk': 'paybrkga_l05'}
LABEL = {
    'brkga_fair_w20_x': r'\textbf{BRKGA-Fair} ($\gamma = 20$) exposure basis',
    'brkga_fair_w20_xk': r'\textbf{BRKGA-Fair} ($\gamma = 20$) exposure, $k_d = 8$',
    'brkga_fair_w40_xk25': r'\textbf{BRKGA-Fair} ($\gamma = 40$) exposure, $k_d = 25$',
    'mipfair_a030_x_e000': r'\textbf{MIP-Fair} ($\alpha = 0.30$) exposure basis',
    'mipfair_a030_xk_e000': r'\textbf{MIP-Fair} ($\alpha = 0.30$) exposure, $k_d = 8$',
    'mipfair_a030_xk_e005': r'\textbf{MIP-Fair} ($\alpha = 0.30$) exposure, $k_d = 8$, $\varepsilon = 0.05$',
    'mipfair_a030_xk25_e000': r'\textbf{MIP-Fair} ($\alpha = 0.30$) exposure, $k_d = 25$',
    'paybrkga_l05_xk': r'\textbf{Pay-BRKGA} ($\lambda_{\text{pay}} = 0.5$) exposure, $k_d = 8$',
}
ORDER = ['brkga_fair_w20_x', 'brkga_fair_w20_xk', 'brkga_fair_w40_xk25', 'mipfair_a030_x_e000',
         'mipfair_a030_xk_e000', 'mipfair_a030_xk_e005', 'mipfair_a030_xk25_e000', 'paybrkga_l05_xk']
MAIN = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05']
NAME = {'greedy': r'\textbf{Greedy}', 'ilp': r'\textbf{ILP}', 'hier': r'\textbf{Hierarchical}', 'brkga': r'\textbf{BRKGA}',
        'brkga_fair_w40': r'\textbf{BRKGA-Fair} ($\gamma = 40$)', 'mipfair_a030': r'\textbf{MIP-Fair} ($\alpha = 0.30$)',
        'paybrkga_l05': r'\textbf{Pay-BRKGA} ($\lambda_{\text{pay}} = 0.5$)'}
REG = (('manual', 'Manual regime'), ('autoaccept', 'Auto-accept regime'))


def ci(x: pd.Series) -> str:
    x = x.dropna()
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'${x.mean():+.3f}$ [{x.mean() - h:+.3f}, {x.mean() + h:+.3f}]'


def gen2_table() -> str:
    main_df = pd.read_csv(OUT + 'main.csv', low_memory=False).merge(pd.read_csv(OUT + 'main_couriers.csv')[COLS], on='run_id')
    gen2 = pd.read_csv(OUT + 'gen2.csv', low_memory=False).merge(pd.read_csv(OUT + 'gen2_couriers.csv')[COLS], on='run_id')
    m = main_df[main_df.seed.isin(sorted(gen2.seed.unique()))]
    lines = []
    for reg, title in REG:
        lines.append(r'\multicolumn{8}{l}{\textit{' + title + r'}} \\')
        base = m[(m.regime == reg) & (m.method == 'greedy')].set_index(KEY)
        for meth in ORDER:
            x = gen2[(gen2.regime == reg) & (gen2.method == meth)].set_index(KEY).reindex(base.index)
            par = PARENT.get(meth, 'mipfair_a030')
            p = m[(m.regime == reg) & (m.method == par)].set_index(KEY).reindex(base.index)
            ok = x.gini_elig_hourly.notna()
            gap = 1 - (x.gini_elig_hourly[ok].mean() - base.gini_elig_hourly[ok].mean()) / \
                (p.gini_elig_hourly[ok].mean() - base.gini_elig_hourly[ok].mean())
            c40 = (x.gini_elig_hourly[ok] <= 0.40).mean() * 100
            c45 = (x.gini_elig_hourly[ok] <= 0.45).mean() * 100
            lines.append(f"{LABEL[meth]} & {int(ok.sum())} & {ci(x.gini_elig_hourly - p.gini_elig_hourly)} & "
                         f"{ci(x.coverage_rate - p.coverage_rate)} & ${(x.overage_mean - p.overage_mean).mean():+.1f}$ & "
                         f"{100 * gap:.0f} & {c40:.0f} & {c45:.0f} \\\\")
        if reg == 'manual':
            lines.append(r'\hline')
    return '\n'.join(lines) + '\n'


def metrics_table() -> str:
    d = pd.read_csv(OUT + 'main.csv', low_memory=False)
    cnt = d.groupby('seed')['run_id'].count()
    d = d[d.seed.isin(cnt[cnt == cnt.max()].index)]
    lines = []
    for reg, title in REG:
        lines.append(r'\multicolumn{7}{l}{\textit{' + title + r'}} \\')
        sub = d[(d.regime == reg) & d.method.isin(MAIN)]
        inst = sub.groupby(['method', 'instance'])[['F_MaxMin', 'c2d_mean', 'c2d_p90', 'solve_mean', 'solve_max']].mean()
        agg = inst.groupby('method').mean()
        mx = sub.groupby('method')['solve_max'].max()
        for meth in MAIN:
            r = agg.loc[meth]
            lines.append(f"{NAME[meth]} & {r.F_MaxMin:.0f} & {r.c2d_mean:.1f} & {r.c2d_p90:.1f} & "
                         f"{r.solve_mean:.2f} & {mx[meth]:.1f} \\\\")
        if reg == 'manual':
            lines.append(r'\hline')
    return '\n'.join(lines) + '\n'


def emissions_table() -> str:
    r = pd.read_csv(FIG + 'F8_emissions_runs.csv')
    r = r[r.method.isin(MAIN)]
    r['km_per_order'] = r.km_total / r.n_delivered
    for v in ('motorcycle', 'car', 'bicycle', 'walking'):
        r[f'sh_{v}'] = r[f'km_{v}'] / r.km_total
    inst = r.groupby(['method', 'instance'])[['km_per_order', 'kg_per_order', 'sh_motorcycle', 'sh_car', 'sh_bicycle', 'sh_walking']].mean()
    agg = inst.groupby('method').mean()
    lines = []
    for meth in MAIN:
        a = agg.loc[meth]
        lines.append(f"{NAME[meth]} & {a.km_per_order:.2f} & {a.kg_per_order:.3f} & {1000 * a.kg_per_order / a.km_per_order:.0f} & "
                     f"{100 * a.sh_motorcycle:.0f} & {100 * a.sh_car:.0f} & {100 * a.sh_bicycle:.0f} & {100 * a.sh_walking:.0f} \\\\")
    return '\n'.join(lines) + '\n'


def main() -> None:
    os.makedirs(TAB, exist_ok=True)
    which = sys.argv[1:] or ['gen2', 'metrics', 'emissions']
    for name, fn in (('gen2', gen2_table), ('metrics', metrics_table), ('emissions', emissions_table)):
        if name in which:
            body = fn()
            open(TAB + f'review_{name}.tex', 'w', encoding='utf-8').write(body)
            print(f'== review_{name}.tex ==')
            print(body)


if __name__ == '__main__':
    main()
