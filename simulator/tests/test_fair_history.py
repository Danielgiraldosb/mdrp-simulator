"""
fair_history.py (E10) -- exposure basis, eligible population, coverage slack of MIP-Fair.

  defaults     fair_history='active', fair_population='round' reproduce the first generation
  exposure     earnings per hour connected so far, with the floor; idle courier = 0
  eligible     a courier whose declared connection is below the minimum leaves the statistic
               but can still be dispatched (BRKGA-Fair, Pay-BRKGA, MIP-Fair do not crash)
  slack        MIP-Fair with cov_slack = 1 under coverage priority reaches the fairness-first v
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models import EquityHistory  # noqa: E402
import fair_history as fh  # noqa: E402
from brkga_fair import BRKGAFairPolicy, deficits_of  # noqa: E402
from pay_brkga import PayBRKGAPolicy  # noqa: E402
from tests.test_brkga import _load_toy  # noqa: E402


class _C:
    def __init__(self, on, off):
        self.on_time, self.off_time = on, off
        self.is_available = True
        self.history = EquityHistory()


def _covered(out):
    return sum(len(seq) for _, seq, _ in out)


def test_exposure_values_and_floor():
    cfg, _, _, _ = _load_toy(fair_history='exposure', fair_exposure_floor_min=30.0)
    c = _C(on=0.0, off=600.0)
    h = EquityHistory(earnings=2200.0, active_time=10.0)
    assert fh.hourly(h, c, 120.0, cfg) == pytest.approx(1100.0)          # 2 h connected
    assert fh.hourly(h, c, 5.0, cfg) == pytest.approx(4400.0)            # floored at 30 min
    assert fh.hourly(EquityHistory(), c, 120.0, cfg) == 0.0               # idle: zero, max deficit
    assert fh.projected_hourly(h, c, 120.0, 2200.0, 60.0, cfg) == pytest.approx(4400.0 / 3.0)
    # first generation: per active hour, independent of the connection
    cfg.fair_history = 'active'
    assert fh.hourly(h, c, 120.0, cfg) == pytest.approx(13200.0)
    assert fh.projected_hourly(h, None, 120.0, 2200.0, 20.0, cfg) == pytest.approx(4400.0 / 0.5)


def test_eligibility_and_population():
    cfg, couriers, orders, state = _load_toy(fair_population='eligible', fair_min_shift_min=60.0)
    short = min(state['L_t'])
    c = state['L_t'][short]
    c.off_time = c.on_time + 10.0
    pop = fh.population(state, cfg, scope='all')
    assert short not in pop and len(pop) == len(state['L_t']) - 1
    cfg.fair_population = 'round'
    assert short in fh.population(state, cfg, scope='all')
    with pytest.raises(ValueError):
        fh.validate(_load_toy(fair_history='nope')[0])


def test_deficits_of():
    d, m = deficits_of({1: 0.0, 2: 10.0, 3: 20.0})
    assert m == pytest.approx(10.0) and d == {1: 1.0, 2: 0.0, 3: 0.0}
    assert deficits_of({}) == ({}, 0.0)


def test_defaults_reproduce_first_generation():
    cfg, _, _, state = _load_toy(seed=3, brkga_population=12, brkga_generations=8, brkga_fair_weight=10.0)
    base = BRKGAFairPolicy(cfg).assign(state)
    cfg2, _, _, state2 = _load_toy(seed=3, brkga_population=12, brkga_generations=8, brkga_fair_weight=10.0,
                                   fair_history='active', fair_population='round')
    assert BRKGAFairPolicy(cfg2).assign(state2) == base


@pytest.mark.parametrize('policy_cls', [BRKGAFairPolicy, PayBRKGAPolicy])
def test_gen2_short_shift_courier_is_dispatchable_but_not_measured(policy_cls):
    cfg, _, _, state = _load_toy(seed=1, brkga_population=20, brkga_generations=10,
                                 brkga_score='finish_per_order', brkga_fair_weight=20.0,
                                 fair_history='exposure', fair_population='eligible', fair_min_shift_min=60.0)
    short = min(state['L_t'])
    state['L_t'][short].off_time = state['L_t'][short].on_time + 10.0
    pol = policy_cls(cfg)
    out = pol.assign(state)
    assert _covered(out) >= 3
    if policy_cls is BRKGAFairPolicy:
        assert short not in pol._deficit


def test_mipfair_gen2_and_slack():
    pulp = pytest.importorskip('pulp')  # noqa: F841
    from mip_fair import MIPFairPolicy
    # eligible population drops the short-shift courier from the Gini, the round still assigns
    cfg, _, _, state = _load_toy(mipfair_alpha=0.30, mipfair_priority='coverage', mipfair_scope='all',
                                 fair_history='exposure', fair_population='eligible', fair_min_shift_min=60.0)
    short = min(state['L_t'])
    state['L_t'][short].off_time = state['L_t'][short].on_time + 10.0
    state['C_all'] = dict(state['L_t'])
    pol = MIPFairPolicy(cfg)
    out = pol.assign(state)
    assert _covered(out) >= 3
    assert pol.rounds[-1]['n_couriers'] == len(state['L_t']) - 1
    # full slack under coverage priority minimises v as freely as the fairness-first order
    cfg_f, _, _, st_f = _load_toy(mipfair_alpha=0.30, mipfair_priority='fairness', mipfair_scope='all')
    cfg_s, _, _, st_s = _load_toy(mipfair_alpha=0.30, mipfair_priority='coverage', mipfair_scope='all',
                                  mipfair_cov_slack=1.0)
    pf, ps = MIPFairPolicy(cfg_f), MIPFairPolicy(cfg_s)
    pf.assign(st_f)
    ps.assign(st_s)
    assert ps.rounds[-1]['v'] == pytest.approx(pf.rounds[-1]['v'], abs=1e-6)
    with pytest.raises(ValueError):
        MIPFairPolicy(_load_toy(mipfair_cov_slack=1.5)[0])
