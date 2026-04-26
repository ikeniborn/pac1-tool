"""GEPA backend — Genetic-Pareto Reflective Prompt Evolution."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import dspy

from agent.optimization.base import BackendError, CompileResult
from agent.optimization.budget import resolve_budget


try:
    from dspy.teleprompt import GEPA as _GEPA
except ImportError:  # pragma: no cover
    _GEPA = None


class GepaBackend:
    name = "gepa"

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
    ) -> CompileResult:
        if _GEPA is None:
            raise BackendError(
                "GEPA not available. Install with: uv add 'dspy-ai[gepa]' or 'gepa'."
            )

        budget_kwargs = resolve_budget()
        dspy.configure(lm=task_lm, adapter=adapter)

        teleprompter = _GEPA(
            metric=metric,
            reflection_lm=prompt_lm,
            num_threads=threads,
            track_stats=True,
            **budget_kwargs,
        )
        compiled = teleprompter.compile(program, trainset=trainset)

        save_path.parent.mkdir(parents=True, exist_ok=True)
        compiled.save(str(save_path))

        return CompileResult(
            compiled=compiled,
            pareto_programs=None,  # filled in Task 9
            stats={"budget": budget_kwargs},
        )
