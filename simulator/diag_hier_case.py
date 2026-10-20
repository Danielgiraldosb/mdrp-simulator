"""
diag_hier_case.py -- run ONE dispatch round of the hierarchical model offline
(épica §8.2: the 30-line pattern -> load input -> configure -> inspect ->
optimize), print the pass table and write the artifacts of §6.

  python diag_hier_case.py --toy                            # didactic 3x4 case (tests/fixtures/hier/toy.json)
  python diag_hier_case.py --input output/hier/<id>/<id>_input.json
  python diag_hier_case.py --instance 0o100t100s1p100 --time 720 --window 10
  python diag_hier_case.py --toy --order coverage equity lateness cost
  python diag_hier_case.py --toy --skip lateness --write-lp
  python diag_hier_case.py --toy --brute-force               # compare with exhaustive lexicographic enumeration

--instance builds a synthetic round at minute T: couriers whose shift covers
T, idle at home, and orders placed in [T-window, T].
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

from hier.context import HierContext, round_from_json, round_to_json
from hier.objectives import CATALOGUE, DEFAULT_ORDER, ObjectiveSetting

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOY = os.path.join(THIS_DIR, 'tests', 'fixtures', 'hier', 'toy.json')


def load_instance_round(name: str, t: float, window: float, instances_dir: str):
    from loader import load_instance
    from config import Config
    cfg = Config()
    inst = load_instance(name, instances_dir, cfg)
    cfg = inst['config']
    couriers = [c for c in inst['couriers'] if c.on_time <= t <= c.off_time]
    orders = [o for o in inst['orders'] if t - window <= o.placement_time <= t]
    for c in couriers:
        c.condition = 'idle'
        c.location = c.home_loc.copy()
    return couriers, orders, cfg


def brute_force(ctx: HierContext):
    """Exhaustive lexicographic optimum over all assignments (small cases only)."""
    couriers = sorted({k[0] for k in ctx.candidates})
    opts = {c: [None] + [k for k in ctx.candidates if k[0] == c] for c in couriers}
    best = None
    best_vec = None
    n = 0
    for combo in itertools.product(*[opts[c] for c in couriers]):
        chosen = [k for k in combo if k is not None]
        seen = set()
        ok = True
        for _, rkey in chosen:
            for oid in rkey:
                if oid in seen:
                    ok = False
                    break
                seen.add(oid)
            if not ok:
                break
        if not ok:
            continue
        n += 1
        vec = []
        for spec in ctx.specs:
            if spec.name == 'coverage':
                vec.append(len(seen))
            else:
                vec.append(sum(spec.coef(ctx.candidates[k]) for k in chosen))
        vec = tuple(round(v, 6) for v in vec)
        if best_vec is None or vec > best_vec:
            best_vec, best = vec, chosen
    return n, best_vec, best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--toy', action='store_true')
    ap.add_argument('--input', type=str, help='<id>_input.json produced by a previous run')
    ap.add_argument('--instance', type=str)
    ap.add_argument('--time', type=float, default=720.0)
    ap.add_argument('--window', type=float, default=10.0)
    ap.add_argument('--instances-dir', type=str, default=os.path.normpath(os.path.join(THIS_DIR, '..', 'public_instances')))
    ap.add_argument('--order', nargs='+', default=None, help=f'pass order, e.g. {" ".join(DEFAULT_ORDER)}')
    ap.add_argument('--skip', nargs='*', default=[], help='objectives to skip (action en caliente)')
    ap.add_argument('--time-limit', type=float, default=None, help='seconds per pass')
    ap.add_argument('--mip-gap', type=float, default=None, help='relative gap for every NON-protected pass')
    ap.add_argument('--lock-rel-tol', type=float, default=None, help='relative lock tolerance between passes')
    ap.add_argument('--top-k', type=int, default=None)
    ap.add_argument('--write-lp', action='store_true')
    ap.add_argument('--out-dir', type=str, default='output/hier')
    ap.add_argument('--brute-force', action='store_true')
    ap.add_argument('--json', action='store_true', help='print the sol json instead of the table')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args(argv)

    if args.toy or args.input:
        path = TOY if args.toy else args.input
        with open(path, encoding='utf8') as f:
            doc = json.load(f)
        couriers, orders, cfg, t, extra = round_from_json(doc)
        top_k = args.top_k or extra['top_k']
        order = args.order or extra.get('order') or None
    elif args.instance:
        couriers, orders, cfg = load_instance_round(args.instance, args.time, args.window, args.instances_dir)
        t = args.time
        top_k = args.top_k or 25
        order = args.order
    else:
        ap.error('one of --toy / --input / --instance')

    settings = {}
    for name in CATALOGUE:
        st = ObjectiveSetting(time_limit=args.time_limit, lock_rel_tol=args.lock_rel_tol)
        if args.mip_gap is not None and not CATALOGUE[name].protected:
            st.mip_gap = args.mip_gap
        settings[name] = st

    log = (lambda m: None) if args.quiet else (lambda m: print('  .', m))
    ctx = HierContext(couriers, orders, cfg, t, order=order, settings=settings, top_k=top_k,
                      write_model=args.write_lp, log=log,
                      on_partial=None if args.quiet else (lambda p: print('  partial', p['pct'], p['indicators'])))
    ctx.configure()
    ctx.optimize(skip=args.skip)

    paths = ctx.write_artifacts(args.out_dir)
    if args.json:
        print(json.dumps(ctx.solution_json(), indent=1, default=str))
        return 0

    d = ctx.details()
    print(f"\n== hier round {ctx.run_id}  t={t:.0f} min  status={d['status']}  solve={d['solve_s']:.3f}s "
          f"configure={d['configure_s'].get('total', 0):.3f}s")
    pf = d['prefilter']
    print(f"   couriers={len(ctx.couriers)} orders={len(ctx.orders)} routes={pf['routes']} candidates={pf['candidates']} "
          f"discards={pf['discards']} impossible={pf['impossible']}")
    print(f"   model: vars={d['model']['vars']} rows={d['model']['rows']} nz={d['model']['nonzeros']} "
          f"rows_by_family={d['rows_by_family']} fingerprint={d['model']['fingerprint'][:12]}")
    print(f"\n   {'pass':<4} {'objective':<10} {'prio':>4} {'sense':<5} {'value':>12} {'bound':>12} {'prog':>6} "
          f"{'end_reason':<12} {'sols':>4} {'nodes':>6} {'t_end':>7}")
    for p in d['passes']:
        val = p['value_display']
        sval = f"{val:.3f}" if val is not None else '-'
        sbnd = f"{p['bound']:.3f}" if p['bound'] is not None else '-'
        tend = p['end_s'] or 0.0
        print(f"   {p['pass_no']:<4} {p['name']:<10} {p['priority']:>4} {p['sense']:<5} {sval:>12} {sbnd:>12} "
              f"{p['progress']:>6.1f} {str(p['end_reason']):<12} {p['solutions']:>4} {p['nodes']:>6} {tend:>7.3f}")
    if d['objectives_absent']:
        print(f"   absent this round: {d['objectives_absent']}")
    print(f"\n   indicators: {d['indicators']}")
    print(f"   pct={d['pct']}  message_events={d['n_message_events']}")
    print("\n   solution:")
    for cid, oids, pay in ctx.solution:
        c = ctx.candidates[(cid, tuple(sorted(oids)))]
        print(f"     courier {cid:>4} -> orders {oids}  lateness={c['lateness']:.2f} tt={c['total_tt']:.2f} "
              f"deficit={c['deficit']:.3f} pay={pay:.2f}")
    if d['uncovered']:
        print(f"   uncovered: {d['uncovered']}")
    print(f"\n   artifacts: {paths}")

    if args.brute_force:
        n, vec, best = brute_force(ctx)
        got = tuple(round(v, 6) for v in [
            (ctx.indicators()['orders_covered'] if s.name == 'coverage'
             else sum(s.coef(ctx.candidates[(cid, tuple(sorted(oids)))]) for cid, oids, _ in ctx.solution))
            for s in ctx.specs])
        print(f"\n   brute force over {n} feasible assignments: lexicographic optimum {vec}")
        print(f"   gurobi vector: {got}   ->  {'MATCH' if vec == got else 'MISMATCH'}")
        return 0 if vec == got else 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
