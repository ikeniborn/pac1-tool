"""COPRO backend — wraps dspy.teleprompt.COPRO behind OptimizerProtocol."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import dspy
from dspy.teleprompt import COPRO

from agent.optimization.base import CompileResult


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _scalar(metric: Callable):
    """COPRO expects a scalar metric. Unwrap dspy.Prediction → score."""
    def _wrapped(ex, pr, trace=None):
        result = metric(ex, pr, trace)
        return result.score if hasattr(result, "score") else float(result)
    return _wrapped


class CoproBackend:
    name = "copro"

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
        dspy.configure(lm=task_lm, adapter=adapter)
        teleprompter = COPRO(
            prompt_model=prompt_lm,
            metric=_scalar(metric),
            breadth=_int_env("COPRO_BREADTH", 4),
            depth=_int_env("COPRO_DEPTH", 2),
            init_temperature=_float_env("COPRO_TEMPERATURE", 0.9),
        )
        compiled = teleprompter.compile(
            program,
            trainset=trainset,
            eval_kwargs={"num_threads": threads, "display_progress": True, "display_table": 0},
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        compiled.save(str(save_path))
        return CompileResult(compiled=compiled, pareto_programs=None, stats={})
