"""Rows of the tables that were filled from analysis printouts (2026-11-05, instance-1 rerun):
tab:sensitivity and tab:sensitivity_gini (regime and alpha columns from X1, or from X3 gen2 for the k_d = 25
variants; theta columns from X2 paired with theta = 903) and the zone statistics of tab:instances.

    python tables_extra.py [--data output/paper] [--out output/paper/tables]
writes sensitivity.tex, sensitivity_gini.tex and instances.tex. Values are relative differences, in %, of the mean
over instances (seeds averaged within each instance) against the base case of the same configuration.
"""
import argparse
import os

import pandas as pd

ROWS = [  # (method, label, source of the regime column)
    ('greedy', r'\textbf{Greedy}', 'main'),
    ('hier', r'\textbf{Hierarchical}', 'main'),
    ('mipfair_a030', r'\textbf{MIP-Fair} ($\alpha = 0.30$)', 'main'),
    ('brkga_fair_w40_xk25', r'\textbf{BRKGA-Fair} ($\gamma = 40$, $k_d = 25$)', 'gen2'),
    ('mipfair_a030_xk25_e000', r'\textbf{MIP-Fair} ($\alpha = 0.30$, $k_d = 25$)', 'gen2'),
    ('paybrkga_l05', r'\textbf{Pay-BRKGA} ($\lambda_{\text{pay}} = 0.5$)', 'main'),
]
X2 = {'greedy', 'hier', 'brkga_fair_w40_xk25', 'mipfair_a030_xk25_e000', 'paybrkga_l05'}


def load(data, stem):
    d = pd.read_csv(os.path.join(data, stem + '.csv'), low_memory=False)
    c = pd.read_csv(os.path.join(data, stem + '_couriers.csv'))[['run_id', 'gini_elig_hourly']]
    return d.merge(c, on='run_id', how='inner')


def level(d, col):
    return d.groupby('instance')[col].mean().mean()


def fmt(v):
    if v is None:
        return '--'
    r = round(v, 1)
    if abs(r) < 0.05:
        return '0.0'
    return f'+{r:.1f}' if r > 0 else f'${r:.1f}$'


def rows_for(col, main, gen2, thr):
    out = []
    for meth, lab, src in ROWS:
        d = main if src == 'main' else gen2
        man = level(d[(d.method == meth) & (d.regime == 'manual')], col)
        aut = level(d[(d.method == meth) & (d.regime == 'autoaccept')], col)
        cells = ['0.0', fmt(100 * (aut / man - 1))]
        if meth in X2:
            base_src = main if meth in ('greedy', 'hier', 'paybrkga_l05') else gen2
            seeds = sorted(thr.seed.unique())
            t = thr[thr.method == meth]
            b = base_src[(base_src.method == meth) & (base_src.regime == 'manual') & base_src.seed.isin(seeds)]
            vals = []
            for th in (615.0, 1242.0):
                x = t[t.ppk_threshold == th]
                keys = set(zip(x.instance, x.seed))
                bb = b[[k in keys for k in zip(b.instance, b.seed)]]
                vals.append(100 * (x[col].mean() / bb[col].mean() - 1))   # pooled over pairs, as analyze_x2.py
            cells += [fmt(vals[0]), '0.0', fmt(vals[1])]
        else:
            cells += ['--', '0.0', '--']
        if meth == 'mipfair_a030':
            base = level(main[(main.method == 'mipfair_a030') & (main.regime == 'manual')], col)
            for m in ('mipfair_a020', 'mipfair_a030', 'mipfair_a040'):
                cells.append(fmt(100 * (level(main[(main.method == m) & (main.regime == 'manual')], col) / base - 1)))
        else:
            cells += ['--', '--', '--']
        out.append(f'{lab} & ' + ' & '.join(cells) + r' \\')
    return '\n'.join(out) + '\n'


def instances_rows(data):
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from batch_paper import DEFAULT_INSTANCES_DIR
    from config import Config
    from loader_real import load_real_instance
    tab = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'paper-cmdp', 'instancias_reales.csv'))
    out = []
    for _, r in tab.iterrows():
        d = load_real_instance(f"Instancia_{int(r['inst'])}", DEFAULT_INSTANCES_DIR,
                               Config(seed=1, real_max_radius_km=3.0, real_circuity=1.3, max_bundle_size=3))
        o, c = len(d['orders']), len(d['couriers'])
        s = len(d['stores'])
        out.append(f"{int(r['inst'])},{r['city']},{o},{c},{s},{o / c:.1f},{int(r['pct_bicycle'])}/{int(r['pct_moto'])}/{int(r['pct_walk'])}/{int(r['pct_car'])}")
    return '\n'.join(out) + '\n'


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(here, 'output', 'paper'))
    ap.add_argument('--out', default=os.path.join(here, 'output', 'paper', 'tables'))
    ap.add_argument('--instances', action='store_true', help='also write instances.csv (loads the 24 zones)')
    a = ap.parse_args()
    main_df, gen2, thr = load(a.data, 'main'), load(a.data, 'gen2'), load(a.data, 'threshold')
    os.makedirs(a.out, exist_ok=True)
    for name, col in (('sensitivity', 'coverage_rate'), ('sensitivity_gini', 'gini_elig_hourly')):
        body = rows_for(col, main_df, gen2, thr)
        open(os.path.join(a.out, name + '.tex'), 'w', encoding='utf-8').write(body)
        print(f'== {name}\n{body}')
    if a.instances:
        body = instances_rows(a.data)
        open(os.path.join(a.out, 'instances.csv'), 'w', encoding='utf-8').write('inst,city,orders,couriers,stores,opc,mix\n' + body)
        print(body)


if __name__ == '__main__':
    main()
