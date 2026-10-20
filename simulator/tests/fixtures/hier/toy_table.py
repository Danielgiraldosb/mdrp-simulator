"""Print the toy round's candidate table and the lexicographic optimum under several pass orders
and under a weighted sum (the 'why not weights' demonstration of the deck)."""
import itertools, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
from hier.context import HierContext, round_from_json
from hier.objectives import CATALOGUE
import gurobipy as gp

doc = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'toy.json')))
couriers, orders, cfg, t, extra = round_from_json(doc)
env = gp.Env(params={'OutputFlag': 0})
ctx = HierContext(couriers, orders, cfg, t, top_k=extra['top_k'], env=env, log=lambda m: None)
ctx.configure()
cands = ctx.candidates
print("CANDIDATES (courier, route): n, lateness, total_tt, deficit, sequence")
for k, c in sorted(cands.items()):
    print(f"  {k}: n={c['n_orders']} late={c['lateness']:.1f} tt={c['total_tt']:.1f} def={c['deficit']:.3f} seq={c['sequence']}")

couriers_ids = sorted({k[0] for k in cands})
opts = {c: [None] + [k for k in cands if k[0] == c] for c in couriers_ids}
feas = []
for combo in itertools.product(*[opts[c] for c in couriers_ids]):
    chosen = [k for k in combo if k is not None]
    seen = set(); ok = True
    for _, rkey in chosen:
        for oid in rkey:
            if oid in seen: ok = False
            seen.add(oid)
    if ok:
        feas.append((chosen, len(seen),
                     sum(cands[k]['lateness'] for k in chosen),
                     sum(cands[k]['deficit'] * cands[k]['n_orders'] for k in chosen),
                     sum(cands[k]['total_tt'] for k in chosen)))
print("feasible assignments:", len(feas))
def vec(sol, order):
    m = {'coverage': sol[1], 'lateness': -sol[2], 'equity': sol[3], 'cost': -sol[4]}
    return tuple(round(m[o], 6) for o in order)
for order in [['coverage','lateness','equity','cost'], ['coverage','equity','lateness','cost'],
              ['coverage','cost','lateness','equity'], ['coverage','lateness','cost','equity']]:
    best = max(feas, key=lambda s: vec(s, order))
    print(f"ORDER {order}: cov={best[1]} late={best[2]:.1f} eq={best[3]:.3f} tt={best[4]:.1f}  -> {best[0]}")
print("coverage-max solutions:", sum(1 for s in feas if s[1] == 4))
# weighted sum: maximize cov*W - lam*late - mu*tt + eq*nu  with coverage-max fixed, scan lam (lateness weight) vs tt weight 1
print("WEIGHTED (among coverage=4): max -(lam*late) - tt + eq ; scanning lam")
for lam in [0, 0.5, 1, 2, 3, 5, 10]:
    best = max([s for s in feas if s[1]==4], key=lambda s: -lam*s[2] - s[4] + s[3])
    print(f"  lam={lam}: late={best[2]:.1f} eq={best[3]:.3f} tt={best[4]:.1f} -> {best[0]}")
