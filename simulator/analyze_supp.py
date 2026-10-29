"""Read of X3 supp (ablations of the supplement + E11 k_d = 50), paired by (instance, seed, regime) with the
base configuration of each ablation: first-generation parents from X1 (main.csv) and the k_d = 25 variants
from X3 gen2 (gen2.csv). Works on a partial supp.csv (rows still being produced): every parent is restricted
to the (instance, seed) pairs the ablation has, so the means are comparable.

Prints, per regime: mean table (columns of Table tab:gen2), paired deltas vs parent (mean, 95% CI), count of
pairs worse than the parent, days with F_Gini <= 0.40, per-seed means; for the k_d = 50 rows also the gap to
Greedy closed from the first-generation grandparent, and the k_d curve {0, 8, 25, 50}. Writes the LaTeX body
of the appendix table to output/paper/tables/ablations.tex.

    python analyze_supp.py > output/paper/supp_analysis.txt
"""
import numpy as np
import pandas as pd

OUT = r'C:/MDRP/simulator/output/paper/'
COLS = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig', 'p25_elig_hourly']
KEY = ['instance', 'seed']
# ablation -> (parent key, source of the parent, label for the table)
ABL = {
    'brkga_finish':           ('brkga', 'main', r'\textbf{BRKGA} decoder score$_{\text{finish}}$ (base: finish per order)'),
    'brkga_p20g20':           ('brkga', 'main', r'\textbf{BRKGA} $20 \times 20$ (base: $10 \times 10$)'),
    'brkga_fair_w10_total':   ('brkga_fair_w10', 'main', r'\textbf{BRKGA-Fair} ($w = 10$) total-earnings basis (base: hourly)'),
    'mipfair_a030_idle':      ('mipfair_a030', 'main', r'\textbf{MIP-Fair} Gini over free couriers only (base: all connected)'),
    'mipfair_a030_total':     ('mipfair_a030', 'main', r'\textbf{MIP-Fair} total-earnings basis (base: hourly)'),
    'mipfair_a030_fairfirst': ('mipfair_a030', 'main', r'\textbf{MIP-Fair} equity-first priority (base: coverage first)'),
    'mipfair_a030_k25':       ('mipfair_a030', 'main', r'\textbf{MIP-Fair} prefilter $k = 25$ (base: $k = 8$)'),
    'mipfair_a030_slack002':  ('mipfair_a030', 'main', r'\textbf{MIP-Fair} coverage slack $\varepsilon = 0.02$ (base: $0$)'),
    'mipfair_a030_slack005':  ('mipfair_a030', 'main', r'\textbf{MIP-Fair} coverage slack $\varepsilon = 0.05$ (base: $0$)'),
    'brkga_fair_w40_xk50':    ('brkga_fair_w40_xk25', 'gen2', r'\textbf{BRKGA-Fair} ($w = 40$, exposure) $k_d = 50$ (base: $k_d = 25$)'),
    'mipfair_a030_xk50_e000': ('mipfair_a030_xk25_e000', 'gen2', r'\textbf{MIP-Fair} ($\alpha = 0.30$, exposure) $k_d = 50$ (base: $k_d = 25$)'),
}
GRAND = {'brkga_fair_w40_xk50': 'brkga_fair_w40', 'mipfair_a030_xk50_e000': 'mipfair_a030'}
KD_CURVE = {'brkga_fair_w40': [('brkga_fair_w40', 'main', 0), ('brkga_fair_w40_xk25', 'gen2', 25), ('brkga_fair_w40_xk50', 'supp', 50)],
            'mipfair_a030': [('mipfair_a030', 'main', 0), ('mipfair_a030_xk_e000', 'gen2', 8),
                             ('mipfair_a030_xk25_e000', 'gen2', 25), ('mipfair_a030_xk50_e000', 'supp', 50)]}
MET = ['coverage_rate', 'gini_elig_hourly', 'share_active_elig', 'gini_elig_active_hourly', 'overage_mean',
       'F_Deficit', 'pay_pct', 'wall_min']


def ci(x: pd.Series) -> str:
    x = x.dropna()
    if len(x) < 2:
        return 'n/a'
    h = 1.96 * x.std(ddof=1) / np.sqrt(len(x))
    return f'{x.mean():+.3f} [{x.mean() - h:+.3f},{x.mean() + h:+.3f}]'


def load(name: str) -> pd.DataFrame:
    d = pd.read_csv(OUT + f'{name}.csv').merge(pd.read_csv(OUT + f'{name}_couriers.csv')[COLS], on='run_id')
    d['pay_pct'] = 100.0 * d['total_payment'] / (d['n_delivered'] * 2200.0)
    d['wall_min'] = d['wall_clock_sec'] / 60.0
    return d


def main() -> None:
    src = {k: load(k) for k in ('main', 'gen2', 'supp')}
    supp = src['supp']
    print(f"supp rows {len(supp)} ({supp.method.nunique()} configs, seeds {sorted(supp.seed.unique())}); "
          f"rows per config: {supp.groupby('method').size().to_dict()}")
    pd.set_option('display.width', 250)
    tex = []
    for reg in ('manual', 'autoaccept'):
        s = supp[supp.regime == reg]
        if s.empty:
            continue
        print(f'\n===================== {reg} =====================')
        mean_rows, pair_rows = [], []
        tex.append(r'\multicolumn{11}{l}{\textit{%s regime}} \\' % ('Manual' if reg == 'manual' else 'Auto-accept'))
        for meth, (par, psrc, label) in ABL.items():
            x = s[s.method == meth].set_index(KEY)
            if x.empty:
                continue
            P = src[psrc]
            p = P[(P.regime == reg) & (P.method == par)].set_index(KEY).reindex(x.index)
            g = src['main'][(src['main'].regime == reg) & (src['main'].method == 'greedy')].set_index(KEY).reindex(x.index)
            for nm, d in ((par + ' (base)', p), (meth, x)):
                m = d[MET].mean()
                mean_rows.append({'config': nm, 'n': int(d.coverage_rate.notna().sum()), **{k: round(v, 3) for k, v in m.items()},
                                  'cov_se': round(d.coverage_rate.std(ddof=1) / np.sqrt(len(d)), 3),
                                  'gini_se': round(d.gini_elig_hourly.std(ddof=1) / np.sqrt(len(d)), 3),
                                  'wall_max': round(d.wall_min.max(), 1)})
            d_p = x.gini_elig_hourly - p.gini_elig_hourly
            d_c = x.coverage_rate - p.coverage_rate
            row = {'ablation': meth, 'base': par, 'n': len(x), 'dGini vs base': ci(d_p), 'dCov vs base': ci(d_c),
                   'dLate vs base': ci(x.overage_mean - p.overage_mean),
                   'worse Gini': int((d_p > 0.005).sum()), 'better Gini': int((d_p < -0.005).sum()),
                   'days<=0.40': f'{int((x.gini_elig_hourly <= 0.40).sum())}/{len(x)}',
                   'per-seed': ' '.join(f'{v:.3f}' for v in x.groupby(level='seed').gini_elig_hourly.mean().values),
                   'CPU x base': f'{x.wall_min.mean() / p.wall_min.mean():.1f}'}
            if meth in GRAND:
                gp = src['main'][(src['main'].regime == reg) & (src['main'].method == GRAND[meth])].set_index(KEY).reindex(x.index)
                gap_x = 1 - (x.gini_elig_hourly - g.gini_elig_hourly) / (gp.gini_elig_hourly - g.gini_elig_hourly)
                gap_p = 1 - (p.gini_elig_hourly - g.gini_elig_hourly) / (gp.gini_elig_hourly - g.gini_elig_hourly)
                row['gap closed (k50 | k25)'] = f'{gap_x.mean():.2f} | {gap_p.mean():.2f}'
                row['dGini vs greedy'] = ci(x.gini_elig_hourly - g.gini_elig_hourly)
            pair_rows.append(row)
            # LaTeX row: ablation against its base (paired)
            hp = 1.96 * d_p.std(ddof=1) / np.sqrt(len(d_p))
            hc = 1.96 * d_c.std(ddof=1) / np.sqrt(len(d_c))
            tex.append(f"{label} & {len(x)} & {x.coverage_rate.mean():.3f} & ${d_c.mean():+.3f}$ & "
                       f"{x.gini_elig_hourly.mean():.3f} & ${d_p.mean():+.3f}$ [{d_p.mean() - hp:+.3f}, {d_p.mean() + hp:+.3f}] & "
                       f"{int((d_p > 0.005).sum())}/{int((d_p < -0.005).sum())} & {x.share_active_elig.mean():.2f} & "
                       f"{x.gini_elig_active_hourly.mean():.3f} & {x.wall_min.mean():.1f} ({x.wall_min.max():.0f}) & "
                       f"{x.wall_min.mean() / p.wall_min.mean():.1f} \\\\")
        print(pd.DataFrame(mean_rows).to_string(index=False))
        print()
        print(pd.DataFrame(pair_rows).to_string(index=False))
        # k_d curve
        print(f'\n-- {reg}: k_d curve (mean F_Gini / coverage / min per run, on the (instance, seed) pairs of the k_d = 50 run) --')
        for fam, chain in KD_CURVE.items():
            idx = s[s.method == chain[-1][0]].set_index(KEY).index
            if len(idx) == 0:
                continue
            parts = []
            for key, sr, kd in chain:
                D = src[sr]
                d = D[(D.regime == reg) & (D.method == key)].set_index(KEY).reindex(idx)
                parts.append(f'k_d={kd}: {d.gini_elig_hourly.mean():.3f}/{d.coverage_rate.mean():.3f}/{d.wall_min.mean():.1f}')
            gd = src['main'][(src['main'].regime == reg) & (src['main'].method == 'greedy')].set_index(KEY).reindex(idx)
            print(f'  {fam:16s} n={len(idx):3d}  ' + '  '.join(parts) + f'  greedy: {gd.gini_elig_hourly.mean():.3f}/{gd.coverage_rate.mean():.3f}')
        tex.append(r'\hline')
    with open(OUT + 'tables/ablations.tex', 'w', encoding='utf-8') as f:
        f.write('\n'.join(tex) + '\n')
    print(f'\nLaTeX body written to {OUT}tables/ablations.tex ({len(tex)} lines)')


if __name__ == '__main__':
    main()
