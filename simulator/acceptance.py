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
  'logit_ppk' -- p = sigma(b * (ln(pay/km) - ln(theta))), the model estimated
                from the Bogota interviews (32 declared decisions, 11
                couriers, 2020 manual regime): theta = 903 COP/km is the pay
                per km at which P = 0.5, b = 2.89 the slope on ln(pay/km).
                Under cfg.accept_regime == 'autoaccept' (2021 regime, 64 %
                of surveyed couriers) every offer is accepted: the courier's
                decision is about being online, not about each order.
"""
from __future__ import annotations
import math
from typing import List

from config import Config
from models import Order, Courier
from distance import dist_km
from routing import sequence_stops


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


def route_km(courier: Courier, orders: List[Order]) -> float:
    """Courier -> store -> drop-offs in nearest-neighbour order (same
    sequencing as routing.route_feasibility), in km."""
    if not orders:
        return 0.0
    store = orders[0].store_loc
    km = dist_km(courier.location, store)
    cursor = store
    for o in sequence_stops(tuple(orders)):
        km += dist_km(cursor, o.user_loc)
        cursor = o.user_loc
    return km


class LogitPayPerKm(AcceptanceModel):
    """
    p = sigma(b * (ln(pay/km) - ln(theta)))  ==  sigma(a + b*ln(pay/km)) with
    a = -b*ln(theta). Parameters cfg.accept_ppk_threshold (theta, COP/km)
    and cfg.accept_ppk_slope (b); regime cfg.accept_regime.

    Check against the interview sheet (Parametros_modelo): at 1,000 / 1,500 /
    2,000 COP/km the model predicts 0.57 / 0.81 / 0.91.
    """

    def prob(self, courier: Courier, orders: List[Order],
             pay_offer: float, cfg: Config) -> float:
        if cfg.accept_regime == 'autoaccept':
            return 1.0
        if cfg.accept_regime != 'manual':
            raise ValueError(f"Unknown accept_regime '{cfg.accept_regime}'. Choices: manual, autoaccept")
        km = max(route_km(courier, orders), cfg.accept_ppk_min_km)
        if pay_offer <= 0:
            return 0.0
        z = cfg.accept_ppk_slope * (math.log(pay_offer / km) - math.log(cfg.accept_ppk_threshold))
        return 1.0 / (1.0 + math.exp(-z))


_MODELS = {
    'auto': AutoAccept,
    'fixed': FixedProbability,
    'logistic': LogisticAcceptance,
    'logit_ppk': LogitPayPerKm,
}


def build_acceptance_model(mode: str) -> AcceptanceModel:
    cls = _MODELS.get(mode)
    if cls is None:
        raise ValueError(
            f"Unknown acceptance_mode '{mode}'. Choices: {', '.join(_MODELS)}"
        )
    return cls()
