"""
BRKGAPolicy (brkga_policy.py) -- the MIC 2026 BRKGA port.

  candidates   same 18 (courier, route) pairs HierContext builds on the toy round
  contract     each courier at most once, each order at most once, routes are
               feasible candidates, pay = pay_per_order x orders
  optimum      on the toy round the BRKGA reaches the exhaustive optimum of its own
               fitness, both with the original 'finish' score (singletons only)
               and with 'finish_per_order' (bundles allowed)
  rejected_by  a courier never gets an order that already rejected him
  seed         same seed -> same assignments; empty round -> []
"""
import itertools
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import Config  # noqa: E402
from models import Order, Courier, Location, EquityHistory  # noqa: E402
from brkga_policy import BRKGAPolicy, build_candidates, fitness_coverage  # noqa: E402

TOY = os.path.join(ROOT, 'tests', 'fixtures', 'hier', 'toy.json')


def _load_toy(**overrides):
    """Same reading of toy.json as hier.context.round_from_json, without gurobipy."""
    with open(TOY, encoding='utf8') as f:
        doc = json.load(f)
    p = doc['params']
    cfg = Config()
    cfg.meters_per_minute = p['meters_per_minute']
    cfg.pickup_service_min = p['pickup_service_min']
    cfg.dropoff_service_min = p['dropoff_service_min']
    cfg.late_tolerance_min = p.get('late_tolerance_min', 0.0)
    cfg.max_bundle_size = p.get('max_bundle_size', 3)
    cfg.pay_per_order = p.get('pay_per_order', 10.0)
    cfg.brkga_cand_top_k = p.get('top_k', 25)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    couriers = []
    for c in doc['couriers']:
        cr = Courier(courier_id=c['id'], on_time=c['on_time'], off_time=c['off_time'],
                     home_loc=Location(c['x'], c['y']))
        cr.condition = 'idle'
        cr.history = EquityHistory(earnings=c['earnings'], orders_delivered=c['orders_delivered'],
                                   active_time=c['active_time'], dist_traveled=c['dist_traveled'])
        couriers.append(cr)
    orders = []
    for o in doc['orders']:
        od = Order(order_id=o['id'], placement_time=o['placement_time'],
                   store_loc=Location(*o['store']), user_loc=Location(*o['user']),
                   ready_time=o['ready_time'], target_click_to_door=o['target_click_to_door'],
                   max_click_to_door=o['max_click_to_door'])
        od.rejected_by = set(o.get('rejected_by', []))
        orders.append(od)
    state = {'L_t': {c.courier_id: c for c in couriers},
             'O_t': {o.order_id: o for o in orders},
             'H_t': {c.courier_id: c.history for c in couriers},
             'time': float(doc['time'])}
    return cfg, couriers, orders, state


def _brute(cands, singles_only=False):
    """Exhaustive optimum of fitness_coverage over the candidate set."""
    keys = [k for k in cands if not singles_only or len(k[1]) == 1]
    cids = sorted({k[0] for k in keys})
    opts = {c: [None] + [k for k in keys if k[0] == c] for c in cids}
    best = float('inf')
    for combo in itertools.product(*[opts[c] for c in cids]):
        chosen = [k for k in combo if k is not None]
        seen = set()
        ok = True
        for _, rkey in chosen:
            for oid in rkey:
                ok = ok and oid not in seen
                seen.add(oid)
        if not ok:
            continue
        fit = fitness_coverage(len(seen), 4, sum(cands[k]['total_tt'] for k in chosen))
        best = min(best, fit)
    return best


def test_candidates_match_hier_prefilter():
    cfg, couriers, orders, state = _load_toy()
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.brkga_cand_top_k)
    assert len(cands) == 18
    assert all(len(k[1]) in (1, 2) for k in cands)


def test_contract_and_pay():
    cfg, couriers, orders, state = _load_toy(brkga_population=12, brkga_generations=8)
    pol = BRKGAPolicy(cfg)
    out = pol.assign(state)
    assert out, 'toy round must produce assignments'
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.brkga_cand_top_k)
    seen_c, seen_o = set(), set()
    for cid, seq, pay in out:
        assert cid not in seen_c
        seen_c.add(cid)
        rkey = tuple(sorted(seq))
        assert (cid, rkey) in cands, 'every returned route must be a feasible shared candidate'
        assert seq == cands[(cid, rkey)]['sequence']
        assert not (set(seq) & seen_o)
        seen_o.update(seq)
        assert pay == pytest.approx(cfg.pay_per_order * len(seq))
    assert len(pol.rounds) == 1 and pol.rounds[0]['candidates'] == 18


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_original_score_reaches_singleton_optimum(seed):
    """'finish' never prefers a bundle, so the reachable optimum is the best
    singleton matching: 3 couriers -> 3 orders covered."""
    cfg, couriers, orders, state = _load_toy(seed=seed, brkga_population=30, brkga_generations=20,
                                             brkga_score='finish')
    pol = BRKGAPolicy(cfg)
    out = pol.assign(state)
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.brkga_cand_top_k)
    assert all(len(seq) == 1 for _, seq, _ in out)
    assert sum(len(seq) for _, seq, _ in out) == 3
    assert pol.rounds[0]['best_fitness'] == pytest.approx(_brute(cands, singles_only=True))


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_per_order_score_reaches_full_optimum(seed):
    """With 'finish_per_order' bundles compete and all 4 orders get covered."""
    cfg, couriers, orders, state = _load_toy(seed=seed, brkga_population=30, brkga_generations=20,
                                             brkga_score='finish_per_order')
    pol = BRKGAPolicy(cfg)
    out = pol.assign(state)
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.brkga_cand_top_k)
    assert sum(len(seq) for _, seq, _ in out) == 4
    assert pol.rounds[0]['best_fitness'] == pytest.approx(_brute(cands))


def test_travel_fitness_runs():
    cfg, _, _, state = _load_toy(brkga_fitness='travel', brkga_population=8, brkga_generations=4)
    out = BRKGAPolicy(cfg).assign(state)
    assert out


def test_rejected_by_is_respected():
    cfg, couriers, orders, state = _load_toy(brkga_population=12, brkga_generations=8)
    for o in orders:
        o.rejected_by.add(1)          # courier 1 rejected everything
    out = BRKGAPolicy(cfg).assign(state)
    assert all(cid != 1 for cid, _, _ in out)
    assert out


def test_seed_reproducible_and_empty_round():
    cfg, _, _, state = _load_toy(seed=7, brkga_population=10, brkga_generations=5)
    a = BRKGAPolicy(cfg).assign(state)
    b = BRKGAPolicy(cfg).assign(state)
    assert a == b
    assert BRKGAPolicy(cfg).assign({'L_t': {}, 'O_t': state['O_t'], 'H_t': {}, 'time': 0.0}) == []
    assert BRKGAPolicy(cfg).assign({'L_t': state['L_t'], 'O_t': {}, 'H_t': {}, 'time': 0.0}) == []


def test_bad_config_rejected():
    cfg, _, _, _ = _load_toy(brkga_fitness='nope')
    with pytest.raises(ValueError):
        BRKGAPolicy(cfg)
