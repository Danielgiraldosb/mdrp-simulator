"""LaTeX table bodies and prose numbers for the paper from X1 (and later X3) results.

Reads the run table (main.csv) and the per-run courier metrics (main_couriers.csv, from
analyze_couriers.py --out) and writes, into --out-dir:

  benchmark.tex   rows of tab:benchmark (both regimes, one configuration per policy)
  scope.tex       rows of tab:scope (manual regime)
  compliance.tex  rows of tab:compliance (both regimes)
  stats.txt       the numbers quoted in the prose: paired differences vs Greedy with bootstrap
                  intervals, by-city Gini, regime loss, parameter sensitivity, compliance of
                  every configuration, CPU maxima

The primary statistic is the end-of-day Gini of hourly earnings over the eligible couriers
(E9: connected >= 1 h, idle at zero), taken from the courier table; the active-courier Gini of
the run table is kept as F_Gini^act. Seeds are restricted to those complete for every cell
unless --all-seeds is given. Extra run tables (X3) can be appended with more positional paths;
they must have matching courier tables (same basename + _couriers.csv) or be covered by one
--couriers-table that contains their run_ids.

Usage (from simulator/):
  python tables_paper.py output/paper/main.csv --couriers-table output/paper/main_couriers.csv
"""
from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List

import numpy as np
import pandas as pd

CONFIGS = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w20', 'mipfair_a030', 'paybrkga_l05']
BENCHMARKS = {'greedy', 'ilp', 'hier', 'brkga'}
ALPHAS = [0.30, 0.35, 0.40, 0.45, 0.50]
GINI_COL = 'gini_elig_hourly'
COUR_COLS = ['run_id', 'gini_elig_hourly', 'gini_elig_active_hourly', 'gini_elig_total',
             'share_active_elig', 'p25_elig_hourly', 'share_elig', 'n_loaded']


def display_name(method: str) -> str:
    base = {'greedy': r'\textbf{Greedy}', 'ilp': r'\textbf{ILP}', 'hier': r'\textbf{Hierarchical}',
            'brkga': r'\textbf{BRKGA}'}
    if method in base:
        return base[method]
    m = re.match(r'^(brkga_fair|mipfair|paybrkga)_(w|a|l)(\d+)(.*)$', method)
    if not m:
        return r'\texttt{' + method.replace('_', r'\_') + '}'
    fam, kind, num, suffix = m.groups()
    if fam == 'brkga_fair':
        par = f'$w = {int(num)}$'
        name = r'\textbf{BRKGA-Fair}'
    elif fam == 'mipfair':
        par = f'$\\alpha = {int(num) / 100:.2f}$'
        name = r'\textbf{MIP-Fair}'
    else:
        par = f'$\\lambda_{{\\text{{pay}}}} = {int(num) / 10:.1f}$'
        name = r'\textbf{Pay-BRKGA}'
    tags = []
    if suffix:
        s = suffix.strip('_')
        if '_x' in '_' + s or s.startswith('x'):
            tags.append('exposure')
        k = re.search(r'xk(\d*)', s)
        if k:
            tags.append(f'$k_d = {int(k.group(1)) if k.group(1) else 8}$')
        e = re.search(r'e(\d{3})', s)
        if e:
            tags.append(f'$\\varepsilon = {int(e.group(1)) / 100:.2f}$')
    return f'{name} ({par}' + (', ' + ', '.join(tags) if tags else '') + ')'


def load(run_paths: List[str], couriers_table: str | None, all_seeds: bool) -> pd.DataFrame:
    runs = pd.concat([pd.read_csv(p) for p in run_paths], ignore_index=True)
    cour_paths = []
    if couriers_table:
        cour_paths.append(couriers_table)
    for p in run_paths:
        q = os.path.splitext(p)[0] + '_couriers.csv'
        if os.path.exists(q) and q not in cour_paths:
            cour_paths.append(q)
    cour = pd.concat([pd.read_csv(p) for p in cour_paths], ignore_index=True).drop_duplicates('run_id')
    df = runs.merge(cour[COUR_COLS], on='run_id', how='inner')
    missing = len(runs) - len(df)
    if missing:
        print(f'warning: {missing} runs without courier metrics were dropped')
    cells = df.groupby(['regime', 'method', 'instance']).ngroups
    if not all_seeds:
        cnt = df.groupby('seed')['run_id'].count()
        full = sorted(int(s) for s, c in cnt.items() if c >= cells)
        print('rows', len(df), 'cells per seed', cells, 'seed counts', cnt.to_dict(), 'complete seeds', full)
        df = df[df['seed'].isin(full)].copy()
    df['pay_pct'] = 100.0 * df['total_payment'] / (df['n_delivered'] * 2200.0)  # % of the tariff of the orders delivered
    df['cpu_min'] = df['wall_clock_sec'] / 60.0
    return df


def fmt_bold(values: pd.Series, best: str, fmt: str) -> Dict[str, str]:
    texts = {k: fmt.format(v) for k, v in values.items()}
    nums = {k: float(t) for k, t in texts.items()}
    target = min(nums.values()) if best == 'min' else max(nums.values())
    winners = [k for k, v in nums.items() if v == target]
    unique = len(winners) == 1   # no bold when the configurations tie after rounding
    return {k: (r'\textbf{' + t + '}' if unique and k in winners else t) for k, t in texts.items()}


def benchmark_rows(blk: pd.DataFrame, regime: str, configs: List[str]) -> str:
    sub = blk[(blk.regime == regime) & blk.method.isin(configs)]
    agg = sub.groupby('method').agg(cov=('coverage_rate', 'mean'), cov_se=('coverage_rate', 'sem'),
                                    gini=(GINI_COL, 'mean'), gini_se=(GINI_COL, 'sem'),
                                    act=('share_active_elig', 'mean'), gact=('F_Gini', 'mean'),
                                    late=('overage_mean', 'mean'), fd=('F_Deficit', 'mean'),
                                    pay=('pay_pct', 'mean'), cpu=('cpu_min', 'mean')).loc[[c for c in configs if c in sub.method.unique()]]
    cols = {'cov': fmt_bold(agg['cov'], 'max', '{:.3f}'), 'gini': fmt_bold(agg['gini'], 'min', '{:.3f}'),
            'act': fmt_bold(agg['act'], 'max', '{:.2f}'), 'gact': fmt_bold(agg['gact'], 'min', '{:.3f}'),
            'late': fmt_bold(agg['late'], 'min', '{:.1f}'), 'fd': fmt_bold(agg['fd'], 'max', '{:.3f}'),
            'pay': fmt_bold(agg['pay'].round(0), 'min', '{:.0f}'), 'cpu': fmt_bold(agg['cpu'], 'min', '{:.1f}')}
    lines = []
    sep_done = False
    for m in agg.index:
        if m not in BENCHMARKS and not sep_done:
            lines.append(r'\hline')
            sep_done = True
        lines.append(f"{display_name(m)} & {cols['cov'][m]} & {agg.loc[m, 'cov_se']:.3f} & {cols['gini'][m]} & "
                     f"{agg.loc[m, 'gini_se']:.3f} & {cols['act'][m]} & {cols['gact'][m]} & {cols['late'][m]} & "
                     f"{cols['fd'][m]} & {cols['pay'][m]} & {cols['cpu'][m]} \\\\")
    return '\n'.join(lines)


def city_rows(blk: pd.DataFrame, df: pd.DataFrame, configs: List[str], regime: str = 'manual', alpha: float = 0.40) -> str:
    """T8 (appendix): one block per city with the configurations of T3, manual regime: coverage, end-of-day
    Gini over the eligible couriers, active share, lateness, payment, and compliance with alpha."""
    city_of = df.groupby('instance')['city'].first()
    sub = blk[(blk.regime == regime) & blk.method.isin(configs)].copy()
    sub['city'] = sub['instance'].map(city_of)
    comp = df[(df.regime == regime) & df.method.isin(configs)].assign(ok=lambda d: d[GINI_COL] <= alpha)
    comp = comp.groupby(['city', 'method'])['ok'].mean() * 100
    lines = []
    for city in sorted(sub.city.unique()):
        s = sub[sub.city == city]
        n_inst = s.instance.nunique()
        agg = s.groupby('method').agg(cov=('coverage_rate', 'mean'), gini=(GINI_COL, 'mean'),
                                      act=('share_active_elig', 'mean'), late=('overage_mean', 'mean'),
                                      pay=('pay_pct', 'mean')).loc[[c for c in configs if c in s.method.unique()]]
        cols = {'cov': fmt_bold(agg['cov'], 'max', '{:.3f}'), 'gini': fmt_bold(agg['gini'], 'min', '{:.3f}'),
                'act': fmt_bold(agg['act'], 'max', '{:.2f}'), 'late': fmt_bold(agg['late'], 'min', '{:.1f}'),
                'pay': fmt_bold(agg['pay'].round(0), 'min', '{:.0f}')}
        lines.append(r'\multicolumn{7}{l}{\textit{' + city.replace('Bogota', "Bogot\\'a").replace('Medellin', "Medell\\'in")
                     + f' ({n_inst} instances)' + r'}} \\')
        for m in agg.index:
            c = comp.get((city, m), float('nan'))
            lines.append(f"{display_name(m)} & {cols['cov'][m]} & {cols['gini'][m]} & {cols['act'][m]} & "
                         f"{cols['late'][m]} & {cols['pay'][m]} & {c:.0f} \\\\")
        lines.append(r'\hline')
    return '\n'.join(lines)


def scope_rows(blk: pd.DataFrame, configs: List[str]) -> str:
    sub = blk[(blk.regime == 'manual') & blk.method.isin(configs)]
    agg = sub.groupby('method').agg(g=(GINI_COL, 'mean'), ga=('gini_elig_active_hourly', 'mean'),
                                    gact=('F_Gini', 'mean'), act=('share_active_elig', 'mean'),
                                    p25=('p25_elig_hourly', 'mean')).loc[[c for c in configs if c in sub.method.unique()]]
    cols = {'g': fmt_bold(agg['g'], 'min', '{:.3f}'), 'ga': fmt_bold(agg['ga'], 'min', '{:.3f}'),
            'gact': fmt_bold(agg['gact'], 'min', '{:.3f}'), 'act': fmt_bold(agg['act'], 'max', '{:.2f}'),
            'p25': fmt_bold(agg['p25'].round(0), 'max', '{:.0f}')}
    lines, sep_done = [], False
    for m in agg.index:
        if m not in BENCHMARKS and not sep_done:
            lines.append(r'\hline')
            sep_done = True
        lines.append(f"{display_name(m)} & {cols['g'][m]} & {cols['ga'][m]} & {cols['gact'][m]} & {cols['act'][m]} & {cols['p25'][m]} \\\\")
    return '\n'.join(lines)


def compliance_table(df: pd.DataFrame, configs: List[str]) -> pd.DataFrame:
    rows = {}
    for (reg, m), g in df.groupby(['regime', 'method']):
        for a in ALPHAS:
            rows.setdefault(m, {})[(reg, a)] = 100.0 * float((g[GINI_COL] <= a).mean())
    t = pd.DataFrame(rows).T
    t = t[[(r, a) for r in ('manual', 'autoaccept') for a in ALPHAS]]
    return t.loc[[c for c in configs if c in t.index]] if configs else t


def compliance_rows(t: pd.DataFrame) -> str:
    lines, sep_done = [], False
    for m in t.index:
        if m not in BENCHMARKS and not sep_done:
            lines.append(r'\hline')
            sep_done = True
        vals = []
        for col in t.columns:
            v = t.loc[m, col]
            txt = f'{v:.0f}'
            vals.append(r'\textbf{' + txt + '}' if abs(v - t[col].max()) < 1e-9 and v > 0 else txt)
        lines.append(f"{display_name(m)} & " + ' & '.join(vals) + r' \\')
    return '\n'.join(lines)


def stats_text(df: pd.DataFrame, blk: pd.DataFrame, configs: List[str]) -> str:
    out = []
    pd.set_option('display.width', 250)
    pd.set_option('display.max_rows', 500)
    out.append(f"rows {len(df)}; seeds {sorted(df.seed.unique())}; instances {df.instance.nunique()}; methods {df.method.nunique()}")
    cols = ['coverage_rate', 'overage_mean', GINI_COL, 'F_Gini', 'gini_elig_active_hourly', 'share_active_elig',
            'p25_elig_hourly', 'F_Deficit', 'pay_pct', 'cpu_min']
    for reg in ('manual', 'autoaccept'):
        t = blk[blk.regime == reg].groupby('method')[cols].agg(['mean', 'sem'])
        tab = pd.DataFrame({c: t[(c, 'mean')].round(3).astype(str) + ' (' + t[(c, 'sem')].round(3).astype(str) + ')'
                            for c in cols})
        tab['cpu_max'] = blk[blk.regime == reg].groupby('method')['cpu_min'].max().round(1)
        out.append(f'\n== {reg}: mean (SE over instances), all configurations ==\n' + tab.to_string())
    rng = np.random.default_rng(0)
    rows = []
    for reg in ('manual', 'autoaccept'):
        base = blk[(blk.regime == reg) & (blk.method == 'greedy')].set_index('instance')
        for m in sorted(blk.method.unique()):
            if m == 'greedy':
                continue
            x = blk[(blk.regime == reg) & (blk.method == m)].set_index('instance').reindex(base.index)
            row = {'regime': reg, 'method': m}
            for c in ['coverage_rate', 'overage_mean', GINI_COL, 'F_Gini', 'share_active_elig', 'p25_elig_hourly']:
                dlt = (x[c] - base[c]).dropna().to_numpy()
                boots = [rng.choice(dlt, len(dlt), replace=True).mean() for _ in range(2000)]
                row[c] = f"{dlt.mean():+.3f} [{np.percentile(boots, 2.5):+.3f},{np.percentile(boots, 97.5):+.3f}]"
            rows.append(row)
    out.append('\n== paired differences vs greedy (instance blocks), mean [95% bootstrap] ==\n' + pd.DataFrame(rows).to_string(index=False))
    out.append('\n== compliance (% of instance-seed pairs with eligible Gini <= alpha), all configurations ==\n'
               + compliance_table(df, []).round(0).to_string())
    piv = blk.pivot_table(index=['method', 'instance'], columns='regime', values=['coverage_rate', GINI_COL])
    if ('coverage_rate', 'manual') in piv.columns and ('coverage_rate', 'autoaccept') in piv.columns:
        loss = pd.DataFrame({'d_cov': piv[('coverage_rate', 'manual')] - piv[('coverage_rate', 'autoaccept')],
                             'd_gini_elig': piv[(GINI_COL, 'manual')] - piv[(GINI_COL, 'autoaccept')]})
        out.append('\n== regime loss (manual - autoaccept) by method ==\n' + loss.groupby('method').mean().round(3).to_string())
    for reg in ('manual', 'autoaccept'):
        city = df[df.regime == reg].groupby(['city', 'method'])[GINI_COL].mean().unstack()
        keep = [c for c in configs if c in city.columns]
        out.append(f'\n== by city, {reg}: eligible Gini ==\n' + city[keep].round(3).to_string())
        out.append(f'   range by city, greedy: {city["greedy"].min():.3f}-{city["greedy"].max():.3f}; others: '
                   f'{city.drop(columns=["greedy"]).min().min():.3f}-{city.drop(columns=["greedy"]).max().max():.3f}')
    g = df[(df.regime == 'manual') & (df.method == 'greedy')]
    out.append('\nshare of couriers connected < 1 h (manual greedy): ' + f'{1 - g.share_elig.mean():.3f}')
    return '\n'.join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('csv', nargs='+')
    ap.add_argument('--couriers-table', default=None)
    ap.add_argument('--out-dir', default='output/paper/tables')
    ap.add_argument('--configs', default=','.join(CONFIGS), help='comma-separated methods for the three tables')
    ap.add_argument('--all-seeds', action='store_true')
    a = ap.parse_args()
    configs = a.configs.split(',')
    df = load(a.csv, a.couriers_table, a.all_seeds)
    cols = ['coverage_rate', 'overage_mean', GINI_COL, 'F_Gini', 'gini_elig_active_hourly', 'share_active_elig',
            'p25_elig_hourly', 'F_Deficit', 'pay_pct', 'cpu_min', 'share_elig']
    blk = df.groupby(['regime', 'method', 'instance'])[cols].mean().reset_index()
    os.makedirs(a.out_dir, exist_ok=True)
    bench = (r'\multicolumn{11}{l}{\textit{Manual regime}} \\' + '\n' + benchmark_rows(blk, 'manual', configs) + '\n'
             + r'\hline' + '\n' + r'\multicolumn{11}{l}{\textit{Auto-accept regime}} \\' + '\n'
             + benchmark_rows(blk, 'autoaccept', configs) + '\n')
    open(os.path.join(a.out_dir, 'benchmark.tex'), 'w', encoding='utf8').write(bench)
    open(os.path.join(a.out_dir, 'scope.tex'), 'w', encoding='utf8').write(scope_rows(blk, configs) + '\n')
    open(os.path.join(a.out_dir, 'compliance.tex'), 'w', encoding='utf8').write(
        compliance_rows(compliance_table(df, configs)) + '\n')
    open(os.path.join(a.out_dir, 'city.tex'), 'w', encoding='utf8').write(city_rows(blk, df, configs) + '\n')
    txt = stats_text(df, blk, configs)
    open(os.path.join(a.out_dir, 'stats.txt'), 'w', encoding='utf8').write(txt)
    print(bench)
    print(open(os.path.join(a.out_dir, 'scope.tex'), encoding='utf8').read())
    print(open(os.path.join(a.out_dir, 'compliance.tex'), encoding='utf8').read())
    print(f'written to {a.out_dir}')


if __name__ == '__main__':
    main()
