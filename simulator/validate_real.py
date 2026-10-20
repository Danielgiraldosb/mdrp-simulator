"""
Face validation of the real-instance loader + calibrated acceptance (Etapa 2).

Runs the greedy policy on one or more real instances under both
courier regimes and compares per-courier medians against the 2021 survey
(docs/Encuesta_cuantitativo_domiciliarios.xlsx, sheets Ingreso / Racha):

    orders per day (no 'racha')            median 4
    orders per connected hour (no racha)   median 0.35   (1.15 in racha)
    income per connected hour (COP)        median 2,622  (P25 1,931 / P75 3,405)

No match is expected -- the simulator has one platform, one day and flat
pay -- only the same order of magnitude, with the gaps explained in
docs/paper-cmdp/modelo-vs-evidencia.md.

Usage
-----
  python validate_real.py --instances Instancia_22 Instancia_4 --seeds 3
  python validate_real.py --instances Instancia_22 --pickup-service 5 60
"""
from __future__ import annotations

import argparse
import os
import statistics as st
import time
from typing import Dict, List

import pandas as pd

from config import Config
from loader_real import load_real_instance
from metrics import courier_table
from run import build_policy, run_simulation

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'real_instancies'))

SURVEY = {
    'orders_per_day_median':   4.0,
    'orders_per_hr_median':    0.35,
    'orders_per_hr_racha':     1.15,
    'earn_per_hr_median':      2622.38,
    'earn_per_hr_p25':         1931.16,
    'earn_per_hr_p75':         3404.89,
    'smmlv_per_hr':            4367.91,
}


def _median(xs: List[float]) -> float:
    return st.median(xs) if xs else float('nan')


def summarize(rows: List[Dict], cfg: Config) -> Dict[str, float]:
    """Medians over couriers that logged on; 'active' = delivered >= 1 order."""
    active = [r for r in rows if r['orders'] > 0]
    shift_h = [r['shift_h'] for r in rows]
    return {
        'n_couriers':            len(rows),
        'n_active':              len(active),
        'share_active':          round(len(active) / len(rows), 3) if rows else float('nan'),
        'shift_h_median':        round(_median(shift_h), 2),
        'orders_median_all':     _median([r['orders'] for r in rows]),
        'orders_median_active':  _median([r['orders'] for r in active]),
        'orders_per_hr_active':  round(_median([r['orders_per_hr'] for r in active]), 3),
        'earn_per_hr_active':    round(_median([r['order_earnings'] / r['shift_h']
                                                for r in active if r['shift_h'] > 0]), 1),
        'earn_per_hr_all':       round(_median([r['order_earnings'] / r['shift_h']
                                                for r in rows if r['shift_h'] > 0]), 1),
        'share_below_smmlv':     round(sum(1 for r in active if r['shift_h'] > 0 and
                                           r['order_earnings'] / r['shift_h'] < SURVEY['smmlv_per_hr'])
                                       / max(1, len(active)), 3),
    }


def run_one(instance_name: str, instances_dir: str, regime: str, seed: int,
            pickup_service: float, circuity: float) -> Dict:
    cfg = Config(seed=seed, acceptance_mode='logit_ppk', accept_regime=regime,
                 real_circuity=circuity)
    cfg.real_pickup_service_min = pickup_service
    inst = load_real_instance(instance_name, instances_dir, cfg)
    policy = build_policy('greedy', cfg)
    t0 = time.perf_counter()
    results, m = run_simulation(cfg, inst, policy, 'greedy', verbose=False)
    rows = courier_table(results['couriers'], cfg)
    out = {'instance': instance_name, 'city': inst['meta']['city'], 'regime': regime, 'seed': seed,
           'pickup_service_min': pickup_service, 'circuity': circuity,
           'n_orders': m['n_orders'], 'coverage_rate': round(m['coverage_rate'], 3),
           'c2d_mean': round(m['c2d_mean'], 1),
           'n_rejections': len(results.get('rejection_log', [])),
           'wall_sec': round(time.perf_counter() - t0, 1)}
    out.update(summarize(rows, cfg))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--instances', nargs='+', default=['Instancia_22'])
    ap.add_argument('--instances-dir', default=DEFAULT_DIR)
    ap.add_argument('--regimes', nargs='+', default=['manual', 'autoaccept'], choices=['manual', 'autoaccept'])
    ap.add_argument('--seeds', type=int, default=3, help='replications per cell (acceptance is Bernoulli)')
    ap.add_argument('--pickup-service', type=float, nargs='+', default=[20.0])
    ap.add_argument('--circuity', type=float, default=1.0)
    ap.add_argument('--out', default=os.path.join(THIS_DIR, 'output', 'validation_real.csv'))
    args = ap.parse_args()

    rows = []
    for inst in args.instances:
        for ps in args.pickup_service:
            for regime in args.regimes:
                for seed in range(args.seeds):
                    r = run_one(inst, args.instances_dir, regime, seed, ps, args.circuity)
                    rows.append(r)
                    print(f"  {inst} {regime:10s} seed={seed} ps={ps:g}: coverage={r['coverage_rate']:.3f} "
                          f"active={r['n_active']}/{r['n_couriers']} orders/active={r['orders_median_active']} "
                          f"orders/h={r['orders_per_hr_active']} COP/h={r['earn_per_hr_active']} "
                          f"rejections={r['n_rejections']} [{r['wall_sec']}s]")

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)

    keys = ['coverage_rate', 'share_active', 'orders_median_active', 'orders_per_hr_active',
            'earn_per_hr_active', 'share_below_smmlv', 'n_rejections']
    print("\n-- Medians over seeds, vs survey ----------------------------------------------")
    agg = df.groupby(['instance', 'pickup_service_min', 'regime'])[keys].median()
    pd.set_option('display.width', 160)
    print(agg.to_string())
    print(f"\n  survey: orders/day (no racha) {SURVEY['orders_per_day_median']}, "
          f"orders/h {SURVEY['orders_per_hr_median']} (racha {SURVEY['orders_per_hr_racha']}), "
          f"COP/h {SURVEY['earn_per_hr_median']:.0f} [P25 {SURVEY['earn_per_hr_p25']:.0f}, "
          f"P75 {SURVEY['earn_per_hr_p75']:.0f}], 91.9 % below SMMLV/h {SURVEY['smmlv_per_hr']:.0f}")
    print(f"  written: {args.out}")


if __name__ == '__main__':
    main()
