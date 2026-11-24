"""
analysis_objections.py -- evidence for referee objections 2 (oversupply) and 3 (population chosen a posteriori)
from EXISTING data only (instances + per-courier tables of the runs); no simulation.

Objection 2: supply/demand per clock hour in each zone (3 km, the loader of the runs). For every instance and
clock hour h: orders placed in h over courier-hours connected in h. Share of connected courier-hours that fall
in clock hours whose ratio reaches the survey's in-ladder 1.15 orders per connected hour (and other cut-offs);
same with the fleet thinned to one in three (ratio x 3). Plus, per policy, the share of eligible couriers (and of
their connected hours) whose realised day ratio orders/shift_h reaches 1.15.

Objection 3: Gini of earnings over populations not defined by a connection-hours threshold, idle at zero:
  P0  all couriers of the zone (no threshold), hourly earnings (payment / shift_h)
  P1  couriers connected at any moment of the zone's busiest clock hour (by orders placed), hourly earnings
  P2  couriers connected over the zone's two busiest clock hours (any overlap), earnings per order placed in the
      zone while connected (demand-weighted exposure, no hours)
  P3  all couriers of the zone, earnings per order placed while connected (demand-weighted exposure)
Seeds 1-5 (shared by X1, the second generation and the k_d = 50 supplement).

  python analysis_objections.py   (writes objections_out/*.csv and prints a summary)
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = r'C:\MDRP'
SIM = os.path.join(ROOT, 'simulator')
sys.path.insert(0, SIM)
from config import Config  # noqa: E402
from loader_real import load_real_instance  # noqa: E402
from analyze_couriers import gini  # noqa: E402

O = os.path.join(SIM, 'output', 'paper')
INST = os.path.join(ROOT, 'real_instancies')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'paper', 'objections')
os.makedirs(OUT, exist_ok=True)

CONFIGS = {  # method -> (csv, label)
    'greedy': ('main.csv', 'Greedy'), 'ilp': ('main.csv', 'ILP'), 'hier': ('main.csv', 'Hierarchical'),
    'brkga': ('main.csv', 'BRKGA'), 'brkga_fair_w40': ('main.csv', 'BRKGA-Fair g40'),
    'mipfair_a030': ('main.csv', 'MIP-Fair a0.30'), 'paybrkga_l05': ('main.csv', 'Pay-BRKGA l0.5'),
    'brkga_fair_w40_xk25': ('gen2.csv', 'BRKGA-Fair kd25'), 'mipfair_a030_xk25_e000': ('gen2.csv', 'MIP-Fair kd25'),
    'brkga_fair_w40_xk50': ('supp.csv', 'BRKGA-Fair kd50'),
}
SEEDS = [1, 2, 3, 4, 5]
CUTS = (0.75, 1.0, 1.15)


def zone(name: str):
    cfg = Config(real_max_radius_km=3.0, acceptance_mode='logit_ppk')
    inst = load_real_instance(name, INST, cfg)
    on = {c.courier_id: (c.on_time / 60.0, c.off_time / 60.0) for c in inst['couriers']}
    plac = np.array([o.placement_time / 60.0 for o in inst['orders']])
    return on, plac


def hourly_profile(on: dict, plac: np.ndarray) -> pd.DataFrame:
    hrs = np.arange(24)
    orders = np.array([((plac >= h) & (plac < h + 1)).sum() for h in hrs], dtype=float)
    ch = np.zeros(24)
    for a, b in on.values():
        for h in hrs:
            ch[h] += max(0.0, min(b, h + 1) - max(a, h))
    return pd.DataFrame({'hour': hrs, 'orders': orders, 'courier_h': ch,
                         'ratio': np.where(ch > 0, orders / np.maximum(ch, 1e-9), np.nan)})


def main() -> None:
    runs = []
    for m, (f, _) in CONFIGS.items():
        d = pd.read_csv(os.path.join(O, f))
        runs.append(d[(d.method == m) & d.seed.isin(SEEDS)][['run_id', 'instance', 'city', 'method', 'regime', 'seed',
                                                               'n_couriers_loaded', 'n_orders']])
    runs = pd.concat(runs, ignore_index=True)
    print('runs', len(runs), runs.groupby(['method', 'regime']).size().unique())

    prof_rows, run_rows = [], []
    for inst, g in runs.groupby('instance'):
        on, plac = zone(inst)
        prof = hourly_profile(on, plac)
        prof['instance'] = inst
        prof['city'] = g.city.iloc[0]
        prof_rows.append(prof)
        top = prof.sort_values('orders', ascending=False).hour.tolist()
        peak1, peak2 = top[0], sorted(top[:2])
        # orders placed while each courier was connected (demand-weighted exposure)
        ps = np.sort(plac)
        expo = {c: float(np.searchsorted(ps, b) - np.searchsorted(ps, a)) for c, (a, b) in on.items()}
        pres1 = {c for c, (a, b) in on.items() if a < peak1 + 1 and b > peak1}
        pres2 = {c for c, (a, b) in on.items() if any(a < h + 1 and b > h for h in peak2)}
        if g.n_couriers_loaded.iloc[0] != len(on) or g.n_orders.iloc[0] != len(plac):
            print('WARNING size mismatch', inst, g.n_couriers_loaded.iloc[0], len(on), g.n_orders.iloc[0], len(plac))
        for r in g.itertuples():
            t = pd.read_csv(os.path.join(O, 'couriers', f'{r.run_id}.csv'),
                            usecols=['courier_id', 'shift_h', 'payment', 'orders'])
            t['hourly'] = t.payment / t.shift_h.clip(lower=1e-9)
            t['expo'] = t.courier_id.map(expo)
            t['per_order_avail'] = t.payment / t.expo.clip(lower=1.0)
            el = t[t.shift_h >= 1.0]
            row = {'run_id': r.run_id, 'instance': inst, 'city': r.city, 'method': r.method, 'regime': r.regime,
                   'seed': r.seed, 'peak_hour': peak1,
                   'FG_check': gini(el.hourly),
                   'P0_all_hourly': gini(t.hourly),
                   'P1_peak_hourly': gini(t[t.courier_id.isin(pres1)].hourly),
                   'P1_active': float((t[t.courier_id.isin(pres1)].orders > 0).mean()),
                   'P1_n_share': len(pres1) / len(t),
                   'P2_peak2_expo': gini(t[t.courier_id.isin(pres2)].per_order_avail),
                   'P3_all_expo': gini(t.per_order_avail),
                   'P4_elig_expo': gini(el.per_order_avail),
                   'shift_check': float((t.courier_id.map(lambda c: on[c][1] - on[c][0]) - t.shift_h).abs().max())}
            dr = el.orders / el.shift_h
            for c in CUTS:
                row[f'elig_share_ge{c:g}'] = float((dr >= c).mean())
                row[f'elig_hshare_ge{c:g}'] = float(el.shift_h[dr >= c].sum() / el.shift_h.sum())
            run_rows.append(row)
        print(inst, 'done', flush=True)

    prof = pd.concat(prof_rows, ignore_index=True)
    prof.to_csv(os.path.join(OUT, 'hourly_profile.csv'), index=False)
    res = pd.DataFrame(run_rows)
    res.to_csv(os.path.join(OUT, 'per_run_alt_populations.csv'), index=False)

    # check FG against the courier tables
    cour = pd.concat([pd.read_csv(os.path.join(O, f), usecols=['run_id', 'gini_elig_hourly'])
                      for f in ('main_couriers.csv', 'gen2_couriers.csv', 'supp_couriers.csv')]).drop_duplicates('run_id')
    m = res.merge(cour, on='run_id')
    print(f'\ncheck FG ({len(m)} runs): max |diff| = {(m.FG_check - m.gini_elig_hourly).abs().max():.2e}; '
          f'max |shift diff| = {res.shift_check.max():.3f} h')

    # ---- Objection 2: hours in in-ladder conditions
    lines = ['== Objection 2: zone supply/demand by clock hour (24 instances)']
    tot = prof.courier_h.sum()
    lines.append(f'pooled orders / courier-hour: {prof.orders.sum() / tot:.3f}; '
                 f'mean of instance ratios {prof.groupby("instance").apply(lambda d: d.orders.sum() / d.courier_h.sum()).mean():.3f}')
    for c in CUTS:
        for k, lab in ((1, 'full fleet'), (3, 'fleet / 3')):
            sh = prof.courier_h[prof.ratio * k >= c].sum() / tot
            per_inst = prof.groupby('instance').apply(lambda d: d.courier_h[d.ratio * k >= c].sum() / d.courier_h.sum())
            lines.append(f'share of courier-hours in clock hours with ratio >= {c:g} ({lab}): pooled {sh:.3f}; '
                         f'by instance median {per_inst.median():.3f}, range {per_inst.min():.3f}-{per_inst.max():.3f}, '
                         f'instances with any such hour {(prof.groupby("instance").apply(lambda d: (d.ratio * k >= c).any())).sum()}')
    mx = prof.groupby('instance').ratio.max()
    lines.append(f'max hourly ratio by instance: median {mx.median():.3f}, range {mx.min():.3f}-{mx.max():.3f}')
    pk = prof.loc[prof.groupby('instance').orders.idxmax()]
    lines.append(f'ratio in the busiest hour: median {pk.ratio.median():.3f}, range {pk.ratio.min():.3f}-{pk.ratio.max():.3f}; '
                 f'busiest hours {sorted(pk.hour.tolist())}')
    # ---- per policy
    inst_mean = res.groupby(['regime', 'method', 'instance']).mean(numeric_only=True)
    tab = inst_mean.groupby(['regime', 'method']).mean()
    cols2 = [f'elig_share_ge{c:g}' for c in CUTS] + [f'elig_hshare_ge{c:g}' for c in CUTS]
    cols3 = ['FG_check', 'P0_all_hourly', 'P1_peak_hourly', 'P1_active', 'P1_n_share', 'P2_peak2_expo',
             'P3_all_expo', 'P4_elig_expo']
    order = list(CONFIGS)
    for reg in ('manual', 'autoaccept'):
        t = tab.loc[reg].reindex(order)
        t.index = [CONFIGS[i][1] for i in t.index]
        lines.append(f'\n== {reg}: eligible couriers with realised day orders/h >= cut (share of couriers, of hours)')
        lines.append(t[cols2].round(3).to_string())
        lines.append(f'\n== {reg}: Gini by alternative population (idle at zero), mean over 24 instances, seeds 1-5')
        lines.append(t[cols3].round(3).to_string())
        # Greedy rank per population
        for c in ['FG_check', 'P0_all_hourly', 'P1_peak_hourly', 'P2_peak2_expo', 'P3_all_expo', 'P4_elig_expo']:
            s = t[c]
            others = s.drop('Greedy')
            lines.append(f'{c}: Greedy {s["Greedy"]:.3f}; best other {others.min():.3f} ({others.idxmin()}); '
                         f'first-gen order-centric range {s.iloc[1:7].min():.3f}-{s.iloc[1:7].max():.3f}')
        # paired diff vs greedy per instance for P1 and P2
        g = inst_mean.loc[reg]
        for c in ['P1_peak_hourly', 'P2_peak2_expo']:
            gr = g.xs('greedy', level='method')[c]
            worst = min((g.xs(mm, level='method')[c] - gr).min() for mm in order[1:7])
            lines.append(f'{c}: smallest instance-level difference (first-gen order-centric - Greedy) {worst:+.3f}')
    txt = '\n'.join(lines)
    open(os.path.join(OUT, 'summary.txt'), 'w', encoding='utf-8').write(txt + '\n')
    print(txt)


if __name__ == '__main__':
    main()
