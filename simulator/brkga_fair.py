"""
BRKGAFairPolicy -- BRKGA-Fair of the thesis (Phase 4, l. 890): BRKGA-Coverage
with a fairness decoder that uses the accumulated equity history H_t to bias
assignment towards under-served couriers "while staying within the coverage
constraint".

It is BRKGAPolicy with ONE override, ``_score``:

    score(route, courier) = base_score(route, courier) - weight * deficit_c

where base_score is the parent's rule (cfg.brkga_score: 'finish' or
'finish_per_order', both in minutes) and

    deficit_c = max(0, mean_w - w_c) / mean_w        in [0, 1]

is the courier's relative shortfall against the mean of the idle couriers of
this round, computed on h_c(t) = (earn_c, orders_c, active_c) from
state['H_t']:

  cfg.brkga_fair_basis = 'hourly'  w_c = earn_c / active_c  (same basis as F_Gini, eq:gini;
                                   0 when the courier has no active time yet)
  cfg.brkga_fair_basis = 'total'   w_c = earn_c             (the basis HierContext uses)

cfg.brkga_fair_weight is in minutes: a courier with full deficit (w_c = 0) is
treated as if every route of his finished ``weight`` minutes earlier. weight = 0
reproduces BRKGAPolicy exactly (same seed, same output).

Coverage is protected the same way as in the parent: the fitness that ranks
the population is unchanged (coverage first), so the deficit only redirects
routes among decodings, and the population keeps the coverage-maximal ones.
This is the "dynamic-fair" variant of the thesis (G2). The "myopic-fair"
control (balance inside the window only) is, in this simulator, the plain
BRKGAPolicy: a courier takes at most one route per round, so within-round
balance is already enforced and there is no further within-window signal --
see docs/paper-cmdp/porte-brkga.md, section BRKGA-Fair.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from config import Config
from brkga_policy import BRKGAPolicy
import fair_history as fh


def deficits_of(w: Dict[int, float]) -> Tuple[Dict[int, float], float]:
    """{courier_id: max(0, mean_w - w_c) / mean_w} for a value per courier."""
    if not w:
        return {}, 0.0
    mean_w = sum(w.values()) / len(w)
    if mean_w <= 0.0:
        return {cid: 0.0 for cid in w}, mean_w
    return {cid: max(0.0, mean_w - wc) / mean_w for cid, wc in w.items()}, mean_w


def relative_deficits(histories: Dict[int, Any], basis: str) -> Tuple[Dict[int, float], float]:
    """{courier_id: max(0, mean_w - w_c) / mean_w}, mean_w over the given couriers (first generation)."""
    if basis == 'hourly':
        w = {cid: float(h.hourly_earnings) for cid, h in histories.items()}
    elif basis == 'total':
        w = {cid: float(h.earnings) for cid, h in histories.items()}
    else:
        raise ValueError(f"brkga_fair_basis must be 'hourly' or 'total', got {basis!r}")
    if not w:
        return {}, 0.0
    mean_w = sum(w.values()) / len(w)
    if mean_w <= 0.0:
        return {cid: 0.0 for cid in w}, mean_w
    return {cid: max(0.0, mean_w - wc) / mean_w for cid, wc in w.items()}, mean_w


class BRKGAFairPolicy(BRKGAPolicy):
    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.weight = float(cfg.brkga_fair_weight)
        if self.weight < 0:
            raise ValueError("brkga_fair_weight must be >= 0")
        self.basis = cfg.brkga_fair_basis
        relative_deficits({}, self.basis)          # validates the basis early
        fh.validate(cfg)
        # second generation (E10): exposure basis and/or eligible population, over every logged-on
        # eligible courier (the mean is the day's population, not the round's)
        self.gen2 = cfg.fair_history == 'exposure' or cfg.fair_population == 'eligible'
        self._deficit: Dict[int, float] = {}
        self._mean_w = 0.0

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        idle = {cid: c for cid, c in state['L_t'].items() if c.is_available}
        hist = state.get('H_t') or {}
        if self.gen2 and self.basis == 'hourly':
            pop = fh.population(state, self.cfg, scope='all')
            t = state['time']
            w = {cid: fh.hourly(h, c, t, self.cfg) for cid, (c, h) in pop.items()}
            self._deficit, self._mean_w = deficits_of(w)
        else:
            self._deficit, self._mean_w = relative_deficits(
                {cid: hist.get(cid, c.history) for cid, c in idle.items()}, self.basis)
        out = super().assign(state)
        if self.rounds and self.rounds[-1].get('time') == state['time'] and 'mean_w' not in self.rounds[-1]:
            self.rounds[-1]['mean_w'] = self._mean_w
            self.rounds[-1]['deficit_assigned'] = [round(self._deficit.get(cid, 0.0), 4) for cid, _, _ in out]
        return out

    def _cand_priority(self, state: Dict[str, Any]):
        return self._deficit if self.cfg.fair_cand_deficit_k > 0 else None

    def _score(self, cand: Dict[str, Any], courier_id: int, t: float) -> float:
        return super()._score(cand, courier_id, t) - self.weight * self._deficit.get(courier_id, 0.0)
