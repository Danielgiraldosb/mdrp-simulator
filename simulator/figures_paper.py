"""
figures_paper.py -- figures of the paper that do not depend on simulation runs.

  F1  map of a 3 km zone (stores, drop-offs, courier log-on points) of a Bogota day
  F2  logit acceptance curve on pay per km with the 95 % CI band and the two regimes

  python figures_paper.py --fig f1 f2 --out ../docs/paper-cmdp/figures
  (use the Python that has matplotlib, e.g. ../.venv314/Scripts/python.exe)

Run-dependent figures (F3-F8) are produced by analyze_paper.py once X1 exists.
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'real_instancies'))

# logit on ln(pay/km): fit on 32 declared decisions, 11 couriers (Bogota 2020, manual regime)
THETA, THETA_CI = 903.0, (615.0, 1242.0)     # COP/km at which P = 0.5
SLOPE, SLOPE_CI = 2.89, (2.02, 5.23)
TARIFF = 2200.0                               # COP per order (decision D1)


def _plt():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.dpi': 150})
    return plt


def _save(fig, out_dir: str, name: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(out_dir, f'{name}.{ext}'), bbox_inches='tight')
    print(f'wrote {os.path.join(out_dir, name)}.pdf/.png')


def _km_offsets(lat: pd.Series, lng: pd.Series, lat0: float, lng0: float):
    kx = 111.32 * math.cos(math.radians(lat0))
    ky = 110.57
    return (lng - lng0) * kx, (lat - lat0) * ky


def fig_f1(out_dir: str, instance: str = 'Instancia_0', radius_km: float = 3.0,
           center: tuple = (4.679, -74.065)) -> None:
    plt = _plt()
    d = os.path.join(REAL_DIR, instance)
    stores = pd.read_csv(os.path.join(d, 'stores.csv'))
    orders = pd.read_csv(os.path.join(d, 'orders.csv'))
    couriers = pd.read_csv(os.path.join(d, 'couriers.csv'))
    lat0, lng0 = center
    sx, sy = _km_offsets(stores['pick_up_lat'], stores['pick_up_lng'], lat0, lng0)
    ox, oy = _km_offsets(orders['drop_off_lat'], orders['drop_off_lng'], lat0, lng0)
    cx, cy = _km_offsets(couriers['on_lat'], couriers['on_lng'], lat0, lng0)

    def inside(x, y):
        return np.hypot(x, y) <= radius_km

    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.scatter(ox[inside(ox, oy)], oy[inside(ox, oy)], s=1.5, c='#9ecae1', alpha=0.5,
               label=f'drop-offs in zone ({int(inside(ox, oy).sum()):,})', rasterized=True)
    ax.scatter(cx[inside(cx, cy)], cy[inside(cx, cy)], s=3, c='#fd8d3c', alpha=0.6, marker='^',
               label=f'courier log-ons ({int(inside(cx, cy).sum()):,})', rasterized=True)
    ax.scatter(sx[inside(sx, sy)], sy[inside(sx, sy)], s=6, c='#08519c', marker='s',
               label=f'stores ({int(inside(sx, sy).sum()):,})', rasterized=True)
    circ = plt.Circle((0, 0), radius_km, fill=False, lw=1.2, ls='--', color='k')
    ax.add_patch(circ)
    far = ~inside(ox, oy)
    ax.scatter(ox[far], oy[far], s=0.5, c='#d9d9d9', alpha=0.4, rasterized=True)
    lim = radius_km * 1.6
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect('equal')
    ax.set_xlabel('km east of the instance centre')
    ax.set_ylabel('km north of the instance centre')
    ax.set_title(f'{instance} (Bogota): the {radius_km:g} km zone used in the experiments', fontsize=9)
    ax.legend(loc='lower left', fontsize=7, frameon=False, markerscale=3)
    _save(fig, out_dir, 'F1_zone_map')


def fig_f2(out_dir: str) -> None:
    plt = _plt()
    ppk = np.linspace(300, 3000, 400)

    def p(theta, b):
        return 1.0 / (1.0 + np.exp(-b * (np.log(ppk) - np.log(theta))))

    # CI band: envelope over the corners of the (theta, slope) intervals
    corners = [p(t, b) for t in (THETA_CI[0], THETA, THETA_CI[1]) for b in (SLOPE_CI[0], SLOPE, SLOPE_CI[1])]
    lo, hi = np.min(corners, axis=0), np.max(corners, axis=0)

    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    ax.fill_between(ppk, lo, hi, color='#c6dbef', alpha=0.7, label='95 % CI of the fit (threshold and slope)')
    ax.plot(ppk, p(THETA, SLOPE), c='#08519c', lw=2, label=f'manual regime: logit, threshold {THETA:.0f} COP/km, slope {SLOPE}')
    ax.axhline(1.0, c='#fd8d3c', lw=2, ls='--', label='auto-accept regime: P = 1')
    for x in (1000, 1500, 2000):
        y = float(1.0 / (1.0 + math.exp(-SLOPE * (math.log(x) - math.log(THETA)))))
        ax.plot([x], [y], 'o', c='#08519c', ms=4)
        ax.annotate(f'{y:.2f}', (x, y), textcoords='offset points', xytext=(6, -10), fontsize=7)
    for km, lab in ((1.0, '1 km'), (2.0, '2 km'), (3.0, '3 km')):
        x = TARIFF / km
        if ppk[0] <= x <= ppk[-1]:
            ax.axvline(x, c='#bdbdbd', lw=0.8, ls=':')
            ax.annotate(f'tariff / {lab}', (x, 0.30), rotation=90, fontsize=7, color='#636363',
                        textcoords='offset points', xytext=(3, 0))
    ax.set_xlabel('pay per km of the offered route (COP/km)')
    ax.set_ylabel('probability of accepting the offer')
    ax.set_ylim(0, 1.05)
    ax.set_xlim(ppk[0], ppk[-1])
    ax.legend(loc='upper left', fontsize=7, frameon=False)
    _save(fig, out_dir, 'F2_acceptance_curve')


FAMILIES = {   # sweep family -> (label, colour, parameter name, ordered configs)
    'mipfair':    ('MIP-Fair ($\\alpha$)', '#d94801', 'alpha',
                   ['mipfair_a020', 'mipfair_a025', 'mipfair_a030', 'mipfair_a035', 'mipfair_a040', 'mipfair_a100']),
    'brkga_fair': ('BRKGA-Fair ($w$)', '#238b45', 'weight',
                   ['brkga_fair_w5', 'brkga_fair_w10', 'brkga_fair_w20', 'brkga_fair_w40']),
    'paybrkga':   ('Pay-BRKGA ($\\lambda_{pay}$)', '#6a51a3', 'lambda_pay',
                   ['paybrkga_l01', 'paybrkga_l02', 'paybrkga_l05', 'paybrkga_l10']),
}
BENCH = {'greedy': ('Greedy', 'k', 's'), 'ilp': ('ILP', '#2171b5', 'D'),
         'hier': ('Hierarchical', '#969696', '^'), 'brkga': ('BRKGA', '#41ab5d', 'o')}
# second generation (E10/E10b, X3 gen2): hollow markers, one dotted path per family from the first-generation
# parent through k_d = 8 to k_d = 25 (the exposure-only variants are left out: they sit on top of the parent)
GEN2_PATHS = {   # family -> (label, colour, [(parent, None), (variant, annotation), ...])
    'mipfair':    ('MIP-Fair, 2nd gen. ($k_d$)', '#d94801',
                   [('mipfair_a030', None), ('mipfair_a030_xk_e000', '8'), ('mipfair_a030_xk25_e000', '25')]),
    'brkga_fair': ('BRKGA-Fair, 2nd gen. ($k_d$)', '#238b45',
                   [('brkga_fair_w20', None), ('brkga_fair_w20_xk', '8'), ('brkga_fair_w40_xk25', '25 ($w=40$)')]),
    'paybrkga':   ('Pay-BRKGA, 2nd gen. ($k_d$)', '#6a51a3',
                   [('paybrkga_l05', None), ('paybrkga_l05_xk', '8')]),
}


def _frontier_panel(ax, pts: pd.DataFrame, ycol: str, ylabel: str, title: str) -> None:
    """pts: one row per method with columns F_Gini, <ycol>, alpha/weight/lambda_pay."""
    pts = pts.set_index('method')
    for fam, (lab, col, par, order) in FAMILIES.items():
        sub = pts.loc[[m for m in order if m in pts.index]]
        if sub.empty:
            continue
        ax.plot(sub['F_Gini'], sub[ycol], '-o', c=col, ms=4, lw=1.2, label=lab)
        for m, r in sub.iterrows():
            v = r[par]
            ax.annotate(f'{v:g}', (r['F_Gini'], r[ycol]), textcoords='offset points', xytext=(3, 3), fontsize=6, color=col)
    for m, (lab, col, mk) in BENCH.items():
        if m in pts.index:
            r = pts.loc[m]
            ax.plot([r['F_Gini']], [r[ycol]], mk, c=col, ms=6, label=lab, ls='none')
    for fam, (lab, col, path) in GEN2_PATHS.items():
        path = [(m, a) for m, a in path if m in pts.index]
        if len(path) < 2:
            continue
        xs = [pts.loc[m, 'F_Gini'] for m, _ in path]
        ys = [pts.loc[m, ycol] for m, _ in path]
        ax.plot(xs, ys, ':', c=col, lw=1.0)
        ax.plot(xs[1:], ys[1:], 'o', mfc='white', mec=col, ms=5, ls='none', label=lab)
        for (m, a), x, y in zip(path[1:], xs[1:], ys[1:]):
            ax.annotate(a, (x, y), textcoords='offset points', xytext=(-3, -9), fontsize=6, color=col, ha='right')
    ax.set_xlabel('end-of-day Gini of hourly earnings, eligible couriers')
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9)


def fig_frontiers(out_dir: str, main_csv: str, couriers_table: str = None, complete_seeds: bool = True,
                  extra_csvs=()) -> None:
    """F3 (coverage) and F4 (lateness) against the end-of-day Gini, one panel per regime.
    With couriers_table (analyze_couriers.py --out) the x-axis is the Gini over the ELIGIBLE couriers
    (decision E9, 2026-10-21); without it, the active-courier F_Gini of metrics.py. extra_csvs (e.g. gen2.csv,
    with its <stem>_couriers.csv next to it) add the second-generation points; the complete-seed filter is applied
    per table, so each configuration is averaged over its own complete seeds (ten in X1, five in X3)."""
    plt = _plt()
    parts = []
    for i, path in enumerate([main_csv, *extra_csvs]):
        d = pd.read_csv(path)
        ct_path = couriers_table if i == 0 else os.path.splitext(path)[0] + '_couriers.csv'
        if ct_path and os.path.exists(ct_path):
            ct = pd.read_csv(ct_path)[['run_id', 'gini_elig_hourly']]
            d = d.merge(ct, on='run_id', how='inner')
            d['F_Gini'] = d['gini_elig_hourly']
        if complete_seeds:
            cnt = d.groupby('seed')['run_id'].count()
            d = d[d['seed'].isin(cnt[cnt == cnt.max()].index)]
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    inst = df.groupby(['regime', 'method', 'instance'])[['F_Gini', 'coverage_rate', 'overage_mean']].mean().reset_index()
    pts = inst.groupby(['regime', 'method'])[['F_Gini', 'coverage_rate', 'overage_mean']].mean().reset_index()
    par = df.groupby('method')[['alpha', 'weight', 'lambda_pay']].first().reset_index()
    pts = pts.merge(par, on='method', how='left')
    nseeds = df['seed'].nunique()
    for name, ycol, ylabel in (('F3_pareto_coverage', 'coverage_rate', 'coverage (fraction of orders delivered)'),
                               ('F4_pareto_lateness', 'overage_mean', 'mean lateness of delivered orders (min)')):
        fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4), sharey=True)
        for ax, reg, title in zip(axes, ('manual', 'autoaccept'), ('manual regime', 'auto-accept regime')):
            _frontier_panel(ax, pts[pts.regime == reg].copy(), ycol, ylabel if ax is axes[0] else '', title)
        axes[0].legend(fontsize=6, frameon=False, loc='lower left', ncol=2, columnspacing=0.8, handletextpad=0.4)
        seeds_txt = (f'{parts[0].seed.nunique()} seeds (first generation) and {parts[1].seed.nunique()} seeds (second generation, hollow markers)'
                     if len(parts) > 1 else f'{nseeds} seed(s)')
        fig.suptitle(f'mean over {inst.instance.nunique()} instances and {seeds_txt}', fontsize=7, y=0.99)
        _save(fig, out_dir, name)


SELECTED = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w20', 'mipfair_a030', 'paybrkga_l05']   # T3 configurations
SHORT = {'greedy': 'Greedy', 'ilp': 'ILP', 'hier': 'Hierarchical', 'brkga': 'BRKGA', 'brkga_fair_w20': 'BRKGA-Fair\n($w=20$)',
         'mipfair_a030': 'MIP-Fair\n($\\alpha=0.30$)', 'paybrkga_l05': 'Pay-BRKGA\n($\\lambda_{pay}=0.5$)'}


def _colour(method: str) -> str:
    if method in BENCH:
        return BENCH[method][1]
    for fam, (_, col, _, order) in FAMILIES.items():
        if method in order:
            return col
    return '#444444'


def _load_runs(main_csv: str, couriers_table: str | None, complete_seeds: bool = True) -> pd.DataFrame:
    df = pd.read_csv(main_csv)
    if couriers_table:
        ct = pd.read_csv(couriers_table)[['run_id', 'gini_elig_hourly']]
        df = df.merge(ct, on='run_id', how='inner')
    if complete_seeds:
        cnt = df.groupby('seed')['run_id'].count()
        df = df[df['seed'].isin(cnt[cnt == cnt.max()].index)]
    return df


def fig_regime_loss(out_dir: str, main_csv: str, couriers_table: str, methods=SELECTED, n_boot: int = 2000) -> None:
    """F5: the regime loss (manual minus auto-accept) per policy, paired by instance (seeds averaged within
    the instance), mean with a 95% bootstrap interval over the instances. Left: coverage (points);
    right: end-of-day Gini over the eligible couriers (E9)."""
    plt = _plt()
    df = _load_runs(main_csv, couriers_table)
    inst = df.groupby(['method', 'regime', 'instance'])[['coverage_rate', 'gini_elig_hourly']].mean()
    rng = np.random.default_rng(0)
    rows = []
    for m in methods:
        if m not in inst.index.get_level_values(0):
            continue
        man = inst.loc[(m, 'manual')]
        aut = inst.loc[(m, 'autoaccept')].reindex(man.index)
        for col, scale in (('coverage_rate', 100.0), ('gini_elig_hourly', 1.0)):
            d = ((man[col] - aut[col]) * scale).dropna().to_numpy()
            boots = [rng.choice(d, len(d), replace=True).mean() for _ in range(n_boot)]
            rows.append({'method': m, 'metric': col, 'mean': d.mean(),
                         'lo': np.percentile(boots, 2.5), 'hi': np.percentile(boots, 97.5)})
    t = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.2))
    for ax, col, xlabel in zip(axes, ('coverage_rate', 'gini_elig_hourly'),
                               ('coverage, manual minus auto-accept (points)',
                                'end-of-day Gini (eligible couriers), manual minus auto-accept')):
        sub = t[t.metric == col].set_index('method').reindex([m for m in methods if m in set(t.method)])
        y = np.arange(len(sub))[::-1]
        for yi, (m, r) in zip(y, sub.iterrows()):
            ax.errorbar(r['mean'], yi, xerr=[[r['mean'] - r['lo']], [r['hi'] - r['mean']]], fmt='o', ms=5,
                        color=_colour(m), ecolor=_colour(m), elinewidth=1.2, capsize=2.5)
        ax.axvline(0, color='#999999', lw=0.8, ls='--')
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT.get(m, m) for m in sub.index], fontsize=7.5)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.grid(axis='x', lw=0.4, alpha=0.5)
    fig.suptitle(f'paired by instance ({inst.index.get_level_values(2).nunique()} instances, '
                 f'{df.seed.nunique()} seeds averaged within each); mean and 95% bootstrap interval', fontsize=7, y=1.0)
    _save(fig, out_dir, 'F5_regime_loss')
    t.to_csv(os.path.join(out_dir, 'F5_regime_loss.csv'), index=False)


def fig_earnings_violin(out_dir: str, main_csv: str, couriers_dir: str, methods=SELECTED, regime: str = 'manual',
                        seed: int = 1, min_shift_h: float = 1.0, clip_q: float = 0.99) -> None:
    """F7: distribution of end-of-day hourly earnings (COP per connected hour) over the ELIGIBLE couriers
    (shift >= 1 h, idle ones at zero), pooled over the 24 instances of one seed, one violin per policy.
    The share of eligible couriers without a delivery is printed under each violin."""
    plt = _plt()
    df = pd.read_csv(main_csv)
    df = df[(df.regime == regime) & (df.seed == seed) & (df.method.isin(methods))]
    data, zeros, n_inst = {}, {}, {}
    for m in methods:
        runs = df[df.method == m]
        vals = []
        for rid in runs.run_id:
            p = os.path.join(couriers_dir, f'{rid}.csv')
            if not os.path.exists(p):
                continue
            t = pd.read_csv(p)
            t = t[t['shift_h'] >= min_shift_h]
            vals.append((t['payment'] / t['shift_h'].clip(lower=1e-9)).to_numpy())
        if not vals:
            continue
        v = np.concatenate(vals)
        data[m], zeros[m], n_inst[m] = v, float((v <= 0).mean()), len(vals)
    cap = np.percentile(np.concatenate(list(data.values())), clip_q * 100)
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    order = [m for m in methods if m in data]
    parts = ax.violinplot([np.minimum(data[m], cap) for m in order], positions=range(len(order)), showmedians=True,
                          showextrema=False, widths=0.85, points=200)
    for body, m in zip(parts['bodies'], order):
        body.set_facecolor(_colour(m))
        body.set_edgecolor('none')
        body.set_alpha(0.55)
    parts['cmedians'].set_color('k')
    parts['cmedians'].set_linewidth(1.0)
    for i, m in enumerate(order):
        q1, q3 = np.percentile(data[m], [25, 75])
        ax.plot([i, i], [min(q1, cap), min(q3, cap)], color='k', lw=2.2, solid_capstyle='butt')
        ax.text(i, -0.06 * cap, f'idle {100 * zeros[m]:.0f}%', ha='center', va='top', fontsize=7, color='#333333')
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([SHORT.get(m, m) for m in order], fontsize=7.5)
    ax.set_ylabel('end-of-day earnings per connected hour (COP/h)', fontsize=8)
    ax.set_ylim(-0.14 * cap, cap * 1.02)
    ax.axhline(0, color='#999999', lw=0.6)
    ax.set_title(f'eligible couriers (connected $\\geq$ {min_shift_h:g} h), {regime} regime, seed {seed}, '
                 f'pooled over {max(n_inst.values())} instances; values above the {int(clip_q * 100)}th percentile '
                 f'({cap:,.0f} COP/h) are clipped; vertical bar = interquartile range, horizontal tick = median', fontsize=7)
    _save(fig, out_dir, 'F7_earnings_violin')
    pd.DataFrame({'method': order, 'n_couriers': [len(data[m]) for m in order],
                  'share_idle': [zeros[m] for m in order],
                  'p25': [np.percentile(data[m], 25) for m in order], 'median': [np.median(data[m]) for m in order],
                  'p75': [np.percentile(data[m], 75) for m in order], 'mean': [data[m].mean() for m in order]}
                 ).to_csv(os.path.join(out_dir, 'F7_earnings_violin.csv'), index=False)


EMISSION_KG_PER_KM = {'motorcycle': 0.114, 'car': 0.167, 'bicycle': 0.0, 'walking': 0.0}   # DEFRA 2023 (T2)


def fig_emissions(out_dir: str, main_csv: str, couriers_dir: str, methods=SELECTED, regime: str = 'manual') -> None:
    """F8: emissions diagnostic. Left: kg CO2e per delivered order by policy and city (mean over seeds),
    from the per-courier distances and the emission factors of T2. Right: share of the distance driven by
    each vehicle type, by policy (mean over the 24 instances). Writes F8_emissions.csv with the numbers."""
    plt = _plt()
    df = pd.read_csv(main_csv)
    df = df[(df.regime == regime) & (df.method.isin(methods))]
    rows = []
    for r in df.itertuples():
        p = os.path.join(couriers_dir, f'{r.run_id}.csv')
        if not os.path.exists(p):
            continue
        t = pd.read_csv(p)
        km = t.groupby('vehicle')['dist_km'].sum()
        kg = sum(EMISSION_KG_PER_KM.get(v, 0.0) * d for v, d in km.items())
        rows.append({'run_id': r.run_id, 'instance': r.instance, 'city': r.city, 'method': r.method, 'seed': r.seed,
                     'n_delivered': r.n_delivered, 'kg_co2e': kg, 'kg_per_order': kg / max(r.n_delivered, 1),
                     'km_total': km.sum(), **{f'km_{v}': km.get(v, 0.0) for v in EMISSION_KG_PER_KM}})
    e = pd.DataFrame(rows)
    e.to_csv(os.path.join(out_dir, 'F8_emissions_runs.csv'), index=False)
    by_city = e.groupby(['city', 'method'])['kg_per_order'].mean().unstack('method')[[m for m in methods if m in set(e.method)]]
    inst = e.groupby(['method', 'instance'])[['km_total'] + [f'km_{v}' for v in EMISSION_KG_PER_KM]].mean()
    share = inst.groupby('method').sum()
    for v in EMISSION_KG_PER_KM:
        share[f'share_{v}'] = share[f'km_{v}'] / share['km_total']
    share = share.reindex([m for m in methods if m in share.index])
    pd.concat([by_city.T.add_prefix('kg_per_order_'), share[[f'share_{v}' for v in EMISSION_KG_PER_KM]]], axis=1
              ).to_csv(os.path.join(out_dir, 'F8_emissions.csv'))
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.3), gridspec_kw={'width_ratios': [1.5, 1]})
    ax = axes[0]
    cities = list(by_city.index)
    w = 0.8 / len(by_city.columns)
    for j, m in enumerate(by_city.columns):
        ax.bar(np.arange(len(cities)) + (j - len(by_city.columns) / 2 + 0.5) * w, by_city[m], width=w,
               color=_colour(m), label=SHORT.get(m, m).replace('\n', ' '))
    ax.set_xticks(range(len(cities)))
    ax.set_xticklabels(cities, fontsize=7, rotation=20, ha='right')
    ax.set_ylabel('kg CO$_2$e per delivered order', fontsize=8)
    ax.legend(fontsize=6, frameon=False, ncol=2)
    ax.set_title(f'{regime} regime, mean over seeds and instances of the city', fontsize=8)
    one_line = {m: SHORT.get(m, m).split('\n')[0] for m in methods}
    ax = axes[1]
    bottom = np.zeros(len(share))
    cols = {'motorcycle': '#d94801', 'car': '#7f2704', 'bicycle': '#41ab5d', 'walking': '#c7e9c0'}
    for v in ('motorcycle', 'car', 'bicycle', 'walking'):
        ax.bar(range(len(share)), 100 * share[f'share_{v}'], bottom=bottom, color=cols[v], label=v, width=0.7)
        bottom += 100 * share[f'share_{v}'].to_numpy()
    ax.set_xticks(range(len(share)))
    ax.set_xticklabels([one_line.get(m, m) for m in share.index], fontsize=6.5, rotation=30, ha='right')
    ax.set_ylabel('share of distance by vehicle type (%)', fontsize=8)
    ax.set_ylim(0, 118)
    ax.legend(fontsize=6, frameon=False, loc='upper center', ncol=4, columnspacing=0.8, handlelength=1.0)
    ax.set_title('24 instances pooled, manual regime', fontsize=8)
    _save(fig, out_dir, 'F8_emissions')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fig', nargs='+', default=['f1', 'f2'], choices=['f1', 'f2', 'f3f4', 'f5', 'f7', 'f8'])
    ap.add_argument('--couriers-dir', default=os.path.join(THIS_DIR, 'output', 'paper', 'couriers'))
    ap.add_argument('--out', default=os.path.normpath(os.path.join(THIS_DIR, '..', 'docs', 'paper-cmdp', 'paper', 'figures')))
    ap.add_argument('--main-csv', default=os.path.join(THIS_DIR, 'output', 'paper', 'main.csv'))
    ap.add_argument('--extra-csv', nargs='*', default=[], help='further run tables for F3/F4 (e.g. gen2.csv)')
    ap.add_argument('--couriers-table', default=os.path.join(THIS_DIR, 'output', 'paper', 'main_couriers.csv'),
                    help='analyze_couriers.py --out table; the x-axis of F3/F4 is then the eligible-courier Gini (E9)')
    args = ap.parse_args()
    if 'f1' in args.fig:
        fig_f1(args.out)
    if 'f2' in args.fig:
        fig_f2(args.out)
    if 'f3f4' in args.fig:
        fig_frontiers(args.out, args.main_csv, args.couriers_table if os.path.exists(args.couriers_table) else None,
                      extra_csvs=args.extra_csv)
    if 'f5' in args.fig:
        fig_regime_loss(args.out, args.main_csv, args.couriers_table)
    if 'f7' in args.fig:
        fig_earnings_violin(args.out, args.main_csv, args.couriers_dir)
    if 'f8' in args.fig:
        fig_emissions(args.out, args.main_csv, args.couriers_dir)


if __name__ == '__main__':
    main()
