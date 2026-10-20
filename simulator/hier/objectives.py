"""
Objective catalogue for the hierarchical MDRP dispatch model (épica §3.3).

One pass per objective, highest priority first, every objective in the SAME
sense (MAX): "the less the better" objectives enter with a negative sign.
All logic (skip, settings, progress) goes by NAME, never by Gurobi's
technical index, because an objective may not exist in a given run
(``exists`` below, or a ``DISABLE_HIER_<NAME>`` gate).

Default hierarchy (see docs/mdrp-jerarquia-objetivos.html for the rationale
and the open questions):

  priority  name       maximises                                  sense  protected  lock reltol
  --------  ---------  -----------------------------------------  -----  ---------  -----------
     40     coverage   number of pending orders assigned          MAX    no         0
     30     lateness   − minutes of overage vs. target c2d        MIN    no         1e-4
     20     equity     deficit-weighted orders to poorer couriers MAX    no         1e-4
     10     cost       − minutes of courier time (travel+service) MIN    no         1e-4

Decisions taken on 2026-10-20 (docs/mdrp-jerarquia-objetivos.md §Decisiones):
  1A order coverage > lateness > equity > cost · 2A lateness in minutes ·
  3C equity deficit on ACCUMULATED earnings of the day (not hourly) ·
  4C lock tolerance 0 on coverage, 1e-4 relative on the rest · 5C no protected
  objectives (every pass accepts mip_gap) · 6A no couriers-used objective ·
  7A one round per model · 8A flat pay · 9A simulator seed in runs, none in prod.

The old ``max_throughput`` (λ·travel + μ·lateness) is intentionally absent:
it is a weighted sum of ``lateness`` and ``cost`` and the framework forbids
weighted sums between objectives (épica §1.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

from .flags import disabled


@dataclass(frozen=True)
class ObjectiveSpec:
    name: str
    priority: int
    label: str                      # human label for logs / deck
    sense: str                      # 'MAX' | 'MIN'  (MIN enters as -expr)
    protected: bool                 # rejects mip_gap overrides (quality is non-negotiable)
    description: str
    # coefficient of x[c, r] in the (MAX) expression -- receives the candidate record
    coef: Callable[[Dict[str, Any]], float]
    # True when the objective makes sense for this round (épica: "¿cuándo existe?")
    exists: Callable[[Dict[str, Any]], bool] = lambda ctx: True


def _coverage_coef(cand: Dict[str, Any]) -> float:
    return float(cand['n_orders'])


def _lateness_coef(cand: Dict[str, Any]) -> float:
    return -float(cand['lateness'])


def _equity_coef(cand: Dict[str, Any]) -> float:
    # deficit weight d_c = max(0, mean accumulated earnings - courier accumulated earnings)  (3C)
    return float(cand['n_orders']) * float(cand['deficit'])


def _cost_coef(cand: Dict[str, Any]) -> float:
    return -float(cand['total_tt'])


CATALOGUE: Dict[str, ObjectiveSpec] = {
    'coverage': ObjectiveSpec(
        name='coverage', priority=40, label='Cobertura', sense='MAX', protected=False,
        description='Pedidos pendientes asignados en esta ronda (una ruta cubre |r| pedidos).',
        coef=_coverage_coef,
    ),
    'lateness': ObjectiveSpec(
        name='lateness', priority=30, label='Atraso', sense='MIN', protected=False,
        description='Minutos de exceso sobre el target click-to-door, sumados sobre los pedidos asignados.',
        coef=_lateness_coef,
    ),
    'equity': ObjectiveSpec(
        name='equity', priority=20, label='Equidad', sense='MAX', protected=False,
        description='Pedidos entregados a repartidores por debajo de la media de ganancia acumulada '
                    'del día, ponderados por su déficit.',
        coef=_equity_coef,
        exists=lambda ctx: any(c['deficit'] > 0 for c in ctx['candidates']),
    ),
    'cost': ObjectiveSpec(
        name='cost', priority=10, label='Costo', sense='MIN', protected=False,
        description='Minutos de repartidor comprometidos (viaje + servicio) por las rutas asignadas.',
        coef=_cost_coef,
    ),
}

DEFAULT_ORDER: List[str] = ['coverage', 'lateness', 'equity', 'cost']

# Defaults per pass (épica §3.5): quality 0-100 -> MIPGap = (100 - quality)/100;
# time_limit in SECONDS here (the HTTP contract of XO uses minutes; the
# simulator calls this hundreds of times per day, so seconds are the unit).
DEFAULT_MIPGAP_BY_NAME: Dict[str, float] = {}
DEFAULT_TIME_LIMIT_BY_NAME: Dict[str, float] = {}
PROTECTED_OBJECTIVE_NAMES = frozenset(n for n, s in CATALOGUE.items() if s.protected)

# Lock tolerance between passes (épica §3.4). Gurobi defaults: ObjNAbsTol
# 1e-6, ObjNRelTol 0. XO ran with ~1e-4 relative and measured the "hueco".
# Decision 4C: exact lock on coverage, 1e-4 relative on every other pass.
DEFAULT_LOCK_ABS_TOL = 1e-6
DEFAULT_LOCK_REL_TOL = 1e-4
DEFAULT_LOCK_REL_TOL_BY_NAME: Dict[str, float] = {'coverage': 0.0}

# Global pct (épica §4.2): (1-F)*prog(main) + F/(n-1)*sum(prog(others))
MULTI_OBJ_FACTOR = 0.20
MAIN_OBJECTIVE = 'coverage'


@dataclass
class ObjectiveSetting:
    mip_gap: Optional[float] = None      # 0..1 (NOT the 0-100 quality of the front)
    time_limit: Optional[float] = None   # seconds
    lock_abs_tol: Optional[float] = None
    lock_rel_tol: Optional[float] = None

    @classmethod
    def from_quality(cls, quality: Optional[float] = None,
                     time_limit_min: Optional[float] = None) -> 'ObjectiveSetting':
        """Front contract: quality 0-100 and time limit in minutes."""
        gap = None if quality is None else max(0.0, (100.0 - float(quality)) / 100.0)
        tl = None if time_limit_min is None else float(time_limit_min) * 60.0
        return cls(mip_gap=gap, time_limit=tl)


def resolve_order(order: Optional[List[str]] = None) -> List[ObjectiveSpec]:
    """
    Pass order = explicit list (highest priority first) or DEFAULT_ORDER, minus
    the objectives switched off by ``DISABLE_HIER_<NAME>``. Priorities are
    reassigned by position so a reordered list is honoured literally.
    """
    names = list(order) if order else list(DEFAULT_ORDER)
    unknown = [n for n in names if n not in CATALOGUE]
    if unknown:
        raise ValueError(f"Unknown objective(s) {unknown}. Known: {list(CATALOGUE)}")
    specs = []
    n = len(names)
    for pos, name in enumerate(names):
        if disabled('HIER_' + name):
            continue
        base = CATALOGUE[name]
        specs.append(ObjectiveSpec(
            name=base.name, priority=(n - pos) * 10, label=base.label, sense=base.sense,
            protected=base.protected, description=base.description, coef=base.coef,
            exists=base.exists,
        ))
    return specs


def resolve_settings(specs: List[ObjectiveSpec],
                     overrides: Optional[Dict[str, ObjectiveSetting]] = None
                     ) -> Dict[str, ObjectiveSetting]:
    """Defaults by name first, then request overrides; protected names reject mip_gap."""
    out: Dict[str, ObjectiveSetting] = {}
    overrides = overrides or {}
    for s in specs:
        st = ObjectiveSetting(
            mip_gap=DEFAULT_MIPGAP_BY_NAME.get(s.name),
            time_limit=DEFAULT_TIME_LIMIT_BY_NAME.get(s.name),
            lock_abs_tol=DEFAULT_LOCK_ABS_TOL,
            lock_rel_tol=DEFAULT_LOCK_REL_TOL_BY_NAME.get(s.name, DEFAULT_LOCK_REL_TOL),
        )
        ov = overrides.get(s.name)
        if ov is not None:
            if ov.mip_gap is not None:
                if s.protected:
                    raise ValueError(f"Objective '{s.name}' is protected: mip_gap not allowed")
                st.mip_gap = ov.mip_gap
            if ov.time_limit is not None:
                st.time_limit = ov.time_limit
            if ov.lock_abs_tol is not None:
                st.lock_abs_tol = ov.lock_abs_tol
            if ov.lock_rel_tol is not None:
                st.lock_rel_tol = ov.lock_rel_tol
        out[s.name] = st
    return out
