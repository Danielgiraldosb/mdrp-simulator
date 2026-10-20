"""
HierPolicy -- the simulator adapter for the hierarchical Gurobi model (hier/).

Same contract as every other policy (policies.Policy):
  assign(state) -> [(courier_id, [order_ids in delivery sequence], pay_offer)]

Each rolling-horizon round builds ONE HierContext (candidates shared with
Greedy/FairGreedy/ILP through routing.py), solves the lexicographic
hierarchy cfg.hier_order (default coverage > lateness > equity > cost) and
returns the chosen routes. Pay is the instance's flat pay_per_order times the
number of orders, like the other policies.

Falls back to GreedyPolicy when gurobipy is missing or a round raises.
Per-round artifacts (épica §6) are written only when cfg.hier_write_artifacts
is set (hundreds of rounds per day otherwise); the last context is kept in
``self.last`` so a caller can inspect pass stats after a run.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from policies import Policy, GreedyPolicy

logger = logging.getLogger(__name__)


def _try_import_gurobi():
    try:
        import gurobipy  # noqa: F401
        return True
    except ImportError:
        return False


_ENV = None


def _shared_env():
    """One Gurobi environment per process (never disposed): batch runs create
    many policies, and env churn plus per-round model churn is what the solver
    tolerates worst."""
    global _ENV
    if _ENV is None:
        import gurobipy as gp
        _ENV = gp.Env(params={'OutputFlag': 0})
    return _ENV


class HierPolicy(Policy):
    def __init__(self, cfg: Config, base_greedy: Optional[Policy] = None):
        super().__init__(cfg)
        self._greedy = base_greedy or GreedyPolicy(pay_per_order=cfg.pay_per_order, cfg=cfg)
        self._ok = _try_import_gurobi()
        self._env = None
        self.last = None
        self.rounds: List[Dict[str, Any]] = []     # compact per-round record (pass table + indicators)
        if not self._ok:
            logger.warning("gurobipy not found -- HierPolicy falls back to GreedyPolicy")
            return
        self._env = _shared_env()
        from hier.objectives import resolve_order
        self._order = [s.name for s in resolve_order(getattr(cfg, 'hier_order', None))]

    def assign(self, state: Dict[str, Any]) -> List[Tuple[int, List[int], float]]:
        if not self._ok:
            return self._greedy.assign(state)
        couriers = [c for c in state['L_t'].values() if c.is_available]
        orders = list(state['O_t'].values())
        if not couriers or not orders:
            return []
        from hier.context import HierContext
        cfg = self.cfg
        ctx = HierContext(couriers, orders, cfg, state['time'],
                          order=self._order, top_k=getattr(cfg, 'hier_top_k', 25),
                          env=self._env, seed=getattr(cfg, 'seed', None),
                          run_id=f"t{int(state['time']):05d}", compute_iis=False)
        try:
            ctx.configure().optimize()
            sol = ctx.solution
            if self.last is not None:
                self.last.dispose()          # keep only the most recent model alive (safe dispose)
            self.last = ctx
            self.rounds.append({
                'time': state['time'],
                'indicators': ctx.indicators(),
                'passes': [{k: p[k] for k in ('name', 'value', 'end_reason', 'solutions', 'nodes')}
                           for p in ctx.pass_table()],
                'solve_s': ctx.solve_s,
                'candidates': len(ctx.candidates),
            })
            if getattr(cfg, 'hier_write_artifacts', False):
                ctx.write_artifacts(getattr(cfg, 'hier_out_dir', 'output/hier'))
            return sol
        except Exception as exc:
            logger.warning(f"Hier solver error ({exc}), falling back to greedy for this round")
            ctx.dispose()
            return self._greedy.assign(state)
