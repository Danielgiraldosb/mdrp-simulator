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
    ax.set_xlabel('end-of-day Gini of hourly earnings, eligible couriers')
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9)


def fig_frontiers(out_dir: str, main_csv: str, couriers_table: str = None, complete_seeds: bool = True) -> None:
    """F3 (coverage) and F4 (lateness) against the end-of-day Gini, one panel per regime.
    With couriers_table (analyze_couriers.py --out) the x-axis is the Gini over the ELIGIBLE couriers
    (decision E9, 2026-10-21); without it, the active-courier F_Gini of metrics.py."""
    plt = _plt()
    df = pd.read_csv(main_csv)
    if couriers_table:
        ct = pd.read_csv(couriers_table)[['run_id', 'gini_elig_hourly']]
        df = df.merge(ct, on='run_id', how='inner')
        df['F_Gini'] = df['gini_elig_hourly']
    if complete_seeds:
        cnt = df.groupby('seed')['run_id'].count()
        df = df[df['seed'].isin(cnt[cnt == cnt.max()].index)]
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
        axes[0].legend(fontsize=6.5, frameon=False, loc='best')
        fig.suptitle(f'mean over {inst.instance.nunique()} instances and {nseeds} seed(s)', fontsize=7, y=0.99)
        _save(fig, out_dir, name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fig', nargs='+', default=['f1', 'f2'], choices=['f1', 'f2', 'f3f4'])
    ap.add_argument('--out', default=os.path.normpath(os.path.join(THIS_DIR, '..', 'docs', 'paper-cmdp', 'paper', 'figures')))
    ap.add_argument('--main-csv', default=os.path.join(THIS_DIR, 'output', 'paper', 'main.csv'))
    ap.add_argument('--couriers-table', default=os.path.join(THIS_DIR, 'output', 'paper', 'main_couriers.csv'),
                    help='analyze_couriers.py --out table; the x-axis of F3/F4 is then the eligible-courier Gini (E9)')
    args = ap.parse_args()
    if 'f1' in args.fig:
        fig_f1(args.out)
    if 'f2' in args.fig:
        fig_f2(args.out)
    if 'f3f4' in args.fig:
        fig_frontiers(args.out, args.main_csv, args.couriers_table if os.path.exists(args.couriers_table) else None)


if __name__ == '__main__':
    main()
