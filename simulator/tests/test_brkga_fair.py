"""
BRKGAFairPolicy (brkga_fair.py) -- BRKGA-Coverage with the H_t deficit decoder.

  deficits   relative deficit on hourly / total earnings, mean over idle couriers
  weight 0   identical output to BRKGAPolicy with the same seed
  bias       with a large weight the richest courier (2) gets nothing while
             coverage stays at the optimum (4 with bundles, 3 without)
  coverage   never below plain BRKGA on the toy (same fitness ranking)
  record     per-round record carries mean_w and the deficits of the assigned couriers
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from models import EquityHistory  # noqa: E402
from brkga_policy import BRKGAPolicy  # noqa: E402
from brkga_fair import BRKGAFairPolicy, relative_deficits  # noqa: E402
from tests.test_brkga import _load_toy  # noqa: E402


def _covered(out):
    return sum(len(seq) for _, seq, _ in out)


def test_relative_deficits_hourly_and_total():
    h = {1: EquityHistory(earnings=8.0, active_time=60.0),
         2: EquityHistory(earnings=30.0, active_time=60.0),
         3: EquityHistory(earnings=14.0, active_time=30.0)}
    d, mean_w = relative_deficits(h, 'hourly')          # w = 8, 30, 28 -> mean 22
    assert mean_w == pytest.approx(22.0)
    assert d[1] == pytest.approx(14 / 22) and d[2] == 0.0 and d[3] == 0.0
    d, mean_w = relative_deficits(h, 'total')           # w = 8, 30, 14 -> mean 17.33
    assert mean_w == pytest.approx(52 / 3)
    assert d[2] == 0.0 and d[1] > d[3] > 0.0
    assert relative_deficits({}, 'hourly') == ({}, 0.0)
    zero = {1: EquityHistory(), 2: EquityHistory()}
    assert relative_deficits(zero, 'hourly')[0] == {1: 0.0, 2: 0.0}
    with pytest.raises(ValueError):
        relative_deficits(h, 'nope')


def test_weight_zero_equals_plain_brkga():
    cfg, _, _, state = _load_toy(seed=3, brkga_population=12, brkga_generations=8, brkga_fair_weight=0.0)
    assert BRKGAFairPolicy(cfg).assign(state) == BRKGAPolicy(cfg).assign(state)


@pytest.mark.parametrize('score', ['finish', 'finish_per_order'])
def test_large_weight_skips_richest_courier_without_losing_coverage(score):
    cfg, _, _, state = _load_toy(seed=1, brkga_population=20, brkga_generations=10,
                                 brkga_score=score, brkga_fair_weight=1000.0)
    out = BRKGAFairPolicy(cfg).assign(state)
    base = BRKGAPolicy(cfg).assign(state)
    assert _covered(out) == _covered(base)
    if score == 'finish_per_order':
        assert _covered(out) == 4
        assert all(cid != 2 for cid, _, _ in out), 'courier 2 has zero deficit and is not needed'
    else:
        assert _covered(out) == 3            # singleton-only: all three couriers are needed


def test_bias_moves_routes_towards_deficit_couriers():
    """Sum of deficits of the assigned couriers is at least the plain BRKGA's."""
    cfg, _, _, state = _load_toy(seed=5, brkga_population=20, brkga_generations=10,
                                 brkga_score='finish_per_order', brkga_fair_weight=10.0)
    fair = BRKGAFairPolicy(cfg)
    out = fair.assign(state)
    d = fair._deficit
    base = BRKGAPolicy(cfg).assign(state)
    assert sum(d[cid] for cid, _, _ in out) >= sum(d[cid] for cid, _, _ in base)
    rec = fair.rounds[-1]
    assert rec['mean_w'] == pytest.approx((8 + 30 + 14) / 3)
    assert len(rec['deficit_assigned']) == len(out)


def test_total_basis_and_missing_history():
    cfg, _, _, state = _load_toy(brkga_population=8, brkga_generations=4, brkga_fair_basis='total')
    pol = BRKGAFairPolicy(cfg)
    assert pol.assign(state)
    state_no_h = dict(state)
    state_no_h['H_t'] = {}
    assert pol.assign(state_no_h)            # falls back to courier.history
    cfg.brkga_fair_basis = 'nope'
    with pytest.raises(ValueError):
        BRKGAFairPolicy(cfg)
