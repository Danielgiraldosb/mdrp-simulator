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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fig', nargs='+', default=['f1', 'f2'], choices=['f1', 'f2'])
    ap.add_argument('--out', default=os.path.normpath(os.path.join(THIS_DIR, '..', 'docs', 'paper-cmdp', 'figures')))
    args = ap.parse_args()
    if 'f1' in args.fig:
        fig_f1(args.out)
    if 'f2' in args.fig:
        fig_f2(args.out)


if __name__ == '__main__':
    main()
