"""
Environment gates for the hierarchical solver (épica §8.1).

Every behaviour change lives behind a gate. The XO trap to avoid: reading
gates by truthiness makes ``DISABLE_X=0`` *disable* the feature. Here
``flag(name)`` treats "", "0", "false", "no", "off" as OFF and anything else
as ON, so ``DISABLE_X=0`` means "not disabled".
"""
from __future__ import annotations

import os

_OFF = {'', '0', 'false', 'no', 'off', 'none'}


def flag(name: str, default: bool = False) -> bool:
    """True when the env var is set to a truthy value ('1', 'true', 'yes', 'on', ...)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _OFF


def disabled(feature: str) -> bool:
    """Shorthand for ``flag('DISABLE_' + feature)``."""
    return flag('DISABLE_' + feature.upper())


def env_float(name: str, default: float | None = None) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return float(raw)
    except ValueError:
        return default
