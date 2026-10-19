"""
Courier acceptance models -- independent of, and combinable with, ANY
assignment policy (Greedy, FairGreedy, or any of the 5 ILP objectives).

Selecting a mode via cfg.acceptance_mode never changes how orders get
matched to couriers -- it only changes the Bernoulli probability used once
a courier has already been notified of an offer, in
CourierActor._decide (simulator.py). Before this module, acceptance was
entangled with assignment: Greedy/FairGreedy/ILP could only ever use a
courier's fixed acceptance_rate, and the logistic formula only worked by
wrapping GreedyPolicy's own assign() inside a separate
LogisticAcceptancePolicy class. That made acceptance a non-transversal
choice (3 of 7 policies could use it, and only paired with Greedy's
matching). This module is the fix: one of 3 interchangeable models, picked
once via cfg.acceptance_mode, used by every Policy through the shared
Policy.acceptance_prob() in policies.py.

Modes (cfg.acceptance_mode)
----------------------------
  'auto'     -- every offer is accepted, unconditionally. Matches mdrplib's
                own assumption that an assigned route is always executed.
  'fixed'    -- each courier's acceptance rate is drawn once at load time
                from [cfg.min_acceptance_rate, cfg.max_acceptance_rate]
                (loader.py) and stays constant for the whole simulation.
                Set both bounds equal for a single global probability
                (e.g. --acceptance-range 0.8 0.8); leave them apart to
                study heterogeneous courier reliability.
  'logistic' -- p = sigma(beta0 + beta1*pay + beta2*dist_km + beta3*active_min),
                a probability that depends on the SPECIFIC offer (pay,
                distance, accumulated fatigue), not a fixed per-courier rate.
"""
from __future__ import annotations
import math
from typing import List

from config import Config
from models import Order, Courier
from distance import dist_km


class AcceptanceModel:
    def prob(self, courier: Courier, orders: List[Order],
             pay_offer: float, cfg: Config) -> float:
        raise NotImplementedError


class AutoAccept(AcceptanceModel):
    """Every offer is accepted -- the mdrplib-baseline default."""

    def prob(self, courier: Courier, orders: List[Order],
             pay_offer: float, cfg: Config) -> float:
        return 1.0


class FixedProbability(AcceptanceModel):
    """Each courier's own pre-drawn acceptance_rate (see loader.py)."""

    def prob(self, courier: Courier, orders: List[Order],
             pay_offer: float, cfg: Config) -> float:
        return courier.acceptance_rate


class LogisticAcceptance(AcceptanceModel):
    """
    p = sigma(beta0 + beta1*pay + beta2*dist_km + beta3*active_min)

    Coefficients live in Config (accept_beta0..3) -- illustrative
    placeholders rescaled to mdrplib's own (small) pay units and
    minute-based clock. Replace with MLE estimates from real
    acceptance/rejection data when available.
    """

    def prob(self, courier: Courier, orders: List[Order],
             pay_offer: float, cfg: Config) -> float:
        total_dist = sum(
            dist_km(courier.location, o.store_loc) + dist_km(o.store_loc, o.user_loc)
            for o in orders
        )
        z = (cfg.accept_beta0
             + cfg.accept_beta1 * pay_offer
             + cfg.accept_beta2 * total_dist
             + cfg.accept_beta3 * courier.history.active_time)
        return 1.0 / (1.0 + math.exp(-z))


_MODELS = {
    'auto': AutoAccept,
    'fixed': FixedProbability,
    'logistic': LogisticAcceptance,
}


def build_acceptance_model(mode: str) -> AcceptanceModel:
    cls = _MODELS.get(mode)
    if cls is None:
        raise ValueError(
            f"Unknown acceptance_mode '{mode}'. Choices: {', '.join(_MODELS)}"
        )
    return cls()
