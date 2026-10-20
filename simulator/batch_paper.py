"""
batch_paper.py -- Etapa 4 grid for the CMDP-with-equity paper (docs/paper-cmdp/diseno-experimental.md).

Experiments
  pilot      6 instances (one per city) x 7 methods at defaults x manual x seed 1     (42 runs)
  main       18 method configurations x 2 regimes x 24 instances x 10 seeds           (8,640 runs)
  threshold  5 selected configurations x logit threshold {615, 1242} x 2 regimes
             x 24 instances x 5 seeds                                                 (2,400 runs)
  supp       4 ablations x manual x 24 instances x 5 seeds                            (480 runs)

Every run executes in its OWN Python subprocess with retries and a timeout
(as batch_hier_clusters.py: gurobipy showed sporadic access violations when one
process runs many days back to back). Resume-safe: run_ids already in --out
are skipped. Each run appends one row (metrics + cell columns) to --out and
writes the per-courier table to <out dir>/couriers/<run_id>.csv.

  python batch_paper.py --experiment pilot --workers 6 --out output/paper/pilot.csv
  python batch_paper.py --estimate output/paper/pilot.csv
  python batch_paper.py --experiment main --workers 16 --out output/paper/main.csv
  python batch_paper.py --experiment main --dry-run            # list cells, run nothing
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List, Optional

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INSTANCES_DIR = os.path.normpath(os.path.join(THIS_DIR, '..', 'real_instancies'))
INSTANCE_TABLE = os.path.normpath(os.path.join(THIS_DIR, '..', 'docs', 'paper-cmdp', 'instancias_reales.csv'))

# Decision D6 (2026-10-20): kg CO2e per km by vehicle, DEFRA/BEIS 2023 "average motorbike"
# and "average car"; applied post hoc to the per-courier dist_km (diseno-experimental.md section 5).
EMISSION_KG_PER_KM = {'motorcycle': 0.114, 'car': 0.167, 'bicycle': 0.0, 'walking': 0.0}
EMISSION_KG_PER_KM_SMALL_MOTO = 0.083  # DEFRA 2024 "small motorbike", sensitivity

PPK_THRESHOLD_POINT = 903.0          # COP/km, logit fit (n = 32 decisions)
PPK_THRESHOLD_CI = (615.0, 1242.0)   # 95 % CI of the fit
PILOT_INSTANCES = ['Instancia_0', 'Instancia_1', 'Instancia_2', 'Instancia_4', 'Instancia_5', 'Instancia_7']

# ---------------------------------------------------------------- method configurations
# key -> (policy name for run.build_policy, Config overrides, sweep parameter columns)
METHODS: Dict[str, Dict[str, Any]] = {
    'greedy': dict(policy='greedy', cfg={}),
    'ilp':    dict(policy='ilp', cfg={'objective': 'max_coverage'}),
    'hier':   dict(policy='hier', cfg={}),
    'brkga':  dict(policy='brkga', cfg={'brkga_score': 'finish_per_order'}),
}
for _w in (5, 10, 20, 40):
    METHODS[f'brkga_fair_w{_w}'] = dict(policy='brkga_fair',
                                        cfg={'brkga_fair_weight': float(_w), 'brkga_fair_basis': 'hourly'},
                                        weight=float(_w))
for _a in (0.20, 0.25, 0.30, 0.35, 0.40, 1.00):
    METHODS[f'mipfair_a{int(round(_a * 100)):03d}'] = dict(
        policy='mip_fair',
        cfg={'mipfair_alpha': _a, 'mipfair_priority': 'coverage', 'mipfair_scope': 'all',
             'mipfair_basis': 'hourly', 'mipfair_cand_top_k': 8},   # top-k 8: pilot H3
        alpha=_a)
for _l in (0.1, 0.2, 0.5, 1.0):
    METHODS[f'paybrkga_l{int(round(_l * 10)):02d}'] = dict(
        policy='pay_brkga',
        cfg={'paybrkga_lambda_pay': _l, 'paybrkga_lambda_deficit': 0.5, 'paybrkga_pay_range': 0.30},
        lambda_pay=_l)

# supplement ablations (manual regime only)
ABLATIONS: Dict[str, Dict[str, Any]] = {
    'brkga_finish':        dict(policy='brkga', cfg={'brkga_score': 'finish'}),
    'mipfair_a030_idle':   dict(policy='mip_fair', cfg={'mipfair_alpha': 0.30, 'mipfair_scope': 'idle',
                                                        'mipfair_priority': 'coverage'}, alpha=0.30),
    # fairness-first lexicographic order (decision E5 as originally taken): the Etapa 4 pilot showed it
    # assigns nothing from a cold start (everyone at 0 earnings -> any assignment raises the Gini)
    'mipfair_a030_fairfirst': dict(policy='mip_fair', cfg={'mipfair_alpha': 0.30, 'mipfair_scope': 'all',
                                                           'mipfair_priority': 'fairness'}, alpha=0.30),
    'mipfair_a030_total':  dict(policy='mip_fair', cfg={'mipfair_alpha': 0.30, 'mipfair_scope': 'all',
                                                        'mipfair_basis': 'total'}, alpha=0.30),
    'brkga_fair_w10_total': dict(policy='brkga_fair', cfg={'brkga_fair_weight': 10.0,
                                                           'brkga_fair_basis': 'total'}, weight=10.0),
    # scaling knobs probed in the Etapa 4 pilot on the Bogota zone
    'mipfair_a030_k25':    dict(policy='mip_fair', cfg={'mipfair_alpha': 0.30, 'mipfair_scope': 'all',
                                                        'mipfair_priority': 'coverage',
                                                        'mipfair_cand_top_k': 25}, alpha=0.30),
    'brkga_p20g20':        dict(policy='brkga', cfg={'brkga_score': 'finish_per_order',
                                                     'brkga_population': 20, 'brkga_generations': 20}),
}

PILOT_METHODS = ['greedy', 'ilp', 'hier', 'brkga', 'brkga_fair_w10', 'mipfair_a030', 'paybrkga_l02']
THRESHOLD_METHODS = ['greedy', 'hier', 'brkga_fair_w10', 'paybrkga_l02']   # + mipfair at the knee


# ---------------------------------------------------------------- instances
def read_instance_table() -> Dict[str, str]:
    """instance name -> city, from docs/paper-cmdp/instancias_reales.csv (fallback: 'unknown')."""
    cities: Dict[str, str] = {}
    if os.path.exists(INSTANCE_TABLE):
        with open(INSTANCE_TABLE, newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                cities[f"Instancia_{row['inst']}"] = row['city']
    return cities


def all_instances(instances_dir: str) -> List[str]:
    from loader_real import list_real_instances
    return list_real_instances(instances_dir)


# ---------------------------------------------------------------- grid
def _cell(experiment: str, instance: str, city: str, method: str, spec: Dict[str, Any],
          regime: str, seed: int, ppk_threshold: float, radius: float) -> Dict[str, Any]:
    key = f"{experiment}|{instance}|{method}|{regime}|{ppk_threshold:g}|{radius:g}|{seed}"
    return dict(
        run_id=hashlib.md5(key.encode()).hexdigest()[:12],
        experiment=experiment, instance=instance, city=city, method=method,
        policy=spec['policy'], regime=regime,
        alpha=spec.get('alpha', ''), weight=spec.get('weight', ''), lambda_pay=spec.get('lambda_pay', ''),
        ppk_threshold=ppk_threshold, radius_km=radius, seed=seed,
        cfg=dict(spec['cfg']),
    )


def build_grid(experiment: str, instances: List[str], cities: Dict[str, str], radius: float,
               seeds: Optional[int] = None, methods: Optional[List[str]] = None,
               mipfair_knee: Optional[float] = None) -> List[Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []

    def add(insts: Iterable[str], mkeys: Iterable[str], regimes: Iterable[str], seed_list: Iterable[int],
            thresholds: Iterable[float], catalogue: Dict[str, Dict[str, Any]] = METHODS):
        for inst in insts:
            for mk in mkeys:
                for reg in regimes:
                    for thr in thresholds:
                        for s in seed_list:
                            cells.append(_cell(experiment, inst, cities.get(inst, 'unknown'), mk,
                                               catalogue[mk], reg, s, thr, radius))

    if experiment == 'pilot':
        insts = [i for i in PILOT_INSTANCES if i in instances] or instances[:6]
        add(insts, methods or PILOT_METHODS, ['manual'], [1], [PPK_THRESHOLD_POINT])
    elif experiment == 'main':
        add(instances, methods or list(METHODS), ['manual', 'autoaccept'],
            range(1, (seeds or 10) + 1), [PPK_THRESHOLD_POINT])
    elif experiment == 'threshold':
        mkeys = list(methods or THRESHOLD_METHODS)
        if not methods:
            if mipfair_knee is None:
                raise SystemExit('--mipfair-knee ALPHA is required for --experiment threshold '
                                 '(the knee alpha found in the main experiment)')
            knee = f'mipfair_a{int(round(mipfair_knee * 100)):03d}'
            if knee not in METHODS:
                raise SystemExit(f'{knee} is not one of the main-grid alphas: '
                                 f'{[k for k in METHODS if k.startswith("mipfair")]}')
            mkeys.append(knee)
        add(instances, mkeys, ['manual', 'autoaccept'], range(1, (seeds or 5) + 1), list(PPK_THRESHOLD_CI))
    elif experiment == 'supp':
        add(instances, methods or list(ABLATIONS), ['manual'], range(1, (seeds or 5) + 1),
            [PPK_THRESHOLD_POINT], catalogue=ABLATIONS)
    else:
        raise SystemExit(f'unknown experiment {experiment}')
    return cells


# ---------------------------------------------------------------- one run (child process)
def run_cell(cell: Dict[str, Any], instances_dir: str, couriers_dir: Optional[str],
             solver: str = 'GUROBI', ilp_time_limit: Optional[float] = 10.0,
             circuity: float = 1.0, speeds: Optional[Dict[str, float]] = None,
             sim_from_min: float = 0.0, sim_until_min: float = 1440.0) -> Dict[str, Any]:
    """Run one cell end to end and return its metrics row. Called inside the child process."""
    import pandas as pd
    from config import Config
    from loader_real import load_real_instance
    from metrics import courier_table
    from run import build_policy, run_simulation

    cfg_kwargs: Dict[str, Any] = dict(
        seed=int(cell['seed']),
        sim_start_clock_min=sim_from_min, sim_end=sim_until_min - sim_from_min,
        acceptance_mode='logit_ppk', accept_regime=cell['regime'],
        accept_ppk_threshold=float(cell['ppk_threshold']),
        real_max_radius_km=float(cell['radius_km']), real_circuity=circuity,
        ilp_solver=solver, ilp_time_limit_sec=ilp_time_limit,
        max_bundle_size=3,
    )
    cfg_kwargs.update(cell['cfg'])
    cfg = Config(**cfg_kwargs)
    if speeds:
        cfg.real_speeds_kmh.update(speeds)

    instance = load_real_instance(cell['instance'], instances_dir, cfg)
    policy = build_policy(cell['policy'], cfg)
    results, m = run_simulation(cfg, instance, policy=policy, policy_name=cell['policy'], verbose=False)

    meta = instance.get('meta', {}) or {}
    row = {k: v for k, v in cell.items() if k != 'cfg'}
    row.update(m)
    row['n_couriers_loaded'] = len(instance['couriers'])
    row['city_detected'] = meta.get('city', '')
    row['cfg_json'] = json.dumps(cell['cfg'], sort_keys=True)
    if couriers_dir:
        os.makedirs(couriers_dir, exist_ok=True)
        pd.DataFrame(courier_table(results['couriers'], cfg)).to_csv(
            os.path.join(couriers_dir, f"{cell['run_id']}.csv"), index=False)
    return row


CHILD = (
    "import json, sys; sys.path.insert(0, %r); "
    "from batch_paper import run_cell; "
    "a = json.loads(sys.argv[1]); "
    "r = run_cell(a['cell'], a['instances_dir'], a['couriers_dir'], a['solver'], a['ilp_time_limit'], "
    "a['circuity'], a['speeds'], a['sim_from'], a['sim_until']); "
    "print('ROW' + json.dumps(r, default=str))"
)


def run_in_subprocess(cell: Dict[str, Any], opts: Dict[str, Any], python: str,
                      retries: int, timeout_min: float) -> Dict[str, Any]:
    payload = json.dumps(dict(cell=cell, **opts))
    last_err = ''
    for attempt in range(1, retries + 2):
        t0 = time.perf_counter()
        try:
            proc = subprocess.run([python, '-c', CHILD % THIS_DIR, payload], capture_output=True,
                                  text=True, timeout=timeout_min * 60.0, cwd=THIS_DIR)
        except subprocess.TimeoutExpired:
            last_err = f'timeout after {timeout_min} min'
            continue
        for line in proc.stdout.splitlines():
            if line.startswith('ROW'):
                row = json.loads(line[3:])
                row['attempts'] = attempt
                row['child_wall_sec'] = round(time.perf_counter() - t0, 1)
                return row
        last_err = (proc.stderr or proc.stdout or '').strip()[-800:] or f'exit {proc.returncode}'
    return dict(run_id=cell['run_id'], failed=True, error=last_err, cell=cell)


# ---------------------------------------------------------------- output helpers
def done_run_ids(out: str) -> set:
    if not os.path.exists(out):
        return set()
    with open(out, newline='', encoding='utf-8') as fh:
        return {row['run_id'] for row in csv.DictReader(fh) if row.get('run_id')}


class RowWriter:
    """Append rows to a CSV, writing the header once (union of keys seen on the first row)."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.fields: Optional[List[str]] = None
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, newline='', encoding='utf-8') as fh:
                self.fields = next(csv.reader(fh))

    def write(self, row: Dict[str, Any]) -> None:
        new = self.fields is None
        if new:
            self.fields = list(row.keys())
        with open(self.path, 'a', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=self.fields, extrasaction='ignore')
            if new:
                w.writeheader()
            w.writerow({k: row.get(k, '') for k in self.fields})


# ---------------------------------------------------------------- estimate
def instance_sizes(instances: List[str], instances_dir: str, radius: float) -> Dict[str, int]:
    """Orders inside the zone per instance (loads each instance once; a few seconds each)."""
    from config import Config
    from loader_real import load_real_instance
    sizes = {}
    for inst in instances:
        cfg = Config(real_max_radius_km=radius, acceptance_mode='logit_ppk')
        sizes[inst] = len(load_real_instance(inst, instances_dir, cfg)['orders'])
    return sizes


def estimate(pilot_csv: str, instances_dir: str, radius: float, seeds: int, workers: List[int]) -> None:
    import pandas as pd
    df = pd.read_csv(pilot_csv)
    df = df[df.get('failed', pd.Series(False, index=df.index)).fillna(False).astype(str) != 'True'] \
        if 'failed' in df.columns else df
    df['sec_per_order'] = df['wall_clock_sec'] / df['n_orders'].clip(lower=1)
    per_method = df.groupby('policy')['sec_per_order'].median()
    print('\nPilot: median wall-clock seconds per order, by policy')
    print(per_method.round(4).to_string())
    corp = df[(df['method'] == 'greedy')]
    if len(corp):
        g = corp['F_Gini'].mean()
        print(f"\nCorporate (greedy, manual) mean end-of-day F_Gini = {g:.3f}  "
              f"-> alpha grid {'stays' if 0.35 <= g <= 0.55 else 'MUST be recentred (see diseno-experimental.md §2)'}")
    big = df.sort_values('n_orders').iloc[-1]
    worst = df[df['instance'] == big['instance']]['wall_clock_sec'].max() / 60.0
    print(f"Largest pilot instance {big['instance']} ({int(big['n_orders'])} orders): slowest method "
          f"{worst:.1f} min -> radius {'stays at %g km' % radius if worst <= 20 else 'drops to 2 km for all cities'}")

    cities = read_instance_table()
    insts = all_instances(instances_dir)
    sizes = instance_sizes(insts, instances_dir, radius)
    grid = build_grid('main', insts, cities, radius, seeds=seeds)
    total = 0.0
    missing = set()
    for c in grid:
        spo = per_method.get(c['policy'])
        if spo is None:
            missing.add(c['policy'])
            continue
        total += spo * sizes[c['instance']]
    print(f"\nMain grid: {len(grid)} runs, mean zone size {sum(sizes.values()) / len(sizes):.0f} orders")
    if missing:
        print(f"  (no pilot timing for policies {sorted(missing)}; their runs are not counted)")
    print(f"  CPU total  : {total / 3600:.1f} h")
    for w in workers:
        print(f"  {w:>3} workers: {total / 3600 / w:.1f} h  ({total / 3600 / w / 24:.2f} days)")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--experiment', choices=['pilot', 'main', 'threshold', 'supp'], default='pilot')
    ap.add_argument('--instances-dir', default=DEFAULT_INSTANCES_DIR)
    ap.add_argument('--instances', nargs='+', default=None, help='subset of instance names')
    ap.add_argument('--methods', nargs='+', default=None, help='subset of method keys')
    ap.add_argument('--seeds', type=int, default=None, help='seeds per cell (default: 10 main, 5 others)')
    ap.add_argument('--radius', type=float, default=3.0, help='zone radius in km (default 3)')
    ap.add_argument('--mipfair-knee', type=float, default=None, help='alpha at the knee (threshold exp.)')
    ap.add_argument('--solver', default='GUROBI', choices=['GUROBI', 'CBC', 'CPLEX'])
    ap.add_argument('--ilp-time-limit', type=float, default=10.0, help='seconds per round for the MIPs')
    ap.add_argument('--circuity', type=float, default=1.3)   # D2
    ap.add_argument('--speeds', nargs='+', default=None, metavar='VEH=KMH')
    ap.add_argument('--from', dest='sim_from', default='00:00')
    ap.add_argument('--until', dest='sim_until', default='24:00')
    ap.add_argument('--out', default=None, help='CSV (default output/paper/<experiment>.csv)')
    ap.add_argument('--no-couriers', action='store_true', help='do not save per-courier tables')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--retries', type=int, default=2)
    ap.add_argument('--timeout-min', type=float, default=60.0)
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--estimate', metavar='PILOT_CSV', default=None,
                    help='extrapolate the main grid cost from a pilot CSV and exit')
    args = ap.parse_args()

    if args.estimate:
        estimate(args.estimate, args.instances_dir, args.radius, args.seeds or 10, [8, 16, 32])
        return

    cities = read_instance_table()
    instances = args.instances or all_instances(args.instances_dir)
    grid = build_grid(args.experiment, instances, cities, args.radius, args.seeds, args.methods,
                      args.mipfair_knee)
    out = args.out or os.path.join(THIS_DIR, 'output', 'paper', f'{args.experiment}.csv')
    done = done_run_ids(out)
    todo = [c for c in grid if c['run_id'] not in done]
    print(f"{args.experiment}: {len(grid)} cells, {len(done)} already in {out}, {len(todo)} to run")
    if args.dry_run:
        by = {}
        for c in grid:
            by[c['method']] = by.get(c['method'], 0) + 1
        for k, v in by.items():
            print(f"  {k:<22} {v:>6}")
        for c in todo[:5]:
            print('  e.g.', {k: v for k, v in c.items() if k not in ('cfg',)})
        return
    if not todo:
        return

    from loader_real import hms_to_min, parse_speeds
    opts = dict(instances_dir=args.instances_dir,
                couriers_dir=None if args.no_couriers else os.path.join(os.path.dirname(os.path.abspath(out)), 'couriers'),
                solver=args.solver, ilp_time_limit=args.ilp_time_limit, circuity=args.circuity,
                speeds=parse_speeds(args.speeds) if args.speeds else None,
                sim_from=hms_to_min(args.sim_from), sim_until=hms_to_min(args.sim_until))
    writer = RowWriter(out)
    failed_path = out + '.failed.jsonl'
    t_start = time.perf_counter()
    n_ok = n_fail = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_in_subprocess, c, opts, args.python, args.retries, args.timeout_min): c
                for c in todo}
        for fut in as_completed(futs):
            row = fut.result()
            if row.get('failed'):
                n_fail += 1
                with open(failed_path, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(row, default=str) + '\n')
                c = row['cell']
                print(f"  FAIL {c['instance']} {c['method']} {c['regime']} s{c['seed']}: {row['error'][:160]}")
            else:
                n_ok += 1
                writer.write(row)
                print(f"  ok {row['instance']:<12} {row['method']:<20} {row['regime']:<10} s{row['seed']:<3} "
                      f"cov={row.get('coverage_rate', float('nan')):.3f} gini={row.get('F_Gini', float('nan')):.3f} "
                      f"{row.get('wall_clock_sec', 0):.0f}s")
            done_n = n_ok + n_fail
            if done_n % 25 == 0 or done_n == len(todo):
                el = time.perf_counter() - t_start
                print(f"-- {done_n}/{len(todo)} done, {n_fail} failed, {el / 60:.1f} min elapsed, "
                      f"~{el / done_n * (len(todo) - done_n) / 60:.1f} min left")
    print(f"finished: {n_ok} ok, {n_fail} failed -> {out}")


if __name__ == '__main__':
    main()
