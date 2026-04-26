"""Optimizer protocol shared between COPRO and GEPA backends."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


class BackendError(RuntimeError):
    """Raised when a backend cannot run (missing dep, invalid config, etc.)."""


@dataclass
class CompileResult:
    """Return value of OptimizerProtocol.compile()."""
    compiled: Any  # dspy.Module
    pareto_programs: list[Any] | None = None  # list[dspy.Module] (GEPA only)
    stats: dict = field(default_factory=dict)


class OptimizerProtocol(Protocol):
    name: str  # "copro" | "gepa"

    def compile(
        self,
        program: Any,
        trainset: list,
        metric: Callable,
        save_path: Path,
        log_label: str,
        *,
        task_lm: Any,
        prompt_lm: Any,
        adapter: Any,
        threads: int,
    ) -> CompileResult: ...
