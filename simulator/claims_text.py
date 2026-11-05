"""Recompute, from the run tables, every number the prose of main.tex cites (instance-1 rerun, 2026-11-05).
Grouped by the sentence that uses it; prints values at full precision for the editor to round.

    python claims_text.py [--data output/paper]
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')
COLS = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'share_active_elig', 'p25_elig_hourly', 'share_elig', 'median_hourly']
FIRST = ['ilp', 'hier', 'brkga', 'brkga_fair_w5', 'brkga_fair_w10', 'brkga_fair_w20', 'brkga_fair_w40', 'mipfair_a020', 'mipfair_a025',
         'mipfair_a030', 'mipfair_a035', 'mipfair_a040', 'mipfair_a100', 'paybrkga_l01', 'paybrkga_l02', 'paybrkga_l05', 'paybrkga_l10']
SWEEPS = [m for m in FIRST if m.startswith(('brkga_fair', 'mipfair', 'paybrkga'))]
KEY = ['instance', 'seed']


def load(d, stem):
    x = pd.read_csv(os.path.join(d, stem + '.csv'), low_memory=False)
    c = pd.read_csv(os.path.join(d, stem + '_couriers.csv'))
    return x.merge(c[[k for k in COLS if k in c.columns]], on='run_id', how='inner')


def lv(df, col):
    return df.groupby('instance')[col].mean().mean()


def sel(df, m, r):
    return df[(df.method == m) & (df.regime == r)]


def gap(var, par, g, col='gini_elig_hourly'):
    keys = set(map(tuple, var[KEY].values))
    f = lambda d: d[[k in keys for k in map(tuple, d[KEY].values)]]
    v, p, b = lv(var, col), lv(f(par), col), lv(f(g), col)
    return 1 - (v - b) / (p - b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'paper'))
    a = ap.parse_args()
    X, G, S, R, T = (load(a.data, s) for s in ('main', 'gen2', 'supp', 'review', 'threshold'))
    X5 = X[X.seed <= 5]
    out = []
    P = lambda *s: out.append(' '.join(str(z) for z in s))
    for r in ('manual', 'autoaccept'):
        P(f'\n######## {r}')
        g = lv(sel(X, 'greedy', r), 'gini_elig_hourly')
        oc = {m: lv(sel(X, m, r), 'gini_elig_hourly') for m in FIRST}
        P('Greedy FG', round(g, 4), '| order-centric FG min', min(oc, key=oc.get), round(min(oc.values()), 4), 'max', max(oc, key=oc.get), round(max(oc.values()), 4))
        P('  sweeps FG range', round(min(oc[m] for m in SWEEPS), 4), round(max(oc[m] for m in SWEEPS), 4))
        cov = {m: lv(sel(X, m, r), 'coverage_rate') for m in FIRST + ['greedy']}
        P('coverage', {m: round(v, 4) for m, v in cov.items() if m in ('greedy', 'ilp', 'brkga', 'brkga_fair_w40', 'hier', 'mipfair_a030', 'paybrkga_l05')})
        P('  best order-centric - greedy (pts)', round(100 * (max(v for m, v in cov.items() if m not in ('greedy', 'ilp')) - cov['greedy']), 2),
          '| spread incl ILP', round(100 * (max(cov.values()) - min(cov.values())), 2))
        gr = sel(X, 'greedy', r).set_index(KEY)
        d = {m: (sel(X, m, r).set_index(KEY).reindex(gr.index).gini_elig_hourly - gr.gini_elig_hourly) for m in FIRST}
        mins = {m: v.groupby(level=0).mean() for m, v in d.items()}
        P('  paired FG diff vs greedy (instance means) min', round(min(v.mean() for v in mins.values()), 4), 'max', round(max(v.mean() for v in mins.values()), 4))
        act = {m: lv(sel(X, m, r), 'share_active_elig') for m in ('greedy', 'brkga', 'brkga_fair_w5', 'brkga_fair_w40')}
        P('  active', {m: round(v, 3) for m, v in act.items()})
        P('  FD range all configs', round(min(lv(sel(X, m, r), 'F_Deficit') for m in FIRST + ['greedy']), 4), round(max(lv(sel(X, m, r), 'F_Deficit') for m in FIRST + ['greedy']), 4))
        P('  MIP alpha FG range', [round(lv(sel(X, m, r), 'gini_elig_hourly'), 4) for m in FIRST if m.startswith('mipfair')])
        P('  BRKGA-Fair gamma FG', [round(lv(sel(X, m, r), 'gini_elig_hourly'), 4) for m in ('brkga_fair_w5', 'brkga_fair_w10', 'brkga_fair_w20', 'brkga_fair_w40')])
        P('  share eligible (greedy)', round(lv(sel(X, 'greedy', r), 'share_elig'), 4))
        P('  compliance greedy', {al: round(100 * (sel(X, 'greedy', r).gini_elig_hourly <= al).mean(), 1) for al in (0.30, 0.35, 0.40)})
        # regime loss
        if r == 'manual':
            P('regime loss pts', {m: round(100 * (lv(sel(X, m, 'autoaccept'), 'coverage_rate') - lv(sel(X, m, 'manual'), 'coverage_rate')), 2)
                                  for m in ('greedy', 'ilp', 'brkga', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05', 'hier')})
        # second generation
        P('-- gen2 (5 seeds)')
        g5 = sel(X5, 'greedy', r)
        for v, p in (('brkga_fair_w20_x', 'brkga_fair_w20'), ('brkga_fair_w20_xk', 'brkga_fair_w20'), ('brkga_fair_w40_xk25', 'brkga_fair_w40'),
                     ('mipfair_a030_x_e000', 'mipfair_a030'), ('mipfair_a030_xk_e000', 'mipfair_a030'), ('mipfair_a030_xk_e005', 'mipfair_a030'),
                     ('mipfair_a030_xk25_e000', 'mipfair_a030'), ('paybrkga_l05_xk', 'paybrkga_l05')):
            vv, pp = sel(G, v, r), sel(X5, p, r)
            dg = (vv.set_index(KEY).gini_elig_hourly - pp.set_index(KEY).reindex(vv.set_index(KEY).index).gini_elig_hourly)
            dc = (vv.set_index(KEY).coverage_rate - pp.set_index(KEY).reindex(vv.set_index(KEY).index).coverage_rate)
            dl = (vv.set_index(KEY).overage_mean - pp.set_index(KEY).reindex(vv.set_index(KEY).index).overage_mean)
            P(f'  {v:24s} FG {lv(vv, "gini_elig_hourly"):.4f} dFG {dg.mean():+.4f} dcov {dc.mean():+.4f} dlate {dl.mean():+.2f} gap {gap(vv, pp, g5):.3f} '
              f'active {lv(vv, "share_active_elig"):.3f} cpu {vv.wall_clock_sec.mean() / 60:.1f} max {vv.wall_clock_sec.max() / 60:.0f} '
              f'c40 {100 * (vv.gini_elig_hourly <= 0.40).mean():.0f} c45 {100 * (vv.gini_elig_hourly <= 0.45).mean():.0f} c50 {100 * (vv.gini_elig_hourly <= 0.50).mean():.0f} c30 {100 * (vv.gini_elig_hourly <= 0.30).mean():.0f}')
        # k_d = 50
        for v, p, gp in (('brkga_fair_w40_xk50', 'brkga_fair_w40_xk25', 'brkga_fair_w40'), ('mipfair_a030_xk50_e000', 'mipfair_a030_xk25_e000', 'mipfair_a030')):
            vv = sel(S, v, r)
            pp = sel(G, p, r)
            keys = set(map(tuple, vv[KEY].values))
            pp = pp[[k in keys for k in map(tuple, pp[KEY].values)]]
            P(f'  {v:24s} FG {lv(vv, "gini_elig_hourly"):.4f} (k25 {lv(pp, "gini_elig_hourly"):.4f}) cov {lv(vv, "coverage_rate"):.4f} (k25 {lv(pp, "coverage_rate"):.4f}) '
              f'gap from grandparent {gap(vv, sel(X5, gp, r), g5):.3f} c40 {100 * (vv.gini_elig_hourly <= 0.40).mean():.0f} cpu {vv.wall_clock_sec.mean() / 60:.1f} max {vv.wall_clock_sec.max() / 60:.0f} '
              f'cpu ratio {vv.wall_clock_sec.mean() / pp.wall_clock_sec.mean():.2f}')
    # threshold
    P('\n######## X2')
    for m in ('greedy', 'hier', 'brkga_fair_w40_xk25', 'mipfair_a030_xk25_e000', 'paybrkga_l05'):
        src = X if m in ('greedy', 'hier', 'paybrkga_l05') else G
        b = src[(src.method == m) & (src.regime == 'manual') & (src.seed <= 5)].set_index(KEY)
        for th in (615.0, 1242.0):
            t = T[(T.method == m) & (T.ppk_threshold == th)].set_index(KEY)
            bb = b.reindex(t.index)
            P(f'  {m:24s} {th:.0f} cov {100 * (t.coverage_rate.mean() / bb.coverage_rate.mean() - 1):+.2f}% pts {100 * (t.coverage_rate.mean() - bb.coverage_rate.mean()):+.2f} '
              f'FG {100 * (t.gini_elig_hourly.mean() / bb.gini_elig_hourly.mean() - 1):+.2f}% dFG {t.gini_elig_hourly.mean() - bb.gini_elig_hourly.mean():+.4f} '
              f'c45 {100 * (t.gini_elig_hourly <= 0.45).mean():.0f} base c45 {100 * (bb.gini_elig_hourly <= 0.45).mean():.0f} cov {t.coverage_rate.mean():.4f}')
    # review
    P('\n######## review')
    for r in ('manual', 'autoaccept'):
        for m in ('greedy_thin', 'brkga_fair_w40_thin', 'brkga_fair_w40_xk25_thin', 'greedy_arrival', 'ilp_k8'):
            x = sel(R, m, r)
            P(f'  {r:10s} {m:26s} FG {lv(x, "gini_elig_hourly"):.4f} cov {lv(x, "coverage_rate"):.4f} active {lv(x, "share_active_elig"):.3f} '
              f'c30 {100 * (x.gini_elig_hourly <= 0.30).mean():.0f} c25 {100 * (x.gini_elig_hourly <= 0.25).mean():.0f}')
    # pilot circuity
    P('\n######## pilot')
    p10 = pd.read_csv(os.path.join(a.data, 'pilot.csv'))
    p13 = pd.read_csv(os.path.join(a.data, 'pilot_c13.csv'))
    g10 = p10[p10.method == 'greedy'].set_index('instance').coverage_rate
    g13 = p13.set_index('instance').coverage_rate.reindex(g10.index)
    P('  pilot instances', sorted(p10.instance.unique()), 'cities', sorted(p10.city.unique()))
    P(f'  greedy coverage c1.0 {g10.mean():.4f} c1.3 {g13.mean():.4f} rel {100 * (g10.mean() / g13.mean() - 1):+.2f}%')
    # totals
    P('\n######## totals')
    tot = 0
    for s in ('pilot', 'pilot_c13', 'main', 'gen2', 'supp', 'threshold', 'review'):
        x = pd.read_csv(os.path.join(a.data, s + '.csv'), low_memory=False)
        col = 'child_wall_sec' if 'child_wall_sec' in x and x.child_wall_sec.notna().mean() > 0.5 else 'wall_clock_sec'
        tot += x[col].sum() / 3600
        P(f'  {s:10s} rows {len(x):5d} cpu_h {x[col].sum() / 3600:.1f}')
    P(f'  total cpu h {tot:.0f}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
