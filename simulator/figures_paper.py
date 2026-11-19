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


TEXTWIDTH_IN = 6.5      # \textwidth of the manuscript (elsarticle 3p, 468 pt); figures are drawn at the width
                        # at which main.tex includes them, so that 8 pt in matplotlib is 8 pt on the page

# One style per policy family for every figure of the paper (P35): colour, marker, line style. The line styles
# differ so that the curves of F6 can be told apart in grey.
POLICY_STYLE = {
    'greedy':         ('Greedy', 'k', 's', '-'),
    'greedy_arrival': ('Greedy-Arrival', '#737373', 'x', '-'),
    'ilp':            ('ILP', '#2171b5', 'D', '-'),
    'hier':           ('Hierarchical', '#969696', '^', '--'),
    'brkga':          ('BRKGA', '#a6761d', 'o', '-'),
    'brkga_fair':     ('BRKGA-Fair', '#238b45', 'o', '-.'),
    'mipfair':        ('MIP-Fair', '#d94801', 'o', ':'),
    'paybrkga':       ('Pay-BRKGA', '#6a51a3', 'o', (0, (5, 1, 1, 1, 1, 1))),
}


def policy_key(method: str) -> str:
    """Family key of POLICY_STYLE for a configuration name of batch_paper (e.g. mipfair_a030_xk25_e000)."""
    if method in POLICY_STYLE:
        return method
    for k in ('brkga_fair', 'mipfair', 'paybrkga'):
        if method.startswith(k):
            return k
    return 'brkga' if method.startswith('brkga') else method


def policy_style(method: str):
    return POLICY_STYLE.get(policy_key(method), (method, '#444444', 'o', '-'))


def _plt():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 8, 'axes.titlesize': 8, 'axes.labelsize': 8, 'xtick.labelsize': 8,
                         'ytick.labelsize': 8, 'legend.fontsize': 8, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.dpi': 150})
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


def fig_f1(out_dir: str, instance: str = 'Instancia_0', radius_km: float = 3.0) -> None:
    """The zone exactly as the experiments load it (loader_real.py: median store location as origin, stores,
    drop-offs and log-ons within radius_km, orders whose store is in the zone), so the counts of the legend are
    those of tab:instances; the drop-offs outside the zone are drawn in grey for context."""
    from config import Config
    from loader_real import load_real_instance
    plt = _plt()
    inst = load_real_instance(instance, REAL_DIR, Config(real_max_radius_km=radius_km, real_circuity=1.0))
    km = lambda locs: (np.array([p.x for p in locs]) / 1000.0, np.array([p.y for p in locs]) / 1000.0)
    ox, oy = km([o.user_loc for o in inst['orders']])
    cx, cy = km([c.home_loc for c in inst['couriers']])
    sx, sy = km(inst['stores'])
    st = pd.read_csv(os.path.join(REAL_DIR, instance, 'stores.csv'))
    allo = pd.read_csv(os.path.join(REAL_DIR, instance, 'orders.csv'))
    lat0, lng0 = float(st['pick_up_lat'].median()), float(st['pick_up_lng'].median())
    fx, fy = _km_offsets(allo['drop_off_lat'], allo['drop_off_lng'], lat0, lng0)
    far = np.hypot(fx, fy) > radius_km

    fig, ax = plt.subplots(figsize=(0.495 * TEXTWIDTH_IN, 0.495 * TEXTWIDTH_IN))   # minipage of 0.495\textwidth
    ax.scatter(fx[far], fy[far], s=0.5, c='#d9d9d9', alpha=0.4, rasterized=True)
    ax.scatter(ox, oy, s=1.5, c='#9ecae1', alpha=0.5, label=f'drop-offs ({len(ox):,} orders)', rasterized=True)
    ax.scatter(cx, cy, s=3, c='#fd8d3c', alpha=0.6, marker='^', label=f'courier log-ons ({len(cx):,})', rasterized=True)
    ax.scatter(sx, sy, s=6, c='#08519c', marker='s', label=f'stores ({len(sx):,})', rasterized=True)
    ax.add_patch(plt.Circle((0, 0), radius_km, fill=False, lw=1.2, ls='--', color='k'))
    lim = radius_km * 1.6
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect('equal')
    ax.set_xlabel('km east of the median store location')
    ax.set_ylabel('km north of the median store location')
    ax.set_title(f"Instance {instance.split('_')[-1]} (Bogotá): the {radius_km:g}-km zone")
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.2), frameon=False, markerscale=3, handletextpad=0.2)
    _save(fig, out_dir, 'F1_zone_map')


def fig_f2(out_dir: str) -> None:
    plt = _plt()
    ppk = np.linspace(300, 3000, 400)

    def p(theta, b):
        return 1.0 / (1.0 + np.exp(-b * (np.log(ppk) - np.log(theta))))

    # CI band: envelope over the corners of the (theta, slope) intervals
    corners = [p(t, b) for t in (THETA_CI[0], THETA, THETA_CI[1]) for b in (SLOPE_CI[0], SLOPE, SLOPE_CI[1])]
    lo, hi = np.min(corners, axis=0), np.max(corners, axis=0)

    fig, ax = plt.subplots(figsize=(0.495 * TEXTWIDTH_IN, 0.37 * TEXTWIDTH_IN))   # minipage of 0.495\textwidth
    ax.fill_between(ppk, lo, hi, color='#c6dbef', alpha=0.7, label='95 % CI of the fit')
    ax.plot(ppk, p(THETA, SLOPE), c='#08519c', lw=2, label=f'manual: logit, $\\theta$ = {THETA:.0f}, $b$ = {SLOPE}')
    ax.axhline(1.0, c='#fd8d3c', lw=2, ls='--', label='auto-accept: P = 1')
    for x in (1000, 1500, 2000):
        y = float(1.0 / (1.0 + math.exp(-SLOPE * (math.log(x) - math.log(THETA)))))
        ax.plot([x], [y], 'o', c='#08519c', ms=3)
        ax.annotate(f'{y:.2f}', (x, y), textcoords='offset points', xytext=(5, -10))
    for km, lab in ((1.0, '1 km'), (2.0, '2 km'), (3.0, '3 km')):
        x = TARIFF / km
        if ppk[0] <= x <= ppk[-1]:
            ax.axvline(x, c='#bdbdbd', lw=0.8, ls=':')
            ax.annotate(f'tariff / {lab}', (x, 0.05), rotation=90, color='#636363',
                        textcoords='offset points', xytext=(2, 0))
    ax.set_xlabel('pay per km of the offered route (COP/km)')
    ax.set_ylabel('P(accept)')
    ax.set_ylim(0, 1.05)
    ax.set_xlim(ppk[0], ppk[-1])
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.28), frameon=False, ncol=1, handlelength=1.5)
    _save(fig, out_dir, 'F2_acceptance_curve')


FAMILIES = {   # sweep family -> (label, parameter symbol, ordered configs, text of the sweep range)
    'mipfair':    ('MIP-Fair ($\\alpha$)', '$\\alpha$',
                   ['mipfair_a020', 'mipfair_a025', 'mipfair_a030', 'mipfair_a035', 'mipfair_a040', 'mipfair_a100'],
                   '0.20–1.00'),
    'brkga_fair': ('BRKGA-Fair ($\\gamma$)', '$\\gamma$',
                   ['brkga_fair_w5', 'brkga_fair_w10', 'brkga_fair_w20', 'brkga_fair_w40'], '5–40'),
    'paybrkga':   ('Pay-BRKGA ($\\lambda_{pay}$)', '$\\lambda_{pay}$',
                   ['paybrkga_l01', 'paybrkga_l02', 'paybrkga_l05', 'paybrkga_l10'], '0.1–1.0'),
}
BENCH = ['greedy', 'ilp', 'hier', 'brkga']
# second generation (E10/E10b, X3 gen2): hollow markers, one dotted path per family from the first-generation
# parent through k_d = 8 to k_d = 25 (the exposure-only variants are left out: they sit on top of the parent)
GEN2_PATHS = {   # family -> (label, [(parent, None), (variant, annotation), ...])
    'mipfair':    ('MIP-Fair, 2nd gen. ($k_d$)',
                   [('mipfair_a030', None), ('mipfair_a030_xk_e000', '$k_d$ = 8'), ('mipfair_a030_xk25_e000', '$k_d$ = 25')]),
    'brkga_fair': ('BRKGA-Fair, 2nd gen. ($k_d$)',
                   [('brkga_fair_w20', None), ('brkga_fair_w20_xk', '$k_d$ = 8'),
                    ('brkga_fair_w40_xk25', '$k_d$ = 25 ($\\gamma$ = 40)')]),
    'paybrkga':   ('Pay-BRKGA, 2nd gen. ($k_d$)',
                   [('paybrkga_l05', None), ('paybrkga_l05_xk', '$k_d$ = 8')]),
}
# Where the arrow labels go (P33): one label per first-generation sweep (its range; the points of a sweep sit
# within a few thousandths of each other) and one per second-generation variant. Offsets in points from the
# labelled point, per figure and regime.
FRONTIER_LABELS = {
    ('coverage_rate', 'manual'): {'brkga_fair': (28, 21), 'mipfair': (25, -4), 'paybrkga': (25, -13),
                                  'mipfair_a030_xk_e000': (3, -21), 'mipfair_a030_xk25_e000': (-12, -18),
                                  'brkga_fair_w20_xk': (0, 14), 'brkga_fair_w40_xk25': (-21, 19),
                                  'paybrkga_l05_xk': (-20, -10)},
    ('coverage_rate', 'autoaccept'): {'brkga_fair': (28, -52), 'mipfair': (32, -25), 'paybrkga': (31, -80),
                                      'mipfair_a030_xk_e000': (5, -43), 'mipfair_a030_xk25_e000': (-18, -20),
                                      'brkga_fair_w20_xk': (-10, -90), 'brkga_fair_w40_xk25': (-15, -70),
                                      'paybrkga_l05_xk': (-6, -112)},
    ('overage_mean', 'manual'): {'brkga_fair': (31, -14), 'mipfair': (28, 18), 'paybrkga': (28, -6),
                                 'mipfair_a030_xk_e000': (3, 18), 'mipfair_a030_xk25_e000': (-21, 16),
                                 'brkga_fair_w20_xk': (0, -14), 'brkga_fair_w40_xk25': (-21, -16),
                                 'paybrkga_l05_xk': (39, 10)},
    ('overage_mean', 'autoaccept'): {'brkga_fair': (30, -14), 'mipfair': (35, 16), 'paybrkga': (34, 2),
                                     'mipfair_a030_xk_e000': (8, 19), 'mipfair_a030_xk25_e000': (-18, 14),
                                     'brkga_fair_w20_xk': (0, -16), 'brkga_fair_w40_xk25': (-15, -15),
                                     'paybrkga_l05_xk': (50, 22)},
}


def _arrow_label(ax, text, xy, off, col):
    ax.annotate(text, xy, textcoords='offset points', xytext=off, color=col, ha='center', va='center',
                arrowprops=dict(arrowstyle='-', color=col, lw=0.6, shrinkA=1, shrinkB=2))


def _frontier_panel(ax, pts: pd.DataFrame, ycol: str, regime: str) -> None:
    """pts: one row per method with columns F_Gini and <ycol>."""
    pts = pts.set_index('method')
    labels = FRONTIER_LABELS.get((ycol, regime), {})
    for fam, (lab, sym, order, rng) in FAMILIES.items():
        sub = pts.loc[[m for m in order if m in pts.index]]
        if sub.empty:
            continue
        _, col, mk, _ = POLICY_STYLE[fam]
        ax.plot(sub['F_Gini'], sub[ycol], '-', marker=mk, c=col, ms=3.5, lw=1.0, label=lab)
        if fam in labels:
            _arrow_label(ax, f'{sym} {rng}', (sub['F_Gini'].mean(), sub[ycol].mean()), labels[fam], col)
    for m in BENCH:
        if m in pts.index:
            lab, col, mk, _ = POLICY_STYLE[m]
            r = pts.loc[m]
            ax.plot([r['F_Gini']], [r[ycol]], mk, c=col, ms=5.5, label=lab, ls='none', zorder=5)
    for fam, (lab, path) in GEN2_PATHS.items():
        path = [(m, a) for m, a in path if m in pts.index]
        if len(path) < 2:
            continue
        col = POLICY_STYLE[fam][1]
        xs = [pts.loc[m, 'F_Gini'] for m, _ in path]
        ys = [pts.loc[m, ycol] for m, _ in path]
        ax.plot(xs, ys, ':', c=col, lw=1.0)
        ax.plot(xs[1:], ys[1:], 'o', mfc='white', mec=col, ms=4.5, ls='none', label=lab)
        for (m, a), x, y in zip(path[1:], xs[1:], ys[1:]):
            if m in labels:
                _arrow_label(ax, a, (x, y), labels[m], col)


def fig_frontiers(out_dir: str, main_csv: str, couriers_table: str = None, complete_seeds: bool = True,
                  extra_csvs=()) -> None:
    """F3 (coverage) and F4 (lateness) against the end-of-day Gini, one panel per regime side by side.
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
    nseeds = df['seed'].nunique()
    for name, ycol, ylabel in (('F3_pareto_coverage', 'coverage_rate', 'coverage (fraction of orders delivered)'),
                               ('F4_pareto_lateness', 'overage_mean', 'mean lateness of delivered orders (min)')):
        fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH_IN, 0.42 * TEXTWIDTH_IN), sharex=True, sharey=True)
        for ax, reg, title in zip(axes, ('manual', 'autoaccept'), ('manual regime', 'auto-accept regime')):
            _frontier_panel(ax, pts[pts.regime == reg].copy(), ycol, reg)
            ax.set_title(title)
            ax.set_xlabel('end-of-day Gini, eligible couriers')
        axes[0].set_xlim(0.285, 0.62)   # room on the right for the labels of the first-generation sweeps
        axes[0].set_ylabel(ylabel)
        handles, labels = axes[0].get_legend_handles_labels()
        seeds_txt = (f'{parts[0].seed.nunique()} seeds (first generation) and {parts[1].seed.nunique()} seeds '
                     f'(second generation, hollow markers)' if len(parts) > 1 else f'{nseeds} seed(s)')
        fig.tight_layout()
        fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False,
                   columnspacing=1.0, handletextpad=0.4,
                   title=f'mean over {inst.instance.nunique()} instances and {seeds_txt}', title_fontsize=8)
        _save(fig, out_dir, name)


SELECTED = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w40', 'mipfair_a030', 'paybrkga_l05']   # T3 configurations
SHORT = {'greedy': 'Greedy', 'ilp': 'ILP', 'hier': 'Hierarchical', 'brkga': 'BRKGA', 'brkga_fair_w40': 'BRKGA-Fair\n($\\gamma=40$)',
         'mipfair_a030': 'MIP-Fair\n($\\alpha=0.30$)', 'paybrkga_l05': 'Pay-BRKGA\n($\\lambda_{pay}=0.5$)'}


def _colour(method: str) -> str:
    return policy_style(method)[1]


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
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH_IN, 0.42 * TEXTWIDTH_IN), sharey=True)
    for ax, col, xlabel in zip(axes, ('coverage_rate', 'gini_elig_hourly'),
                               ('coverage, manual minus\nauto-accept (points)',
                                'end-of-day Gini (eligible couriers),\nmanual minus auto-accept')):
        sub = t[t.metric == col].set_index('method').reindex([m for m in methods if m in set(t.method)])
        y = np.arange(len(sub))[::-1]
        for yi, (m, r) in zip(y, sub.iterrows()):
            ax.errorbar(r['mean'], yi, xerr=[[r['mean'] - r['lo']], [r['hi'] - r['mean']]], fmt=policy_style(m)[2],
                        ms=5, color=_colour(m), ecolor=_colour(m), elinewidth=1.2, capsize=2.5)
        ax.axvline(0, color='#999999', lw=0.8, ls='--')
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT.get(m, m).replace('\n', ' ') for m in sub.index])
        ax.set_xlabel(xlabel)
        ax.grid(axis='x', lw=0.4, alpha=0.5)
    fig.suptitle(f'paired by instance ({inst.index.get_level_values(2).nunique()} instances, '
                 f'{df.seed.nunique()} seeds averaged within each); mean and 95% bootstrap interval', fontsize=8, y=1.0)
    fig.tight_layout()
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
    fig, ax = plt.subplots(figsize=(TEXTWIDTH_IN, 0.45 * TEXTWIDTH_IN))
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
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([f'{SHORT.get(m, m)}\nidle {100 * zeros[m]:.0f}%' for m in order])
    ax.set_ylabel('end-of-day earnings per\nconnected hour (COP/h)')
    ax.set_ylim(-0.03 * cap, cap * 1.02)
    ax.axhline(0, color='#999999', lw=0.6)
    ax.set_title(f'eligible couriers (connected $\\geq$ {min_shift_h:g} h), {regime} regime, seed {seed}, '
                 f'pooled over {max(n_inst.values())} instances; values above the {int(clip_q * 100)}th percentile\n'
                 f'({cap:,.0f} COP/h) are clipped; vertical bar = interquartile range, horizontal tick = median')
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
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH_IN, 0.46 * TEXTWIDTH_IN), gridspec_kw={'width_ratios': [1.5, 1]})
    ax = axes[0]
    cities = list(by_city.index)
    accents = {'Bogota': 'Bogotá', 'Medellin': 'Medellín'}
    w = 0.8 / len(by_city.columns)
    for j, m in enumerate(by_city.columns):
        ax.bar(np.arange(len(cities)) + (j - len(by_city.columns) / 2 + 0.5) * w, by_city[m], width=w,
               color=_colour(m), label=SHORT.get(m, m).replace('\n', ' '))
    ax.set_xticks(range(len(cities)))
    ax.set_xticklabels([accents.get(c, c) for c in cities], rotation=35, ha='right', rotation_mode='anchor')
    ax.set_ylabel('kg CO$_2$e per delivered order')
    ax.set_title(f'{regime} regime, mean over seeds and\ninstances of the city')
    one_line = {m: SHORT.get(m, m).split('\n')[0] for m in methods}
    ax = axes[1]
    bottom = np.zeros(len(share))
    cols = {'motorcycle': '#08519c', 'car': '#6baed6', 'bicycle': '#bdbdbd', 'walking': '#ececec'}   # not policy colours
    for v in ('motorcycle', 'car', 'bicycle', 'walking'):
        ax.bar(range(len(share)), 100 * share[f'share_{v}'], bottom=bottom, color=cols[v], label=v, width=0.7)
        bottom += 100 * share[f'share_{v}'].to_numpy()
    ax.set_xticks(range(len(share)))
    ax.set_xticklabels([one_line.get(m, m) for m in share.index], rotation=45, ha='right', rotation_mode='anchor')
    ax.set_ylabel('share of distance by vehicle type (%)')
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc='lower left', bbox_to_anchor=(1.0, 0.0), ncol=1, handlelength=1.0)
    ax.set_title(f'{e.instance.nunique()} instances pooled,\n{regime} regime')
    fig.tight_layout()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False,
               columnspacing=1.0, handlelength=1.0, handletextpad=0.4)
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
