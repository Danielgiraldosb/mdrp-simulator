"""
Hierarchical (lexicographic) multi-objective dispatch model for the MDRP,
built with Gurobi following the framework ported from XO Scheduler
(Epicas/mdrp-marco-de-optimizacion.md).

Public surface:
  HierContext           build + optimize one dispatch round, artifacts, fingerprint
  CATALOGUE / DEFAULT_ORDER / ObjectiveSetting   objectives and per-pass settings
  round_to_json / round_from_json                 offline reproduction (diag tools)
"""
from .objectives import CATALOGUE, DEFAULT_ORDER, ObjectiveSetting, ObjectiveSpec, resolve_order
from .context import HierContext, round_to_json, round_from_json

__all__ = ['HierContext', 'CATALOGUE', 'DEFAULT_ORDER', 'ObjectiveSetting', 'ObjectiveSpec',
           'resolve_order', 'round_to_json', 'round_from_json']
