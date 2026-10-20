"""
compare_objectives.py -- read every policy (ours, the hier variants and the four
mdrp-sim ports) on the SAME instances and evaluate them on OUR four objectives,
whatever each policy optimised internally:

  P1 coverage   coverage_rate            (higher is better)
  P2 lateness   overage_total_min        (lower)   -- minutes over the target click-to-door
  P3 equity     F_Gini                   (lower)   -- plus F_Deficit / F_MaxMin as companions
  P4 cost       courier_active_min_total (lower)   -- minutes of courier time committed

Outputs: mean of each objective by policy (overall and by cluster), the
lexicographic winner per instance under each pass order, and paired
comparisons against a reference policy. Writes a markdown report and a JSON
block for the deck.

  python compare_objectives.py output/all_policies_240.csv output/mdrpsim_slow_240.csv \
         --md output/compare_objectives.md --json output/compare_objectives.json
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')   # Windows consoles default to cp1252

import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CLUSTER_LABELS = {0: 'Dispersas, con holgura', 1: 'Pequeñas y compactas',
                  2: 'Medianas y cargadas', 3: 'Grandes y saturadas'}
OBJ = {  # name -> (column, higher_is_better)
    'coverage': ('coverage_rate', True),
    'lateness': ('overage_total_min', False),
    'equity': ('F_Gini', False),
    'cost': ('courier_active_min_total', False),
}
ORDERS = {
    'cov›lat›eq›cost (1A)': ['coverage', 'lateness', 'equity', 'cost'],
    'cov›lat›cost›eq': ['coverage', 'lateness', 'cost', 'equity'],
    'cov›cost›lat›eq': ['coverage', 'cost', 'lateness', 'equity'],
    'cov›eq›lat›cost': ['coverage', 'equity', 'lateness', 'cost'],
}
PRETTY = {'greedy': 'greedy', 'fair_greedy': 'fair_greedy', 'hier': 'hier cov›lat›eq›cost',
          'hier[cov,lat,cost,eq]': 'hier cov›lat›cost›eq', 'hier[cov,cost,lat,eq]': 'hier cov›cost›lat›eq',
          'mdrpsim_greedy': 'mdrp-sim greedy', 'mdrpsim_mip': 'mdrp-sim mdrp (MIP)',
          'mdrpsim_graph': 'mdrp-sim mdrp_graph', 'mdrpsim_graph_prospects': 'mdrp-sim mdrp_graph_prospects'}


def load(csvs):
    df = pd.concat([pd.read_csv(c) for c in csvs], ignore_index=True)
    if 'failed' in df.columns:
        df = df[df['failed'].isna()]
    cl = pd.read_csv(os.path.join(THIS_DIR, 'instance_clusters.csv'))[['instance', 'cluster']]
    df = df.drop(columns=[c for c in ('cluster',) if c in df.columns]).merge(cl, on='instance', how='left')
    df = df.drop_duplicates(subset=['instance', 'policy'], keep='last')
    return df


def lexi_winners(df, order, tol=1e-9):
    """Per instance: policy that wins lexicographically on the given order (ties keep all)."""
    wins = {}
    for inst, g in df.groupby('instance'):
        g = g.set_index('policy')
        cand = list(g.index)
        for name in order:
            col, hib = OBJ[name]
            vals = g.loc[cand, col]
            best = vals.max() if hib else vals.min()
            cand = [p for p in cand if abs(g.loc[p, col] - best) <= tol]
            if len(cand) == 1:
                break
        for p in cand:
            wins[p] = wins.get(p, 0) + 1.0 / len(cand)
    return wins


def fmt_table(df, by):
    cols = ['coverage_rate', 'overage_total_min', 'overage_mean', 'F_Gini', 'F_Deficit', 'courier_active_min_total',
            'bundle_size_mean', 'total_payment', 'wall_clock_sec']
    cols = [c for c in cols if c in df.columns]
    t = df.groupby(by)[cols].mean()
    return t


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csvs', nargs='+')
    ap.add_argument('--reference', default='greedy')
    ap.add_argument('--md', default=None)
    ap.add_argument('--json', default=None)
    args = ap.parse_args(argv)

    df = load(args.csvs)
    pols = [p for p in PRETTY if p in set(df['policy'])] + sorted(set(df['policy']) - set(PRETTY))
    # only instances where EVERY policy ran, so the comparison is paired
    counts = df.groupby('instance')['policy'].nunique()
    complete = counts[counts == len(pols)].index
    dfc = df[df['instance'].isin(complete)]
    out = []
    out.append(f"# Nuestros objetivos sobre todas las políticas\n\n{len(pols)} políticas · {len(complete)} instancias con todas las políticas (de {df['instance'].nunique()})\n")
    pd.set_option('display.width', 250)
    pd.set_option('display.max_columns', 30)

    overall = fmt_table(dfc, 'policy').reindex(pols)
    overall.index = [PRETTY.get(p, p) for p in overall.index]
    out.append("## Media de cada objetivo por política (todas las instancias)\n")
    out.append(overall.round(4).to_markdown())
    out.append("")

    out.append("## Ganador lexicográfico por instancia (empates repartidos)\n")
    win_rows = []
    for oname, order in ORDERS.items():
        w = lexi_winners(dfc, order)
        row = {'orden': oname}
        for p in pols:
            row[PRETTY.get(p, p)] = round(100 * w.get(p, 0) / len(complete), 1)
        win_rows.append(row)
    wins_df = pd.DataFrame(win_rows).set_index('orden')
    out.append("Porcentaje de instancias que gana cada política cuando se lee con cada orden de pasadas:\n")
    out.append(wins_df.to_markdown())
    out.append("")

    out.append("## Por cluster\n")
    percl = {}
    for c in sorted(dfc['cluster'].dropna().unique()):
        g = dfc[dfc['cluster'] == c]
        t = fmt_table(g, 'policy').reindex(pols)
        t.index = [PRETTY.get(p, p) for p in t.index]
        out.append(f"### Cluster {int(c)} · {CLUSTER_LABELS.get(int(c), '')} · {g['instance'].nunique()} instancias\n")
        out.append(t[['coverage_rate', 'overage_total_min', 'F_Gini', 'courier_active_min_total', 'wall_clock_sec']].round(4).to_markdown())
        out.append("")
        percl[int(c)] = t.round(4).to_dict(orient='index')

    ref = args.reference
    out.append(f"## Pareado frente a {ref}: media de la diferencia y % de instancias donde la política es mejor\n")
    piv = dfc.pivot_table(index='instance', columns='policy', values=[OBJ[k][0] for k in OBJ])
    pr = []
    for p in pols:
        if p == ref:
            continue
        row = {'política': PRETTY.get(p, p)}
        for k, (col, hib) in OBJ.items():
            d = piv[col][p] - piv[col][ref]
            better = (d > 1e-9) if hib else (d < -1e-9)
            row[f'Δ {k}'] = round(d.mean(), 4)
            row[f'mejor {k} %'] = round(100 * better.mean(), 1)
        pr.append(row)
    paired = pd.DataFrame(pr).set_index('política')
    out.append(paired.to_markdown())
    out.append("")

    text = '\n'.join(out)
    print(text)
    if args.md:
        with open(args.md, 'w', encoding='utf8') as f:
            f.write(text)
    if args.json:
        with open(args.json, 'w', encoding='utf8') as f:
            json.dump({'n_instances': int(len(complete)), 'policies': [PRETTY.get(p, p) for p in pols],
                       'overall': overall.round(4).to_dict(orient='index'),
                       'wins': wins_df.to_dict(orient='index'),
                       'per_cluster': percl,
                       'paired_vs': {ref: paired.to_dict(orient='index')}}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
