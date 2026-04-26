"""DSPy optimizer backends (COPRO + GEPA) with shared infrastructure."""
from __future__ import annotations

import os

from agent.optimization.base import OptimizerProtocol, CompileResult, BackendError
from agent.optimization.copro_backend import CoproBackend
from agent.optimization.gepa_backend import GepaBackend
from agent.optimization.logger import OptimizeLogger


_VALID = {"copro", "gepa"}


def select_backend(target_label: str) -> OptimizerProtocol:
    """Return backend for the given target.

    target_label may be plain ('builder') or slashed ('builder/global', 'builder/email').
    The first segment is used to resolve OPTIMIZER_<UPPER>; falls back to
    OPTIMIZER_DEFAULT (default 'copro').
    """
    head = target_label.split("/", 1)[0].upper()
    raw = (
        os.environ.get(f"OPTIMIZER_{head}")
        or os.environ.get("OPTIMIZER_DEFAULT", "copro")
    )
    kind = raw.strip().lower()
    if kind not in _VALID:
        kind = "copro"
    return GepaBackend() if kind == "gepa" else CoproBackend()


__all__ = [
    "OptimizerProtocol", "CompileResult", "BackendError", "OptimizeLogger",
    "CoproBackend", "GepaBackend", "select_backend",
]
