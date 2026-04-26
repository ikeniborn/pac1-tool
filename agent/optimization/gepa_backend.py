"""GEPA backend — Genetic-Pareto Reflective Prompt Evolution."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import dspy

from agent.optimization.base import BackendError, CompileResult
from agent.optimization.budget import resolve_budget


try:
    from dspy.teleprompt import GEPA as _GEPA
except ImportError:  # pragma: no cover
    _GEPA = None


def _parse_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _parse_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _split_trainset(
    trainset: list,
    val_fraction: float,
    min_for_split: int,
) -> tuple[list, list | None, str, dict]:
    """Split trainset deterministically: last val_fraction → val, rest → train.

    Returns (train, val, log_msg, payload).
    val is None when split is skipped (trainset too small or invalid fraction).
    """
    n = len(trainset)
    if n >= min_for_split and 0 < val_fraction < 1:
        cut = max(1, int(n * (1 - val_fraction)))
        train, val = trainset[:cut], trainset[cut:]
        msg = (
            f"trainset={len(train)}, valset={len(val)}"
            f" (last {int(val_fraction * 100)}%)"
        )
        payload: dict = {
            "trainset_size": len(train),
            "valset_size": len(val),
            "fraction": val_fraction,
        }
    else:
        train, val = trainset, None
        reason = "below_min" if n < min_for_split else "fraction_invalid"
        msg = f"split skipped ({reason}, n={n}); trainset-as-valset"
        payload = {
            "trainset_size": n,
            "valset_size": 0,
            "skipped_reason": reason,
            "fraction": val_fraction,
        }
    return train, val, msg, payload


def _model_supports_logprobs(model_id: str | None) -> bool:
    """Return True if models.json says this model's provider can return logprobs."""
    if not model_id:
        return False
    try:
        from pathlib import Path as _P
        import json as _json
        models_path = _P(__file__).parent.parent.parent / "models.json"
        raw = _json.loads(models_path.read_text())
        cfg = raw.get(model_id, {})
        provider = cfg.get("provider", "")
        if isinstance(provider, str) and provider in raw.get("_profiles", {}):
            provider = raw["_profiles"][provider].get("provider", "")
        return provider in {"openrouter", "ollama"}
    except Exception:
        return False


class GepaBackend:
    name = "gepa"

    def _maybe_confidence_adapter(self, program, fallback, task_lm):
        """Return ConfidenceAdapter only when target is classifier AND model supports logprobs."""
        # Detect classifier by signature class name to avoid coupling to the import.
        sig = getattr(program, "signature", None)
        sig_name = getattr(sig, "__name__", "") or type(sig).__name__
        if "ClassifyTask" not in sig_name:
            return fallback
        model_id = getattr(task_lm, "model", None) or getattr(task_lm, "_model", None)
        if not _model_supports_logprobs(model_id):
            return fallback
        try:
            from dspy import ConfidenceAdapter  # type: ignore
            return ConfidenceAdapter()
        except Exception as exc:
            print(f"[optimize] ConfidenceAdapter unavailable: {exc} — using fallback adapter")
            return fallback

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
        emit: "Callable[[str, dict], None] | None" = None,
    ) -> CompileResult:
        if _GEPA is None:
            raise BackendError(
                "GEPA not available. Install with: uv add 'dspy-ai[gepa]' or 'gepa'."
            )

        val_fraction = _parse_float_env("GEPA_VAL_FRACTION", 0.2)
        min_for_split = _parse_int_env("GEPA_MIN_TRAINSET_FOR_SPLIT", 20)
        train, val, split_msg, split_payload = _split_trainset(
            trainset, val_fraction, min_for_split
        )
        print(f"[optimize] gepa: {split_msg}")
        if emit is not None:
            split_payload = {"target": log_label, **split_payload}
            emit("split", split_payload)

        budget_kwargs = resolve_budget()
        eff_adapter = self._maybe_confidence_adapter(program, adapter, task_lm)
        dspy.configure(lm=task_lm, adapter=eff_adapter)

        def _gepa_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
            # GEPA passes 5 args; our metrics use the 3-arg form.
            return metric(gold, pred, trace)

        teleprompter = _GEPA(
            metric=_gepa_metric,
            reflection_lm=prompt_lm,
            num_threads=threads,
            track_stats=True,
            **budget_kwargs,
        )
        compiled = teleprompter.compile(program, trainset=train, valset=val)

        save_path.parent.mkdir(parents=True, exist_ok=True)
        compiled.save(str(save_path))

        pareto = self._extract_pareto(compiled, teleprompter)
        index = self._save_pareto(pareto, save_path)

        return CompileResult(
            compiled=compiled,
            pareto_programs=pareto or None,
            stats={"budget": budget_kwargs, "pareto_count": len(pareto), "pareto_index": index},
        )

    def _extract_pareto(self, compiled, teleprompter) -> list:
        """Return list of dspy.Module instances on the Pareto frontier.

        GEPA stores them on the teleprompter after compile (attribute name confirmed
        in Task 9 step 1). Falls back to [] if attribute is missing.
        """
        for attr in ("pareto_programs", "pareto_frontier", "frontier"):
            progs = getattr(teleprompter, attr, None)
            if progs:
                return list(progs)
        return []

    def _save_pareto(self, programs: list, save_path: Path) -> dict:
        """Save Pareto programs to a sibling directory; return index dict."""
        if not programs:
            return {}
        pareto_dir = save_path.parent / (save_path.stem + "_pareto")
        pareto_dir.mkdir(parents=True, exist_ok=True)
        index: dict = {}
        for i, prog in enumerate(programs):
            try:
                p = pareto_dir / f"{i}.json"
                prog.save(str(p))
                score = getattr(prog, "_pareto_score", None)
                index[str(i)] = {"path": str(p.relative_to(save_path.parent)),
                                 "score": score}
            except Exception as exc:  # fail-open: a single bad program shouldn't lose others
                index[str(i)] = {"error": str(exc)}
        (pareto_dir / "index.json").write_text(
            __import__("json").dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return index
