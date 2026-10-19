"""
Entry point for the mdrplib-adapted MDRP simulator.

-- Basics -----------------------------------------------------------------------
  python run.py --list
  python run.py --instance 0o100t100s1p100
  python run.py --instance 0o100t100s1p100 --from 07:00 --until 23:00

-- Policies / objectives -------------------------------------------------------
  python run.py --instance 0o100t100s1p100 --policy fair_greedy
  python run.py --instance 0o100t100s1p100 --ilp --objective max_equity
  python run.py --instance 0o100t100s1p100 --compare

-- Bundling / tolerance ----------------------------------------------------------
  python run.py --instance 0o100t100s1p100 --bundle 3
  python run.py --instance 0o100t100s1p100 --late-tolerance 5

-- Acceptance mode (transversal to every policy -- see acceptance.py) -----------
  python run.py --instance 0o100t100s1p100 --acceptance-mode auto        # default: always accepts
  python run.py --instance 0o100t100s1p100 --acceptance-mode fixed --acceptance-range 0.5 1.0
  python run.py --instance 0o100t100s1p100 --ilp --objective max_equity --acceptance-mode logistic

-- Thesis extensions (off by default -- see config.py) --------------------------
  python run.py --instance 0o100t100s1p100 --cancellation
  python run.py --instance 0o100t100s1p100 --reposition

-- Output -------------------------------------------------------------------------
  python run.py --instance 0o100t100s1p100 --save
"""
import os
import time
import logging
import argparse

import simpy
import pandas as pd

from config import Config
from loader import load_instance, list_instances
from simulator import MDRPSimulator
from policies import GreedyPolicy, FairGreedyPolicy
from metrics import (compute_metrics, courier_table, delivery_detail_table,
                     cancellation_table, rejection_table, snapshot_table)

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s  %(levelname)-8s  %(message)s'
)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
# This simulator lives inside mdrplib-master/simulator/, right next to
# public_instances/ -- no absolute-path configuration needed or to go stale.
DEFAULT_INSTANCES_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'public_instances'))


def _hm_to_min(hm: str) -> float:
    parts = hm.strip().split(':')
    return int(parts[0]) * 60 + int(parts[1])


# -- Policy factory ----------------------------------------------------------------

def build_policy(name: str, cfg: Config):
    if name == 'greedy':
        return GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)
    if name == 'fair_greedy':
        return FairGreedyPolicy(pay_per_order=cfg.pay_per_order,
                                equity_bonus=0.3 * cfg.pay_per_order, cfg=cfg)
    if name == 'ilp':
        from ilp_policy import ILPPolicy
        return ILPPolicy(cfg)
    if name in ('mdrpsim_greedy', 'mdrpsim_mip', 'mdrpsim_graph', 'mdrpsim_graph_prospects'):
        from mdrpsim_policies import build_mdrpsim_policy
        return build_mdrpsim_policy(name, cfg)
    raise ValueError(f"Unknown policy '{name}'. Choices: greedy | fair_greedy | ilp | "
                     f"mdrpsim_greedy | mdrpsim_mip | mdrpsim_graph | mdrpsim_graph_prospects. "
                     f"(Acceptance criterion is set separately via --acceptance-mode.)")


# -- Core simulation runner ---------------------------------------------------------

def run_simulation(cfg: Config, instance: dict,
                   policy=None, policy_name: str = 'greedy',
                   verbose: bool = True) -> tuple:
    if policy is None:
        policy = GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)

    n_orders, n_couriers = len(instance['orders']), len(instance['couriers'])

    if verbose:
        print(f"\n{'='*66}")
        print(f"  MDRP Simulator (mdrplib)  -  Policy: {policy_name.upper()}")
        print(f"  {n_orders:,} orders  .  {n_couriers:,} couriers  .  "
              f"speed={cfg.meters_per_minute:.0f} m/min  .  Horizon: {cfg.rolling_horizon:.0f} min")
        print(f"  Objective: {cfg.objective}  .  Bundle: {cfg.max_bundle_size}  .  "
              f"Acceptance: {cfg.acceptance_mode}  .  "
              f"Cancellation: {'ON' if cfg.enable_cancellation else 'OFF'}")
        print(f"{'='*66}")

    env = simpy.Environment()
    sim = MDRPSimulator(env, instance, policy, cfg)
    sim.start()

    t0 = time.perf_counter()
    env.run(until=cfg.sim_end)
    wall_clock_sec = time.perf_counter() - t0

    results = sim.get_results()
    m = compute_metrics(results, cfg, wall_clock_sec=wall_clock_sec)

    if verbose:
        _print_metrics(m, cfg)
        _print_courier_table(results, cfg)

    return results, m


def _print_metrics(m: dict, cfg: Config = None):
    print(f"\n-- Service metrics " + "-" * 47)
    print(f"  Coverage rate         : {m['coverage_rate']*100:6.1f}%")
    print(f"  Orders delivered      : {m['n_delivered']:,} / {m['n_orders']:,}")
    print(f"  Canceled              : {m['n_canceled']:,}")
    print(f"  Click-to-door   (mean): {m['c2d_mean']:6.1f} min  "
          f"(p90: {m['c2d_p90']:.1f})")
    print(f"  Overage vs target     : {m['overage_mean']:6.1f} min  (mean)")
    print(f"  Ready-to-door   (mean): {m['r2d_mean']:6.1f} min")
    print(f"  Ready-to-pickup (mean): {m['r2p_mean']:6.1f} min")
    print(f"  Bundle size     (mean): {m['bundle_size_mean']:5.2f}")
    print(f"  Throughput cost       : {m['throughput_cost']:8.3f}")

    print(f"\n-- Economic & fairness " + "-" * 43)
    print(f"  Active couriers                 : {m['n_couriers_active']}")
    print(f"  Total payment                   : {m['total_payment']:,.2f}")
    print(f"  Proportion receiving true-up    : {m['proportion_trueup']*100:5.1f}%")
    print(f"  Mean hourly earnings            : {m['mean_hourly_earn']:,.2f}")
    print(f"  F_Gini   (earnings inequality)  : {m['F_Gini']:.4f}")
    print(f"  F_MaxMin (min hourly earnings)  : {m['F_MaxMin']:,.2f}")
    print(f"  F_Orders (orders/hr inequality) : {m['F_Orders']:.4f}")
    print(f"  F_Deficit(below wage threshold) : {m['F_Deficit']*100:.1f}%")
    print(f"  F_Dist   (distance inequality)  : {m['F_Dist']:.4f}")

    print(f"\n-- Compute time (wall-clock, real seconds) " + "-" * 23)
    print(f"  Total run time                  : {m.get('wall_clock_sec', 0):,.3f} s")
    print(f"  Dispatch rounds with a decision : {m.get('solve_calls', 0):,}")
    print(f"  assign() time  mean / p90 / max : "
          f"{m.get('solve_mean', 0):.4f} / {m.get('solve_p90', 0):.4f} / {m.get('solve_max', 0):.4f} s")
    if cfg is not None:
        budget = cfg.rolling_horizon * 60.0
        worst = m.get('solve_max', 0)
        verdict = 'dentro del presupuesto' if worst <= budget else 'EXCEDE el presupuesto'
        print(f"  Presupuesto por ronda (rolling_horizon={cfg.rolling_horizon:.0f} min): "
              f"{budget:,.0f} s  ->  peor caso {verdict}")


def _print_courier_table(results: dict, cfg: Config):
    rows = courier_table(results['couriers'], cfg)
    if not rows:
        return
    df = pd.DataFrame(rows)
    df = df[df['orders'] > 0].sort_values('earn_per_hr', ascending=False)
    if df.empty:
        return
    print(f"\n-- Courier summary (top 15 by hourly earnings) " + "-" * 18)
    print(df.head(15).to_string(index=False))


def compare_policies(cfg: Config, instance: dict, policies: dict = None,
                     verbose: bool = True):
    if policies is None:
        policies = {
            'greedy':      GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg),
            'fair_greedy': FairGreedyPolicy(pay_per_order=cfg.pay_per_order,
                                            equity_bonus=0.3 * cfg.pay_per_order, cfg=cfg),
        }

    results_all = {}
    for name, pol in policies.items():
        _, m = run_simulation(cfg, instance, pol, name, verbose=verbose)
        results_all[name] = m

    if verbose:
        names = list(policies.keys())
        print(f"\n{'='*66}\n  POLICY COMPARISON\n{'-'*66}")
        header = f"  {'Metric':<28}" + ''.join(f"  {n:>14}" for n in names)
        print(header)
        print('-' * 66)
        for k in ['coverage_rate', 'c2d_mean', 'throughput_cost', 'total_payment',
                 'proportion_trueup', 'F_Gini', 'F_MaxMin', 'F_Deficit', 'F_Dist']:
            row = f"  {k:<28}"
            for n in names:
                row += f"  {str(results_all[n].get(k, '-')):>14}"
            print(row)
        print('=' * 66)

    return results_all


# -- Output helpers ------------------------------------------------------------------

def save_results(results: dict, metrics: dict, cfg: Config,
                 label: str = 'run', out_dir: str = 'output'):
    os.makedirs(out_dir, exist_ok=True)

    def _save(df, suffix):
        if df.empty:
            return
        path = os.path.join(out_dir, f'{label}_{suffix}.csv')
        df.to_csv(path, index=False)
        print(f'  Saved: {path}  ({len(df):,} rows)')

    _save(pd.DataFrame(courier_table(results['couriers'], cfg)), 'couriers')

    log = results.get('delivery_log', [])
    if log:
        _save(pd.DataFrame(delivery_detail_table(log)), 'deliveries')

    clog = results.get('cancellation_log', [])
    if clog:
        _save(pd.DataFrame(cancellation_table(clog)), 'cancellations')

    rlog = results.get('rejection_log', [])
    if rlog:
        _save(pd.DataFrame(rejection_table(rlog)), 'rejections')

    snaps = results.get('state_snapshots', [])
    if snaps:
        _save(pd.DataFrame(snapshot_table(snaps)), 'snapshots')

    path_m = os.path.join(out_dir, f'{label}_metrics.csv')
    pd.DataFrame([metrics]).to_csv(path_m, index=False)
    print(f'  Saved: {path_m}')


# -- CLI ------------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='mdrplib-adapted MDRP Simulator')

    parser.add_argument('--instance', type=str, default=None, metavar='NAME',
                        help='mdrplib instance name, e.g. 0o100t100s1p100')
    parser.add_argument('--instances-dir', type=str, default=DEFAULT_INSTANCES_DIR)
    parser.add_argument('--list', action='store_true', help='List available mdrplib instances')

    parser.add_argument('--from', dest='sim_from', type=str, default='00:00', metavar='HH:MM')
    parser.add_argument('--until', dest='sim_until', type=str, default='24:00', metavar='HH:MM')

    parser.add_argument('--policy', type=str, default='greedy',
                        choices=['greedy', 'fair_greedy', 'ilp', 'mdrpsim_greedy',
                                'mdrpsim_mip', 'mdrpsim_graph', 'mdrpsim_graph_prospects'])
    parser.add_argument('--ilp', action='store_true', help='Shortcut for --policy ilp')
    parser.add_argument('--objective', type=str, default='max_coverage',
                        choices=['max_coverage', 'max_throughput', 'min_lateness',
                                'max_equity', 'min_cost'],
                        help='ILP tie-break rule among coverage-maximal solutions -- '
                             'all 5 share coverage as the true objective (see '
                             'ilp_policy.py)')
    parser.add_argument('--solver', type=str, default='CBC', choices=['CBC', 'GUROBI', 'CPLEX'])
    parser.add_argument('--bundle', type=int, default=3, metavar='N',
                        help='Max same-restaurant orders per route, transversal to every '
                             'policy (default: 3; 1 disables bundling)')
    parser.add_argument('--late-tolerance', type=float, default=0.0, metavar='MIN',
                        help='Grace (minutes) beyond the instance maximum click-to-door')

    parser.add_argument('--cancellation', action='store_true',
                        help='Enable the 2-threshold cancellation hazard (off by default)')

    parser.add_argument('--acceptance-mode', type=str, default='auto',
                        choices=['auto', 'fixed', 'logistic'],
                        help="Courier acceptance criterion, transversal to --policy "
                             "(default: auto -- always accepts)")
    parser.add_argument('--acceptance-range', type=float, nargs=2, default=[1.0, 1.0],
                        metavar=('MIN', 'MAX'),
                        help='Used when --acceptance-mode fixed: range to draw each '
                             "courier's own acceptance rate from (set MIN=MAX for a "
                             'single global probability)')
    parser.add_argument('--min-wage', type=float, default=None,
                        help='External statutory wage threshold for F_Deficit '
                             '(default: the instance guaranteed_pay_per_hour)')

    parser.add_argument('--compare', action='store_true', help='Compare greedy vs fair-greedy')
    parser.add_argument('--reposition', action='store_true', help='Enable idle-courier repositioning')

    parser.add_argument('--save', action='store_true')
    parser.add_argument('--out-dir', type=str, default='output')
    parser.add_argument('--seed', type=int, default=42)

    args = parser.parse_args()

    if args.list:
        names = list_instances(args.instances_dir)
        print(f"mdrplib instances ({len(names)}) in {args.instances_dir}:")
        for n in names:
            print(f"  {n}")
        raise SystemExit(0)

    if not args.instance:
        parser.error("Specify --instance NAME (use --list to see available names).")

    from_min = _hm_to_min(args.sim_from)
    until_min = _hm_to_min(args.sim_until) if args.sim_until != '24:00' else 1_440.0
    if until_min <= from_min:
        parser.error("--until must be later than --from")

    cfg = Config(
        seed=args.seed,
        sim_start_clock_min=from_min,
        sim_end=until_min - from_min,
        objective=args.objective,
        ilp_solver=args.solver,
        max_bundle_size=args.bundle,
        late_tolerance_min=args.late_tolerance,
        enable_cancellation=args.cancellation,
        enable_repositioning=args.reposition,
        acceptance_mode=args.acceptance_mode,
        min_acceptance_rate=args.acceptance_range[0],
        max_acceptance_rate=args.acceptance_range[1],
        min_wage_hourly=args.min_wage,
    )

    instance = load_instance(args.instance, args.instances_dir, cfg)

    policy_name = 'ilp' if args.ilp else args.policy
    policy = build_policy(policy_name, cfg)

    if args.compare:
        compare_policies(cfg, instance)
    else:
        results, metrics = run_simulation(cfg, instance, policy, policy_name)
        if args.save:
            save_results(results, metrics, cfg,
                         label=f"{policy_name}_{args.instance}", out_dir=args.out_dir)
