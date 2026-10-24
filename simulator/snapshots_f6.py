"""
snapshots_f6.py -- F6: intraday trajectory of the end-of-day Gini statistic on one zone-day.

Runs one configuration of batch_paper's catalogue (same Config as run_cell) on one instance and saves the
delivery log (courier_id, delivery_time_min, pay) and the couriers with their connection window, so that the
Gini coefficient of earnings per connected hour can be recomputed at any time of the day ex post:

    python snapshots_f6.py run  --method greedy       --instance Instancia_0 --seed 1 [--regime manual]
    python snapshots_f6.py run  --method hier ...
    python snapshots_f6.py run  --method mipfair_a030 ...
    python snapshots_f6.py plot --instance Instancia_0 --methods greedy hier mipfair_a030 [--alpha 0.40]

Outputs in output/paper/f6/<instance>_<method>_<regime>_s<seed>_{deliveries,couriers}.csv and the figure
docs/paper-cmdp/paper/figures/F6_intraday_gini.{pdf,png} (+ .csv with the curves).

Populations (decision E9): "eligible" = declared shift >= 60 min, connected up to t, idle ones at zero
(the statistic of the paper); "active" = couriers with at least one delivery up to t (the statistic read by
the first-generation policies and by metrics.F_Gini).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
OUT_DIR = os.path.join(THIS_DIR, 'output', 'paper', 'f6')
FIG_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'docs', 'paper-cmdp', 'paper', 'figures'))
MIN_SHIFT_MIN = 60.0


def gini(values) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    n = len(v)
    if n == 0 or v.sum() <= 0:
        return 0.0
    i = np.arange(1, n + 1)
    return float((2.0 * (i * v).sum()) / (n * v.sum()) - (n + 1.0) / n)


def run(args) -> None:
    from batch_paper import METHODS, GEN2, ABLATIONS, DEFAULT_INSTANCES_DIR, PPK_THRESHOLD_POINT
    from config import Config
    from loader_real import load_real_instance
    from run import build_policy, run_simulation

    cat = {**METHODS, **GEN2, **ABLATIONS}
    spec = cat[args.method]
    cfg_kwargs = dict(seed=args.seed, sim_start_clock_min=0.0, sim_end=1440.0,
                      acceptance_mode='logit_ppk', accept_regime=args.regime,
                      accept_ppk_threshold=PPK_THRESHOLD_POINT, real_max_radius_km=3.0, real_circuity=1.3,
                      ilp_solver=args.solver, ilp_time_limit_sec=10.0, max_bundle_size=3)
    cfg_kwargs.update(spec['cfg'])
    cfg = Config(**cfg_kwargs)
    instance = load_real_instance(args.instance, DEFAULT_INSTANCES_DIR, cfg)
    policy = build_policy(spec['policy'], cfg)
    results, m = run_simulation(cfg, instance, policy=policy, policy_name=spec['policy'], verbose=False)
    os.makedirs(OUT_DIR, exist_ok=True)
    stem = os.path.join(OUT_DIR, f'{args.instance}_{args.method}_{args.regime}_s{args.seed}')
    pd.DataFrame(results.get('delivery_log', [])).to_csv(stem + '_deliveries.csv', index=False)
    cour = []
    for c in instance['couriers']:
        cour.append({'courier_id': c.courier_id, 'vehicle': getattr(c, 'vehicle', ''),
                     'on_time': float(c.on_time), 'off_time': float(c.off_time)})
    pd.DataFrame(cour).to_csv(stem + '_couriers.csv', index=False)
    print(f"{args.method}: coverage {m.get('coverage_rate')}, F_Gini {m.get('F_Gini')}, "
          f"{len(results.get('delivery_log', []))} deliveries, {len(cour)} couriers -> {stem}_*.csv")


def trajectory(deliveries: pd.DataFrame, couriers: pd.DataFrame, step_min: float = 10.0) -> pd.DataFrame:
    d = deliveries.sort_values('delivery_time_min')
    c = couriers.set_index('courier_id')
    shift = c['off_time'] - c['on_time']
    elig_ids = c.index[shift >= MIN_SHIFT_MIN]
    rows = []
    for t in np.arange(step_min, 1440.0 + step_min / 2, step_min):
        earned = d[d['delivery_time_min'] <= t].groupby('courier_id')['pay'].sum()
        on = c.index[c['on_time'] <= t]
        pop = elig_ids.intersection(on)
        hours = (np.minimum(t, c.loc[pop, 'off_time']) - c.loc[pop, 'on_time']).clip(lower=1e-9) / 60.0
        earn = earned.reindex(pop).fillna(0.0)
        hourly_elig = (earn / hours)
        act = earned.index.intersection(c.index)
        hours_act = (np.minimum(t, c.loc[act, 'off_time']) - c.loc[act, 'on_time']).clip(lower=1e-9) / 60.0
        hourly_act = earned.loc[act] / hours_act
        rows.append({'time_min': t, 'n_eligible_connected': len(pop), 'n_active': len(act),
                     'gini_elig': gini(hourly_elig) if len(pop) else np.nan,
                     'gini_active': gini(hourly_act) if len(act) else np.nan,
                     'share_active_elig': float((earn > 0).mean()) if len(pop) else np.nan})
    return pd.DataFrame(rows)


LABEL = {'greedy': 'Greedy', 'hier': 'Hierarchical', 'ilp': 'ILP', 'brkga': 'BRKGA'}
COLOUR = {'greedy': 'k', 'hier': '#969696', 'ilp': '#2171b5', 'brkga': '#41ab5d'}


def _label(m: str) -> str:
    if m in LABEL:
        return LABEL[m]
    if m.startswith('mipfair'):
        return 'MIP-Fair' + (' (2nd gen.)' if '_x' in m else '')
    if m.startswith('brkga_fair'):
        return 'BRKGA-Fair' + (' (2nd gen.)' if '_x' in m else '')
    if m.startswith('paybrkga'):
        return 'Pay-BRKGA'
    return m


def _colour(m: str) -> str:
    if m in COLOUR:
        return COLOUR[m]
    if m.startswith('mipfair'):
        return '#d94801' if '_x' not in m else '#fd8d3c'
    if m.startswith('brkga_fair'):
        return '#238b45' if '_x' not in m else '#74c476'
    return '#6a51a3'


def plot(args) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 150})
    curves = {}
    for m in args.methods:
        stem = os.path.join(OUT_DIR, f'{args.instance}_{m}_{args.regime}_s{args.seed}')
        if not os.path.exists(stem + '_deliveries.csv'):
            print('missing', stem)
            continue
        curves[m] = trajectory(pd.read_csv(stem + '_deliveries.csv'), pd.read_csv(stem + '_couriers.csv'))
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.3), sharex=True)
    for m, t in curves.items():
        h = t['time_min'] / 60.0
        axes[0].plot(h, t['gini_elig'], color=_colour(m), lw=1.4, label=_label(m))
        axes[1].plot(h, t['gini_active'], color=_colour(m), lw=1.4, label=_label(m))
    for ax, title in zip(axes, ('eligible couriers connected so far, idle at zero (Eq. of the paper)',
                               'active couriers so far (statistic read by the first-generation policies)')):
        ax.axhline(args.alpha, color='#999999', lw=0.8, ls='--')
        ax.text(0.3, args.alpha + 0.01, f'$\\alpha$ = {args.alpha:.2f}', fontsize=7, color='#666666')
        ax.set_xlabel('time of day (h)')
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_ylim(0, 1)
        ax.set_title(title, fontsize=7.5)
    axes[0].set_ylabel('Gini of earnings per connected hour so far')
    axes[0].legend(fontsize=7, frameon=False, loc='upper right')
    fig.suptitle(f'{args.instance} ({args.regime} regime, seed {args.seed})', fontsize=8, y=1.0)
    os.makedirs(FIG_DIR, exist_ok=True)
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(FIG_DIR, f'F6_intraday_gini.{ext}'), bbox_inches='tight')
    out = pd.concat([t.assign(method=m) for m, t in curves.items()], ignore_index=True)
    out.to_csv(os.path.join(FIG_DIR, 'F6_intraday_gini.csv'), index=False)
    print('wrote', os.path.join(FIG_DIR, 'F6_intraday_gini.pdf'))
    # numbers for the prose: the time at which each curve first goes below alpha and the end-of-day values
    for m, t in curves.items():
        peak = t.loc[t['gini_elig'].idxmax()]
        below = t[(t['gini_elig'] <= args.alpha) & (t['time_min'] > peak['time_min'])]
        first = below['time_min'].iloc[0] / 60.0 if len(below) else None
        print(f"{m:>22}: peak elig {peak['gini_elig']:.3f} at {peak['time_min'] / 60:.1f} h; first <= alpha at "
              f"{first if first is None else round(first, 1)} h; end elig {t['gini_elig'].iloc[-1]:.3f}, "
              f"end active {t['gini_active'].iloc[-1]:.3f}, active share {t['share_active_elig'].iloc[-1]:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['run', 'plot'])
    ap.add_argument('--method', default='greedy')
    ap.add_argument('--methods', nargs='+', default=['greedy', 'hier', 'mipfair_a030'])
    ap.add_argument('--instance', default='Instancia_0')
    ap.add_argument('--regime', default='manual', choices=['manual', 'autoaccept'])
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--solver', default='GUROBI')
    ap.add_argument('--alpha', type=float, default=0.40)
    args = ap.parse_args()
    run(args) if args.cmd == 'run' else plot(args)


if __name__ == '__main__':
    main()
