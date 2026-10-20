"""
PayBRKGAPolicy (pay_brkga.py) -- bi-objective coverage + F_Deficit with pay offers.

  contract     routes are shared candidates, each courier / order once, pays within
               base * (1 -+ pay_range)
  pay cost     lambda_pay alone drives every offer below the tariff
  deficit      lambda_deficit alone lifts the offer of the below-minimum-wage courier
               above the offer of the courier already above it
  acceptance   expected coverage uses the acceptance model (fixed rates)
  range 0      flat tariff, pay_ratio == 1
  record       per-round record carries pay_ratio, multipliers, expected_covered, f_deficit_proj
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from brkga_policy import build_candidates  # noqa: E402
from pay_brkga import PayBRKGAPolicy  # noqa: E402
from tests.test_brkga import _load_toy  # noqa: E402


def _run(**over):
    over.setdefault('brkga_population', 30)
    over.setdefault('brkga_generations', 20)
    over.setdefault('brkga_score', 'finish_per_order')
    cfg, couriers, orders, state = _load_toy(**over)
    pol = PayBRKGAPolicy(cfg)
    out = pol.assign(state)
    return cfg, couriers, orders, state, pol, out


def test_contract_and_pay_bounds():
    cfg, couriers, orders, state, pol, out = _run(seed=0)
    assert out
    cands = build_candidates(couriers, orders, state['time'], cfg, cfg.brkga_cand_top_k)
    seen_c, seen_o = set(), set()
    for cid, seq, pay in out:
        assert cid not in seen_c
        seen_c.add(cid)
        rkey = tuple(sorted(seq))
        assert (cid, rkey) in cands and seq == cands[(cid, rkey)]['sequence']
        assert not (set(seq) & seen_o)
        seen_o.update(seq)
        base = cfg.pay_per_order * len(seq)
        assert base * (1 - cfg.paybrkga_pay_range) - 1e-9 <= pay <= base * (1 + cfg.paybrkga_pay_range) + 1e-9
    rec = pol.rounds[-1]
    assert set(rec['multipliers']) == seen_c
    assert rec['expected_covered'] == pytest.approx(len(seen_o))      # auto acceptance
    assert 0.0 <= rec['f_deficit_proj'] <= 1.0


@pytest.mark.parametrize('seed', [0, 1])
def test_pay_weight_alone_pushes_offers_below_tariff(seed):
    cfg, _, _, _, pol, out = _run(seed=seed, paybrkga_lambda_deficit=0.0, paybrkga_lambda_pay=1.0)
    assert all(pay < cfg.pay_per_order * len(seq) for _, seq, pay in out)
    assert pol.rounds[-1]['pay_ratio'] < 1.0


@pytest.mark.parametrize('seed', [0, 1])
def test_deficit_weight_lifts_the_poor_courier(seed):
    """Courier 1 earns 8/h (< 15 minimum), courier 2 earns 30/h. With lambda_deficit
    only, the optimiser must pay courier 1 enough to clear the minimum wage."""
    cfg, _, _, _, pol, out = _run(seed=seed, paybrkga_lambda_deficit=1.0, paybrkga_lambda_pay=0.0,
                                  brkga_score='finish')
    pays = {cid: pay / (cfg.pay_per_order * len(seq)) for cid, seq, pay in out}
    assert 1 in pays and 2 in pays, 'singleton-only round uses all three couriers'
    assert pays[1] > 1.0
    assert pol.rounds[-1]['f_deficit_proj'] < 1.0


def test_expected_coverage_uses_acceptance_model():
    cfg, couriers, orders, state, pol, out = _run(seed=2, acceptance_mode='fixed')
    for c in couriers:
        c.acceptance_rate = 0.5
    keys = [(cid, tuple(sorted(seq))) for cid, seq, _ in out]
    mult = {cid: 1.0 for cid in state['L_t']}
    assert pol._expected_coverage(keys, mult) == pytest.approx(0.5 * sum(len(k[1]) for k in keys))


def test_zero_range_is_flat_tariff_and_bad_config():
    cfg, _, _, _, pol, out = _run(seed=3, paybrkga_pay_range=0.0, brkga_population=8, brkga_generations=4)
    assert all(pay == pytest.approx(cfg.pay_per_order * len(seq)) for _, seq, pay in out)
    assert pol.rounds[-1]['pay_ratio'] == pytest.approx(1.0)
    cfg.paybrkga_pay_range = 1.0
    with pytest.raises(ValueError):
        PayBRKGAPolicy(cfg)
    cfg.paybrkga_pay_range = 0.3
    cfg.paybrkga_lambda_pay = -1.0
    with pytest.raises(ValueError):
        PayBRKGAPolicy(cfg)


def test_empty_round():
    cfg, _, _, state, pol, _ = _run(seed=4, brkga_population=4, brkga_generations=2)
    assert pol.assign({'L_t': {}, 'O_t': state['O_t'], 'H_t': {}, 'time': 0.0}) == []
