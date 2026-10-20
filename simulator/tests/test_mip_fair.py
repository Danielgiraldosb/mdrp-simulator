"""
MIPFairPolicy (mip_fair.py) -- per-window MIP with the elastic Gini constraint.

  projections  w_c^0 / w_c(r) under hourly and total bases
  alpha = 1    constraint inactive: coverage 4 on the toy (same as ILP max_coverage), v = 0
  fairness     alpha = 0, priority fairness: (min Gini excess, max coverage) equals the
               exhaustive lexicographic optimum over the shared candidates
  coverage     priority coverage: coverage 4 and, among coverage-4 assignments, minimal excess
  contract     each courier / order at most once, routes are candidates, pay = flat x orders
  fallback     no PuLP -> greedy; empty round -> []
"""
import itertools
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models import EquityHistory  # noqa: E402
from brkga_policy import build_candidates  # noqa: E402
from mip_fair import MIPFairPolicy, projected_earnings, gini_excess  # noqa: E402
from tests.test_brkga import _load_toy  # noqa: E402

pytest.importorskip('pulp')


def _setup(**over):
    cfg, couriers, orders, state = _load_toy(**over)
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.mipfair_cand_top_k)
    hist = {c.courier_id: c.history for c in couriers}
    return cfg, state, cands, hist


def _brute(cands, hist, basis, pay, alpha, priority):
    """Exhaustive lexicographic optimum of (excess, coverage) or (coverage, excess)."""
    w0, w_opt = projected_earnings(cands, hist, basis, pay)
    cids = sorted(hist)
    w_ref = sum(max(w0[c], max((w_opt[k] for k in cands if k[0] == c), default=0.0)) for c in cids)
    opts = {c: [None] + [k for k in cands if k[0] == c] for c in cids}
    best = None
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
        w = dict(w0)
        for k in chosen:
            w[k[0]] = w_opt[k]
        ex = round(gini_excess(w, alpha, w_ref), 6)
        cov = len(seen)
        key = (ex, -cov) if priority == 'fairness' else (-cov, ex)
        if best is None or key < best:
            best = key
    return best


def test_projected_earnings_bases():
    h = {1: EquityHistory(earnings=8.0, active_time=60.0), 2: EquityHistory()}
    cands = {(1, (1,)): {'total_tt': 30.0}, (2, (1, 2)): {'total_tt': 60.0}}
    w0, w = projected_earnings(cands, h, 'hourly', 10.0)
    assert w0 == {1: 8.0, 2: 0.0}
    assert w[(1, (1,))] == pytest.approx(18.0 / 1.5)
    assert w[(2, (1, 2))] == pytest.approx(20.0 / 1.0)
    w0, w = projected_earnings(cands, h, 'total', 10.0)
    assert w0 == {1: 8.0, 2: 0.0} and w[(2, (1, 2))] == 20.0
    with pytest.raises(ValueError):
        projected_earnings(cands, h, 'nope', 10.0)
    assert gini_excess({1: 5.0, 2: 5.0}, 0.0, 10.0) == 0.0
    assert gini_excess({1: 0.0, 2: 10.0}, 0.0, 10.0) == pytest.approx(10.0 / 20.0)
    assert gini_excess({1: 0.0, 2: 10.0}, 1.0, 10.0) == 0.0


def test_alpha_one_is_plain_coverage():
    cfg, state, cands, hist = _setup(mipfair_alpha=1.0)
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    assert sum(len(seq) for _, seq, _ in out) == 4
    rec = pol.rounds[-1]
    assert rec['v'] == pytest.approx(0.0, abs=1e-6) and rec['coverage'] == 4
    assert rec['candidates'] == 18 and rec['gini_before'] > 0


@pytest.mark.parametrize('basis', ['hourly', 'total'])
def test_fairness_priority_matches_brute_force(basis):
    cfg, state, cands, hist = _setup(mipfair_alpha=0.0, mipfair_priority='fairness', mipfair_basis=basis)
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    rec = pol.rounds[-1]
    ex, neg_cov = _brute(cands, hist, basis, cfg.pay_per_order, 0.0, 'fairness')
    assert round(rec['excess_after'], 6) == pytest.approx(ex, abs=1e-5)
    assert sum(len(seq) for _, seq, _ in out) == -neg_cov == rec['coverage']


def test_coverage_priority_matches_brute_force():
    cfg, state, cands, hist = _setup(mipfair_alpha=0.0, mipfair_priority='coverage')
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    rec = pol.rounds[-1]
    neg_cov, ex = _brute(cands, hist, 'hourly', cfg.pay_per_order, 0.0, 'coverage')
    assert -neg_cov == 4 == sum(len(seq) for _, seq, _ in out)
    assert round(rec['excess_after'], 6) == pytest.approx(ex, abs=1e-5)


def test_fairness_reduces_gini_vs_alpha_one():
    cfg1, state, _, _ = _setup(mipfair_alpha=1.0)
    p1 = MIPFairPolicy(cfg1)
    p1.assign(state)
    cfg0, state0, _, _ = _setup(mipfair_alpha=0.0, mipfair_priority='fairness')
    p0 = MIPFairPolicy(cfg0)
    p0.assign(state0)
    assert p0.rounds[-1]['gini_after'] <= p1.rounds[-1]['gini_after'] + 1e-9


def test_contract_rejections_and_fallbacks():
    cfg, state, cands, _ = _setup(mipfair_alpha=0.3)
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    seen_c, seen_o = set(), set()
    for cid, seq, pay in out:
        assert cid not in seen_c
        seen_c.add(cid)
        rkey = tuple(sorted(seq))
        assert (cid, rkey) in cands and seq == cands[(cid, rkey)]['sequence']
        assert not (set(seq) & seen_o)
        seen_o.update(seq)
        assert pay == pytest.approx(cfg.pay_per_order * len(seq))
    for o in state['O_t'].values():
        o.rejected_by.add(1)
    out = MIPFairPolicy(cfg).assign(state)
    assert out and all(cid != 1 for cid, _, _ in out)
    assert MIPFairPolicy(cfg).assign({'L_t': {}, 'O_t': state['O_t'], 'H_t': {}, 'time': 0.0}) == []
    nop = MIPFairPolicy(cfg)
    nop._pulp = None
    assert nop.assign(state)                      # greedy fallback still assigns
    with pytest.raises(ValueError):
        cfg.mipfair_alpha = 1.5
        MIPFairPolicy(cfg)


def test_scope_all_includes_busy_couriers_with_fixed_earnings():
    """A busy courier in H_all enters the Gini with fixed earnings and never gets a route."""
    cfg, state, cands, hist = _setup(mipfair_alpha=0.0, mipfair_priority='fairness', mipfair_scope='all')
    busy = EquityHistory(earnings=200.0, active_time=60.0)      # very rich, not idle
    state['H_all'] = dict(state['H_t'])
    state['H_all'][99] = busy
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    rec = pol.rounds[-1]
    assert rec['n_couriers'] == 4 and all(cid != 99 for cid, _, _ in out)
    # the fixed rich courier raises the Gini seen by the model
    cfg_idle, state_idle, _, _ = _setup(mipfair_alpha=0.0, mipfair_priority='fairness', mipfair_scope='idle')
    pol_idle = MIPFairPolicy(cfg_idle)
    pol_idle.assign(state_idle)
    assert rec['gini_before'] > pol_idle.rounds[-1]['gini_before']
    cfg.mipfair_scope = 'nope'
    with pytest.raises(ValueError):
        MIPFairPolicy(cfg)
