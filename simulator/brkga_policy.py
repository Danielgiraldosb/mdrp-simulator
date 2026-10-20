"""
BRKGAPolicy -- the BRKGA-Coverage / BRKGA-Travel rolling-horizon dispatcher of
MIC 2026 (``articulo MDRP/MDVRPTW_BRKGA/brkga_rolling_horizon.py``) ported to
the simulator's policy contract (policies.Policy):

  assign(state) -> [(courier_id, [order_ids in delivery sequence], pay_offer)]

One BRKGA per dispatch round, exactly like the original ran one BRKGA per
2-minute window. What is shared with Greedy / FairGreedy / ILP / Hier, so the
comparison is fair:

* the candidate set -- routing.generate_store_routes (singletons plus ONE
  urgency bundle per store) filtered by routing.route_feasibility over the
  cfg.brkga_cand_top_k nearest idle couriers per route and the orders'
  rejected_by sets. This is the same prefilter ilp_policy._precompute_routes
  and hier.context._generate_candidates use;
* the dispatch window (cfg.rolling_horizon), the acceptance model
  (cfg.acceptance_mode) and the pay rule (flat cfg.pay_per_order per order).

What is kept from the original BRKGA (see docs/paper-cmdp/porte-brkga.md for
the full list of what changed and why):

* chromosome = one random key per pending order + one per idle courier;
* decoder = walk the stores in order of their highest-priority order; at each
  store take the highest-priority remaining order, try its candidate routes
  (singleton, then the bundle it belongs to) against the first
  cfg.brkga_top_k_couriers couriers by courier key, keep the (route, courier)
  with the lowest score and repeat; no courier takes two routes per round;
* fitness_coverage / fitness_travel are copied verbatim (lower is better);
* elite / biased crossover / mutant generations with elite_bias 0.7.

The ONLY knobs a derived method needs to touch are ``_score`` (which route a
courier takes first inside the decoder) and ``_fitness`` (what the population
is ranked by). BRKGA-Fair of the thesis will override ``_score`` with the
equity deficit of H_t and leave everything else untouched.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import Config
from models import Order, Courier
from distance import dist_km
from routing import generate_store_routes, route_feasibility
from policies import Policy

logger = logging.getLogger(__name__)

RouteKey = Tuple[int, ...]
CandKey = Tuple[int, RouteKey]


# -- Fitness functions (verbatim from MDVRPTW_BRKGA/decoder.py) -------------------------------

def fitness_coverage(orders_covered: int, total_orders: int, total_travel_time: float) -> float:
    """Coverage first (tiered penalty on the uncovered share), then mean travel
    time per covered order normalised by a 20 min baseline. Lower is better."""
    if total_orders == 0:
        return 1e12
    coverage_rate = orders_covered / total_orders
    avg_travel = total_travel_time / max(orders_covered, 1)
    if coverage_rate < 0.50:
        penalty = 1e9 * (1 - coverage_rate)
    elif coverage_rate < 0.60:
        penalty = 1e7 * (1 - coverage_rate)
    else:
        penalty = 1e5 * (1 - coverage_rate)
    return penalty + (avg_travel / 20.0)


def fitness_travel(orders_covered: int, total_orders: int, total_travel_time: float) -> float:
    """Mean travel time per covered order first, with a milder coverage penalty."""
    if total_orders == 0:
        return 1e12
    coverage_rate = orders_covered / total_orders
    avg_travel = total_travel_time / max(orders_covered, 1)
    if coverage_rate < 0.50:
        penalty = 1e6 * (1 - coverage_rate)
    else:
        penalty = 1e4 * (1 - coverage_rate)
    return penalty + avg_travel


FITNESS = {'coverage': fitness_coverage, 'travel': fitness_travel}


# -- Candidate prefilter (same rule as ILPPolicy._precompute_routes / HierContext) -----------

def build_candidates(couriers: List[Courier], orders: List[Order], t: float, cfg: Config,
                     top_k: int) -> Dict[CandKey, Dict[str, Any]]:
    """
    (courier_id, route_key) -> {'lateness', 'total_tt', 'sequence', 'n_orders'}
    for every feasible pair, where route_key is the sorted tuple of order ids.
    Only the ``top_k`` idle couriers nearest to the route's store are tried and
    a courier that already rejected any order of the route is skipped.
    """
    cands: Dict[CandKey, Dict[str, Any]] = {}
    for route in generate_store_routes(orders, cfg.max_bundle_size):
        rkey = tuple(sorted(o.order_id for o in route))
        store_loc = route[0].store_loc
        ranked = sorted(couriers, key=lambda c: dist_km(c.location, store_loc))[:top_k]
        for c in ranked:
            if any(c.courier_id in o.rejected_by for o in route):
                continue
            res = route_feasibility(c, route, t, cfg)
            if res is None:
                continue
            cands[(c.courier_id, rkey)] = {
                'lateness': res['lateness'],
                'total_tt': res['total_tt'],
                'sequence': [o.order_id for o in res['sequence']],
                'n_orders': len(rkey),
            }
    return cands


# -- One dispatch round -------------------------------------------------------------------------

class _Round:
    """Precomputed lookups for one assign() call so each decode is a few dict hits."""

    def __init__(self, couriers: List[Courier], orders: List[Order],
                 cands: Dict[CandKey, Dict[str, Any]]):
        self.order_ids = [o.order_id for o in orders]
        self.courier_ids = [c.courier_id for c in couriers]
        self.n_orders = len(self.order_ids)
        self.n_couriers = len(self.courier_ids)
        self.cands = cands
        # store of each order (routing.store_key semantics: rounded location)
        self.store_of = {o.order_id: (round(o.store_loc.x), round(o.store_loc.y)) for o in orders}
        # candidate routes containing each order, smallest first (singleton, then bundle)
        self.routes_of: Dict[int, List[RouteKey]] = {oid: [] for oid in self.order_ids}
        for (_, rkey) in cands:
            for oid in rkey:
                if rkey not in self.routes_of[oid]:
                    self.routes_of[oid].append(rkey)
        for oid in self.order_ids:
            self.routes_of[oid].sort(key=len)
        self.chromosome_length = self.n_orders + self.n_couriers


class BRKGAPolicy(Policy):
    """
    Parameters are read from Config (all prefixed ``brkga_``):
      brkga_fitness         'coverage' | 'travel'      (BRKGA-Coverage / BRKGA-Travel)
      brkga_population      individuals per round      (MIC 2026 rolling default: 10)
      brkga_generations     generations per round      (MIC 2026 rolling default: 10)
      brkga_elite_frac, brkga_mutant_frac, brkga_elite_bias
      brkga_top_k_couriers  couriers tried per batch inside the decoder (original K = 3)
      brkga_cand_top_k      nearest couriers per route in the candidate prefilter (25, as ILP/Hier)
      brkga_score           'finish' (original: route finish time) |
                            'finish_per_order' (travel time / orders in the route)
    Randomness comes from one numpy Generator seeded with cfg.seed, so a run is
    reproducible; ``self.rounds`` keeps a compact per-round record.
    """

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.pay_per_order = cfg.pay_per_order
        self.fitness_type = cfg.brkga_fitness
        if self.fitness_type not in FITNESS:
            raise ValueError(f"brkga_fitness must be one of {sorted(FITNESS)}, got {self.fitness_type!r}")
        self.score_rule = cfg.brkga_score
        if self.score_rule not in ('finish', 'finish_per_order'):
            raise ValueError(f"brkga_score must be 'finish' or 'finish_per_order', got {self.score_rule!r}")
        self.pop_size = max(2, int(cfg.brkga_population))
        self.generations = max(1, int(cfg.brkga_generations))
        self.elite_size = max(1, int(self.pop_size * cfg.brkga_elite_frac))
        self.mutant_size = max(1, int(self.pop_size * cfg.brkga_mutant_frac))
        if self.elite_size + self.mutant_size >= self.pop_size:
            self.elite_size = max(1, self.pop_size // 2)
            self.mutant_size = max(0, self.pop_size - self.elite_size - 1)
        self.elite_bias = cfg.brkga_elite_bias
        self.top_k_couriers = max(1, int(cfg.brkga_top_k_couriers))
        self.cand_top_k = max(1, int(cfg.brkga_cand_top_k))
        self.rng = np.random.default_rng(cfg.seed)
        self.rounds: List[Dict[str, Any]] = []
        self._last_round: Optional[_Round] = None
        self._best_chrom: Optional[np.ndarray] = None

    # -- Policy contract -------------------------------------------------------------------

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        couriers = [c for c in state['L_t'].values() if c.is_available]
        orders = list(state['O_t'].values())
        t: float = state['time']
        if not couriers or not orders:
            return []

        cands = build_candidates(couriers, orders, t, self.cfg, self.cand_top_k)
        if not cands:
            return []

        rnd = _Round(couriers, orders, cands)
        self._last_round = rnd              # derived policies (Pay-BRKGA) map genes back to couriers
        best_assign, best_fit, decodes = self._evolve(rnd, t)
        self.rounds.append({
            'time': t, 'n_orders': rnd.n_orders, 'n_couriers': rnd.n_couriers,
            'candidates': len(cands), 'best_fitness': best_fit, 'decodes': decodes,
            'orders_covered': sum(len(rkey) for _, rkey in best_assign),
        })
        return [(cid, list(cands[(cid, rkey)]['sequence']), self.pay_per_order * len(rkey))
                for cid, rkey in best_assign]

    # -- Hooks for derived methods ------------------------------------------------------------

    def _score(self, cand: Dict[str, Any], courier_id: int, t: float) -> float:
        """Lower is better. Original rule: finish time of the route. The
        simulator has no return-to-base leg, so 'finish' is the arrival at the
        last drop-off, t + total_tt."""
        if self.score_rule == 'finish_per_order':
            return cand['total_tt'] / cand['n_orders']
        return t + cand['total_tt']

    def _fitness(self, covered: int, n_orders: int, total_tt: float,
                 assignments: List[CandKey]) -> float:
        return FITNESS[self.fitness_type](covered, n_orders, total_tt)

    # -- Decoder ---------------------------------------------------------------------------

    def decode(self, chromosome: np.ndarray, rnd: _Round, t: float
               ) -> Tuple[List[CandKey], int, float]:
        """Chromosome -> (assignments [(courier_id, route_key)], orders covered, total travel)."""
        n_o = rnd.n_orders
        order_keys = chromosome[:n_o]
        courier_keys = chromosome[n_o:]

        sorted_orders = [rnd.order_ids[i] for i in np.argsort(-order_keys, kind='stable')]
        priority = {rnd.courier_ids[i]: courier_keys[i] for i in range(rnd.n_couriers)}

        store_groups: Dict[Tuple[float, float], List[int]] = {}
        for oid in sorted_orders:
            store_groups.setdefault(rnd.store_of[oid], []).append(oid)

        free = list(rnd.courier_ids)
        free.sort(key=lambda cid: priority[cid], reverse=True)
        assignments: List[CandKey] = []
        covered = 0
        total_tt = 0.0

        for store_orders in store_groups.values():
            if not free:
                break
            pending = list(store_orders)
            while pending and free:
                head = pending[0]
                pending_set = set(pending)
                best: Optional[CandKey] = None
                best_score = float('inf')
                for rkey in rnd.routes_of[head]:
                    if not all(oid in pending_set for oid in rkey):
                        continue
                    for cid in free[:self.top_k_couriers]:
                        cand = rnd.cands.get((cid, rkey))
                        if cand is None:
                            continue
                        s = self._score(cand, cid, t)
                        if s < best_score:
                            best_score, best = s, (cid, rkey)
                if best is None:
                    # original: abandon the store; here: skip this order and go on
                    pending.pop(0)
                    continue
                cid, rkey = best
                assignments.append(best)
                covered += len(rkey)
                total_tt += rnd.cands[best]['total_tt']
                pending = [oid for oid in pending if oid not in rkey]
                free.remove(cid)
        return assignments, covered, total_tt

    # -- Evolution (same scheme as BRKGARollingHorizon._optimize_window) ------------------

    def _evolve(self, rnd: _Round, t: float) -> Tuple[List[CandKey], float, int]:
        L = rnd.chromosome_length
        pop = self.rng.uniform(0.0, 1.0, (self.pop_size, L))
        best_assign: List[CandKey] = []
        best_fit = float('inf')
        decodes = 0
        for gen in range(self.generations):
            fits = np.empty(self.pop_size)
            sols = []
            for i in range(self.pop_size):
                a, cov, tt = self.decode(pop[i], rnd, t)
                decodes += 1
                sols.append(a)
                fits[i] = self._fitness(cov, rnd.n_orders, tt, a)
            gi = int(np.argmin(fits))
            if fits[gi] < best_fit:
                best_fit, best_assign = float(fits[gi]), sols[gi]
                self._best_chrom = pop[gi].copy()
            if gen == self.generations - 1:
                break
            order = np.argsort(fits, kind='stable')
            elite_idx = order[:self.elite_size]
            non_elite_idx = order[self.elite_size:]
            nxt = [pop[i] for i in elite_idx]
            n_off = self.pop_size - self.elite_size - self.mutant_size
            for _ in range(n_off):
                e = pop[self.rng.choice(elite_idx)]
                ne = (pop[self.rng.choice(non_elite_idx)] if len(non_elite_idx)
                      else self.rng.uniform(0.0, 1.0, L))
                mask = self.rng.random(L) < self.elite_bias
                nxt.append(np.where(mask, e, ne))
            for _ in range(self.mutant_size):
                nxt.append(self.rng.uniform(0.0, 1.0, L))
            pop = np.array(nxt)
        return best_assign, best_fit, decodes
