"""Budget resolution for GEPA: auto preset + optional fine-grained override."""
from __future__ import annotations

import os


_VALID_AUTO = {"light", "medium", "heavy"}
_VALID_OVERRIDE_KEYS = {"max_full_evals", "max_metric_calls"}


def resolve_budget() -> dict:
    """Return kwargs to pass to dspy.GEPA(...) for budget control.

    Priority:
      1. GEPA_BUDGET_OVERRIDE='key=N' — fine-grained.
      2. GEPA_AUTO=light|medium|heavy — preset.
      3. Default: auto=light.
    """
    override = (os.environ.get("GEPA_BUDGET_OVERRIDE") or "").strip()
    if override and "=" in override:
        k, _, v = override.partition("=")
        k = k.strip()
        try:
            n = int(v.strip())
        except ValueError:
            n = 0
        if k in _VALID_OVERRIDE_KEYS and n > 0:
            return {k: n}

    level = (os.environ.get("GEPA_AUTO", "light") or "light").strip().lower()
    if level not in _VALID_AUTO:
        level = "light"
    return {"auto": level}
