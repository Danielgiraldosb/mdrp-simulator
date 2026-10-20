"""
Tests for the logit_ppk acceptance model (Etapa 2).
Run: python -m pytest tests/test_acceptance_ppk.py -q
"""
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from acceptance import LogitPayPerKm, build_acceptance_model, route_km  # noqa: E402
from config import Config  # noqa: E402
from models import Courier, Location, Order  # noqa: E402


def _order(oid, store_xy, user_xy):
    return Order(order_id=oid, placement_time=0.0, store_loc=Location(*store_xy),
                 user_loc=Location(*user_xy), ready_time=5.0,
                 target_click_to_door=40.0, max_click_to_door=90.0)


@pytest.fixture
def courier():
    return Courier(courier_id=1, on_time=0.0, off_time=600.0, home_loc=Location(0.0, 0.0))


def test_registered():
    assert isinstance(build_acceptance_model('logit_ppk'), LogitPayPerKm)


def test_route_km_sequences_drops(courier):
    o1 = _order(1, (1000.0, 0.0), (1000.0, 1000.0))
    o2 = _order(2, (1000.0, 0.0), (1000.0, 3000.0))
    # courier -> store 1 km, store -> o1 1 km, o1 -> o2 2 km = 4 km
    assert route_km(courier, [o1, o2]) == pytest.approx(4.0)
    assert route_km(courier, [o2, o1]) == pytest.approx(4.0)
    assert route_km(courier, []) == 0.0


@pytest.mark.parametrize('ppk, expected', [(1000.0, 0.57), (1500.0, 0.81), (2000.0, 0.91)])
def test_matches_interview_sheet_predictions(courier, ppk, expected):
    """Parametros_modelo: P(acepta | 1,000 / 1,500 / 2,000 COP/km) = 0.57 / 0.81 / 0.91."""
    cfg = Config(acceptance_mode='logit_ppk')
    o = _order(1, (0.0, 0.0), (2000.0, 0.0))          # route = 2 km
    p = LogitPayPerKm().prob(courier, [o], pay_offer=ppk * 2.0, cfg=cfg)
    assert p == pytest.approx(expected, abs=0.005)


def test_threshold_gives_one_half(courier):
    cfg = Config(acceptance_mode='logit_ppk')
    o = _order(1, (0.0, 0.0), (3000.0, 0.0))
    p = LogitPayPerKm().prob(courier, [o], pay_offer=cfg.accept_ppk_threshold * 3.0, cfg=cfg)
    assert p == pytest.approx(0.5)


def test_equivalent_to_a_plus_b_ln_ppk(courier):
    cfg = Config(acceptance_mode='logit_ppk', accept_ppk_threshold=800.0, accept_ppk_slope=2.0)
    o = _order(1, (0.0, 0.0), (1000.0, 0.0))
    pay = 1500.0
    a = -cfg.accept_ppk_slope * math.log(cfg.accept_ppk_threshold)
    expected = 1 / (1 + math.exp(-(a + cfg.accept_ppk_slope * math.log(pay / 1.0))))
    assert LogitPayPerKm().prob(courier, [o], pay, cfg) == pytest.approx(expected)


def test_monotone_in_pay_and_distance(courier):
    cfg = Config(acceptance_mode='logit_ppk')
    o_near = _order(1, (0.0, 0.0), (1000.0, 0.0))
    o_far = _order(2, (0.0, 0.0), (4000.0, 0.0))
    m = LogitPayPerKm()
    assert m.prob(courier, [o_near], 1000.0, cfg) < m.prob(courier, [o_near], 3000.0, cfg)
    assert m.prob(courier, [o_far], 3000.0, cfg) < m.prob(courier, [o_near], 3000.0, cfg)


def test_autoaccept_regime_is_certain(courier):
    cfg = Config(acceptance_mode='logit_ppk', accept_regime='autoaccept')
    o = _order(1, (0.0, 0.0), (5000.0, 0.0))
    assert LogitPayPerKm().prob(courier, [o], pay_offer=100.0, cfg=cfg) == 1.0


def test_bad_regime_raises(courier):
    cfg = Config(acceptance_mode='logit_ppk', accept_regime='whatever')
    o = _order(1, (0.0, 0.0), (1000.0, 0.0))
    with pytest.raises(ValueError):
        LogitPayPerKm().prob(courier, [o], 1000.0, cfg)


def test_zero_distance_and_zero_pay_guards(courier):
    cfg = Config(acceptance_mode='logit_ppk')
    o = _order(1, (0.0, 0.0), (0.0, 0.0))           # degenerate 0 km route
    p = LogitPayPerKm().prob(courier, [o], 2200.0, cfg)
    assert 0.0 < p <= 1.0 and math.isfinite(p)
    assert LogitPayPerKm().prob(courier, [o], 0.0, cfg) == 0.0


def test_other_modes_untouched(courier):
    o = _order(1, (0.0, 0.0), (1000.0, 0.0))
    assert build_acceptance_model('auto').prob(courier, [o], 1.0, Config()) == 1.0
    courier.acceptance_rate = 0.42
    assert build_acceptance_model('fixed').prob(courier, [o], 1.0, Config()) == 0.42
