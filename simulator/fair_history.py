"""
fair_history.py -- what the fairness policies read in the equity history (decision E10, 2026-10-21).

First generation (cfg.fair_history = 'active', cfg.fair_population = 'round'): the policies read
EquityHistory.hourly_earnings = earnings / active_time (minutes in motion or serving). That is a
productivity rate, nearly equal across couriers with work, so the deficit signal only separates
"never delivered" from "delivered" (analysis A2, diseno-experimental.md section 12.7), and the
population is the couriers of the round (plus H_all in MIP-Fair).

Second generation ('exposure', 'eligible'): the policies read what the paper's constraint measures,

    w_c(t) = earnings_c / max(t - on_time_c, floor) in hours          (exposure: hours connected so far)

over the ELIGIBLE couriers, those whose declared connection (off_time - on_time) is at least
cfg.fair_min_shift_min minutes; the idle eligible courier has w_c = 0 and the largest deficit, which grows
with every hour it waits. The floor (cfg.fair_exposure_floor_min) tames the first minutes of a connection.
Couriers below the minimum shift can still be dispatched; they do not enter the statistic.

The defaults reproduce the first generation exactly.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from config import Config


def validate(cfg: Config) -> None:
    if cfg.fair_history not in ('active', 'exposure'):
        raise ValueError(f"fair_history must be 'active' or 'exposure', got {cfg.fair_history!r}")
    if cfg.fair_population not in ('round', 'eligible'):
        raise ValueError(f"fair_population must be 'round' or 'eligible', got {cfg.fair_population!r}")
    if cfg.fair_min_shift_min < 0 or cfg.fair_exposure_floor_min <= 0:
        raise ValueError("fair_min_shift_min must be >= 0 and fair_exposure_floor_min > 0")


def is_eligible(courier: Any, cfg: Config) -> bool:
    if cfg.fair_population != 'eligible':
        return True
    return (courier.off_time - courier.on_time) >= cfg.fair_min_shift_min


def exposure_minutes(courier: Any, t: float, cfg: Config) -> float:
    return max(t - courier.on_time, cfg.fair_exposure_floor_min)


def hourly(history: Any, courier: Optional[Any], t: float, cfg: Config) -> float:
    """Current value of a courier under the configured basis (hourly basis of the policies)."""
    if cfg.fair_history == 'exposure':
        if courier is None:
            raise ValueError('exposure basis needs the courier object (on_time)')
        return float(history.earnings) / (exposure_minutes(courier, t, cfg) / 60.0)
    return float(history.hourly_earnings)


def projected_hourly(history: Any, courier: Optional[Any], t: float, pay: float, tt: float, cfg: Config) -> float:
    """Value after taking a route that pays ``pay`` and takes ``tt`` minutes."""
    if cfg.fair_history == 'exposure':
        if courier is None:
            raise ValueError('exposure basis needs the courier object (on_time)')
        minutes = max(t - courier.on_time + tt, cfg.fair_exposure_floor_min)
        return (float(history.earnings) + pay) / (minutes / 60.0)
    hours = (history.active_time + tt) / 60.0
    return (float(history.earnings) + pay) / hours if hours > 0 else 0.0


def population(state: Dict[str, Any], cfg: Config, scope: str = 'all'
               ) -> Dict[int, Tuple[Any, Any]]:
    """{courier_id: (courier, history)} of the couriers that enter the policy's statistic.

    scope 'idle': the idle couriers of the round (L_t); 'all': every logged-on courier (C_all, or
    L_t + H_all when the state carries no courier objects for the busy ones). With
    fair_population = 'eligible' the couriers below the minimum declared shift are dropped.
    """
    idle = {cid: c for cid, c in state['L_t'].items() if c.is_available}
    hist = state.get('H_t') or {}
    pop: Dict[int, Tuple[Any, Any]] = {cid: (c, hist.get(cid, c.history)) for cid, c in idle.items()}
    if scope == 'all':
        c_all = state.get('C_all')
        if c_all:
            for cid, c in c_all.items():
                pop.setdefault(cid, (c, c.history))
        else:
            for cid, h in (state.get('H_all') or {}).items():
                pop.setdefault(cid, (None, h))
    if cfg.fair_population == 'eligible':
        pop = {cid: (c, h) for cid, (c, h) in pop.items() if c is None or is_eligible(c, cfg)}
    return pop
