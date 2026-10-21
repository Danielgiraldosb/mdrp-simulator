"""
PayBRKGAPolicy -- Pay-BRKGA of the thesis (Phase 4, l. 892; gap G3, eq:cost_plus):
a bi-objective BRKGA over coverage and F_Deficit that also DECIDES THE PAY
OFFER of every route, within a bounded range around the platform's tariff.

It is BRKGAPolicy with a longer chromosome and its own fitness:

  chromosome = [order keys | courier keys | pay genes, one per idle courier]
  multiplier m_c = (1 - delta) + 2 * delta * gene_c,   delta = cfg.paybrkga_pay_range
  pay_offer(c, r) = base_pay(r) * m_c,  base_pay(r) = cfg.pay_per_order * |r|

(with the flat tariff of the current loaders; when eq:tariff pi0 + pi1*dist
lands, the multiplier applies to pi1 only, as the thesis prescribes).

Fitness (lower is better), scalarised with cfg weights, all terms in [0, ~1]:

  f = (1 - E[covered] / n)                       expected coverage, E over the acceptance model
      + lambda_deficit * F_Deficit^proj           share of idle couriers below the minimum wage
                                                  after the round (hourly, assuming acceptance)
      + lambda_pay * (sum pay / sum base_pay - 1) pay cost relative to the tariff (eq:cost_plus)
      + 1e-3 * mean total_tt / 20                 tie-break, same scale as the original

E[covered] = sum_r |r| * P(accept | c, r, pay_offer) uses the SAME acceptance
model the simulator will draw from (cfg.acceptance_mode, e.g. logit_ppk), so
raising pay buys coverage only when the acceptance model says so; under
'auto' acceptance pay affects F_Deficit and cost only. The minimum wage is
cfg.min_wage_hourly, else cfg.guaranteed_pay_per_hour (as metrics.py).

The decoder is the parent's (cfg.brkga_score), so Pay-BRKGA changes WHO is
paid WHAT, not how routes are built. Sweeping lambda_pay traces the
cost-of-fairness curve of the thesis; lambda_deficit = 0 and
paybrkga_pay_range = 0 give back BRKGAPolicy's objective up to the tie-break.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from config import Config
from brkga_policy import BRKGAPolicy, _Round, CandKey
import fair_history as fh
from brkga_fair import deficits_of


class PayBRKGAPolicy(BRKGAPolicy):
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.pay_range = float(cfg.paybrkga_pay_range)
        if not 0.0 <= self.pay_range < 1.0:
            raise ValueError("paybrkga_pay_range must be in [0, 1)")
        self.lambda_deficit = float(cfg.paybrkga_lambda_deficit)
        self.lambda_pay = float(cfg.paybrkga_lambda_pay)
        if self.lambda_deficit < 0 or self.lambda_pay < 0:
            raise ValueError("paybrkga lambdas must be >= 0")
        self.min_wage = (cfg.min_wage_hourly if cfg.min_wage_hourly is not None
                         else cfg.guaranteed_pay_per_hour)
        self._couriers: Dict[int, Any] = {}
        self._orders: Dict[int, Any] = {}
        self._hist: Dict[int, Any] = {}
        self._t = 0.0
        self._cur_mult: Dict[int, float] = {}
        fh.validate(cfg)
        self.gen2 = cfg.fair_history == 'exposure' or cfg.fair_population == 'eligible'

    # -- Policy contract -------------------------------------------------------------------

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        self._couriers = {cid: c for cid, c in state['L_t'].items() if c.is_available}
        self._orders = dict(state['O_t'])
        hist = state.get('H_t') or {}
        self._hist = {cid: hist.get(cid, c.history) for cid, c in self._couriers.items()}
        self._t = state['time']
        if self.gen2:
            # E10: the projected deficit is over the eligible idle couriers, per hour connected so far
            pop = fh.population(state, self.cfg, scope='idle')
            self._hist = {cid: h for cid, (c, h) in pop.items()}
        out = super().assign(state)
        if not out:
            return out
        mult = self._multipliers(self._best_chrom, self._last_round)
        priced = [(cid, seq, self.pay_per_order * len(seq) * mult[cid]) for cid, seq, _ in out]
        rec = self.rounds[-1]
        base = sum(self.pay_per_order * len(seq) for _, seq, _ in out)
        rec['pay_ratio'] = sum(p for _, _, p in priced) / base if base else 1.0
        rec['multipliers'] = {cid: round(mult[cid], 4) for cid, _, _ in priced}
        rec['expected_covered'] = self._expected_coverage(
            [(cid, tuple(sorted(seq))) for cid, seq, _ in priced], mult)
        rec['f_deficit_proj'] = self._deficit_after(
            [(cid, tuple(sorted(seq))) for cid, seq, _ in priced], mult)
        return priced

    def _cand_priority(self, state: Dict[str, Any]):
        if self.cfg.fair_cand_deficit_k <= 0 or not self._hist:
            return None
        w = {cid: fh.hourly(h, self._couriers.get(cid), self._t, self.cfg) for cid, h in self._hist.items()}
        return deficits_of(w)[0]

    # -- Chromosome layout ---------------------------------------------------------------------

    def _evolve(self, rnd: _Round, t: float):
        rnd.chromosome_length = rnd.n_orders + 2 * rnd.n_couriers
        return super()._evolve(rnd, t)

    def _multipliers(self, chromosome: np.ndarray, rnd: _Round) -> Dict[int, float]:
        genes = chromosome[rnd.n_orders + rnd.n_couriers:]
        lo = 1.0 - self.pay_range
        return {cid: lo + 2.0 * self.pay_range * float(genes[i]) for i, cid in enumerate(rnd.courier_ids)}

    def decode(self, chromosome: np.ndarray, rnd: _Round, t: float):
        # remember this individual's pay genes: the parent calls _fitness right after decode
        self._cur_mult = self._multipliers(chromosome, rnd)
        return super().decode(chromosome[:rnd.n_orders + rnd.n_couriers], rnd, t)

    # -- Fitness -------------------------------------------------------------------------------

    def _pay(self, key: CandKey, mult: Dict[int, float]) -> float:
        return self.pay_per_order * len(key[1]) * mult[key[0]]

    def _expected_coverage(self, assignments: List[CandKey], mult: Dict[int, float]) -> float:
        exp = 0.0
        for cid, rkey in assignments:
            courier = self._couriers[cid]
            orders = [self._orders[oid] for oid in rkey]
            p = self.acceptance_model.prob(courier, orders, self._pay((cid, rkey), mult), self.cfg)
            exp += len(rkey) * p
        return exp

    def _deficit_after(self, assignments: List[CandKey], mult: Dict[int, float]) -> float:
        if not self._hist:
            return 0.0
        rnd = self._last_round
        w = {cid: fh.hourly(h, self._couriers.get(cid), self._t, self.cfg) for cid, h in self._hist.items()}
        for cid, rkey in assignments:
            if cid not in self._hist:
                continue                     # below the minimum shift: dispatched, not measured
            w[cid] = fh.projected_hourly(self._hist[cid], self._couriers.get(cid), self._t,
                                         self._pay((cid, rkey), mult), rnd.cands[(cid, rkey)]['total_tt'], self.cfg)
        return sum(1 for v in w.values() if v < self.min_wage) / len(w)

    def _fitness(self, covered: int, n_orders: int, total_tt: float,
                 assignments: List[CandKey]) -> float:
        mult = self._cur_mult
        exp_cov = self._expected_coverage(assignments, mult)
        base = sum(self.pay_per_order * len(rkey) for _, rkey in assignments)
        pay_excess = (sum(self._pay(k, mult) for k in assignments) / base - 1.0) if base else 0.0
        n_routes = max(1, len(assignments))
        return ((1.0 - exp_cov / n_orders)
                + self.lambda_deficit * self._deficit_after(assignments, mult)
                + self.lambda_pay * pay_excess
                + 1e-3 * (total_tt / n_routes) / 20.0)
