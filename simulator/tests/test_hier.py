"""
Tests for the hierarchical Gurobi model (hier/). Pyramid (épica §8.3):
  unit        no Gurobi: objective catalogue, settings, flags
  integration configure() only: candidates, families, fingerprint
  e2e         one toy round with Gurobi vs exhaustive lexicographic enumeration

Run:  python -m pytest tests/test_hier.py -q
"""
import itertools
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hier.objectives import (CATALOGUE, DEFAULT_ORDER, ObjectiveSetting, resolve_order,  # noqa: E402
                             resolve_settings)
from hier.flags import flag  # noqa: E402

TOY = os.path.join(ROOT, 'tests', 'fixtures', 'hier', 'toy.json')
gp = pytest.importorskip('gurobipy')


# -- unit (no Gurobi) ---------------------------------------------------------------------------------

def test_default_order_and_priorities():
    specs = resolve_order(None)
    assert [s.name for s in specs] == DEFAULT_ORDER
    assert [s.priority for s in specs] == sorted([s.priority for s in specs], reverse=True)
    assert specs[0].name == 'coverage'


def test_reorder_is_honoured_literally():
    specs = resolve_order(['coverage', 'equity', 'lateness', 'cost'])
    assert [s.name for s in specs] == ['coverage', 'equity', 'lateness', 'cost']
    assert specs[1].priority > specs[2].priority


def test_no_protected_objectives_and_lock_defaults():
    # decision 5C: every pass accepts mip_gap; decision 4C: coverage lock exact, others 1e-4
    specs = resolve_order(None)
    assert not any(s.protected for s in specs)
    st = resolve_settings(specs, {'coverage': ObjectiveSetting(mip_gap=0.05),
                                  'lateness': ObjectiveSetting(mip_gap=0.05, time_limit=3)})
    assert st['coverage'].mip_gap == 0.05
    assert st['lateness'].mip_gap == 0.05 and st['lateness'].time_limit == 3
    assert st['coverage'].lock_rel_tol == 0.0
    assert all(st[n].lock_rel_tol == 1e-4 for n in ('lateness', 'equity', 'cost'))


def test_protected_flag_still_enforced_when_set():
    from hier.objectives import ObjectiveSpec
    base = resolve_order(None)[0]
    prot = ObjectiveSpec(name=base.name, priority=base.priority, label=base.label, sense=base.sense,
                         protected=True, description=base.description, coef=base.coef, exists=base.exists)
    with pytest.raises(ValueError):
        resolve_settings([prot], {'coverage': ObjectiveSetting(mip_gap=0.05)})


def test_quality_contract():
    st = ObjectiveSetting.from_quality(quality=95, time_limit_min=0.5)
    assert abs(st.mip_gap - 0.05) < 1e-12 and st.time_limit == 30.0


def test_flag_truthiness_trap(monkeypatch):
    monkeypatch.setenv('DISABLE_HIER_COST', '0')
    assert flag('DISABLE_HIER_COST') is False
    monkeypatch.setenv('DISABLE_HIER_COST', '1')
    assert flag('DISABLE_HIER_COST') is True
    assert [s.name for s in resolve_order(None)] == ['coverage', 'lateness', 'equity']


# -- integration (configure only) ------------------------------------------------------------------------

def _load_toy():
    from hier.context import HierContext, round_from_json
    with open(TOY, encoding='utf8') as f:
        doc = json.load(f)
    couriers, orders, cfg, t, extra = round_from_json(doc)
    env = gp.Env(params={'OutputFlag': 0})
    return HierContext(couriers, orders, cfg, t, top_k=extra['top_k'], env=env, log=lambda m: None)


def test_configure_families_and_fingerprint():
    ctx = _load_toy().configure()
    assert ctx.rows_by_family == {'Cover': 4, 'Impossible': 0, 'CourierOnce': 3, 'PrevSolution': 0}
    assert len(ctx.candidates) == 18 and ctx.discards == {}
    fp1 = ctx.fingerprint()
    ctx2 = _load_toy().configure()
    assert fp1 == ctx2.fingerprint(), 'same input must give the same model fingerprint'
    ctx.dispose(); ctx2.dispose()


def test_prev_solution_is_fixed():
    from hier.context import HierContext
    base = _load_toy()
    ctx = HierContext(base.couriers, base.orders, base.cfg, base.t, top_k=3, env=base._env,
                      prev_solution=[(2, [3, 4])], log=lambda m: None).configure().optimize()
    assert any(cid == 2 and sorted(oids) == [3, 4] for cid, oids, _ in ctx.solution)
    assert ctx.rows_by_family['PrevSolution'] == 1
    ctx.dispose()


# -- e2e: Gurobi vs exhaustive enumeration -------------------------------------------------------------------

def _brute(ctx):
    cands = ctx.candidates
    cids = sorted({k[0] for k in cands})
    opts = {c: [None] + [k for k in cands if k[0] == c] for c in cids}
    best, best_vec = None, None
    for combo in itertools.product(*[opts[c] for c in cids]):
        chosen = [k for k in combo if k is not None]
        seen, ok = set(), True
        for _, rkey in chosen:
            for oid in rkey:
                ok = ok and oid not in seen
                seen.add(oid)
        if not ok:
            continue
        vec = tuple(round(len(seen) if s.name == 'coverage' else sum(s.coef(cands[k]) for k in chosen), 6)
                    for s in ctx.specs)
        if best_vec is None or vec > best_vec:
            best, best_vec = chosen, vec
    return best_vec


def _vector(ctx):
    cands = ctx.candidates
    return tuple(round(ctx.indicators()['orders_covered'] if s.name == 'coverage'
                       else sum(s.coef(cands[(cid, tuple(sorted(oids)))]) for cid, oids, _ in ctx.solution), 6)
                 for s in ctx.specs)


@pytest.mark.parametrize('order', [None, ['coverage', 'equity', 'lateness', 'cost'],
                                   ['coverage', 'cost', 'lateness', 'equity']])
def test_toy_matches_brute_force(order):
    from hier.context import HierContext
    base = _load_toy()
    ctx = HierContext(base.couriers, base.orders, base.cfg, base.t, top_k=3, env=base._env,
                      order=order, log=lambda m: None).configure().optimize()
    assert ctx.inner_status == 'OPTIMAL'
    assert [p['end_reason'] for p in ctx.pass_table()] == ['optimal'] * len(ctx.specs)
    assert _vector(ctx) == _brute(ctx)
    ctx.dispose()


def test_toy_default_hierarchy_values():
    """Baseline KPI (épica §8.3): the documented toy outcome used by the deck."""
    ctx = _load_toy().configure().optimize()
    ind = ctx.indicators()
    assert ind['orders_covered'] == 4 and ind['lateness_min'] == 8.0 and ind['courier_minutes'] == 44.0
    assert sorted((cid, sorted(oids)) for cid, oids, _ in ctx.solution) == [(1, [1, 2]), (2, [4]), (3, [3])]
    ctx.dispose()


def test_skip_pass_keeps_previous_locks():
    ctx = _load_toy().configure().optimize(skip=['lateness'])
    table = {p['name']: p for p in ctx.pass_table()}
    assert table['coverage']['end_reason'] == 'optimal'
    assert table['lateness']['skip_state'] in ('requested', 'applied')
    assert ctx.indicators()['orders_covered'] == 4
    ctx.dispose()
