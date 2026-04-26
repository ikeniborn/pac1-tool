"""DSPy COPRO optimizer for prompt_builder and evaluator (Variant 4).

Loads real examples from data/dspy_examples.jsonl (accumulated by main.py runs).
If fewer than 30 real examples are available, supplements with cold-start synthetic
examples from data/dspy_synthetic.jsonl.

Saves compiled programs to:
  data/prompt_builder_program.json  — loaded by agent/prompt_builder.py at startup
  data/evaluator_program.json       — loaded by agent/evaluator.py at startup

Optimization run logs are appended to:
  data/optimize_runs.jsonl          — one JSON event per line (run_start, lm_call, metric_eval, run_end)

Usage:
    uv run python scripts/optimize_prompts.py --target builder
    uv run python scripts/optimize_prompts.py --target evaluator
    uv run python scripts/optimize_prompts.py --target all

Environment requirements (same as main.py — loaded from .env / .secrets):
    MODEL_DEFAULT or MODEL_CLASSIFIER — used as optimizer LM
    ANTHROPIC_API_KEY / OPENROUTER_API_KEY / OLLAMA_BASE_URL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env / .secrets before any agent imports
# ---------------------------------------------------------------------------

def _load_file(path: "str | Path") -> None:
    try:
        for line in Path(path).read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                k = k.strip()
                v = v.partition("#")[0].strip()
                os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass


_BASE = Path(__file__).resolve().parent.parent
_load_file(_BASE / ".env")
_load_file(_BASE / ".secrets")
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))

import dspy
from dspy.teleprompt import COPRO

from agent.optimization.logger import OptimizeLogger
from agent.optimization.metrics import builder_metric, evaluator_metric, classifier_metric
from agent.dspy_lm import DispatchLM


def _scalar(metric):
    """Adapt a Prediction-returning metric into a scalar metric for COPRO."""
    def _wrapped(ex, pr, trace=None):
        return metric(ex, pr, trace).score
    return _wrapped
from agent.dspy_examples import get_trainset, get_eval_trainset, get_classifier_trainset
from agent.dispatch import anthropic_client as _ant_client, openrouter_client as _or_client
from agent.prompt_builder import PromptAddendum
from agent.evaluator import EvaluateCompletion
from agent.classifier import ClassifyTask

_BUILDER_PROGRAM_PATH = _BASE / "data" / "prompt_builder_program.json"
_EVAL_PROGRAM_PATH = _BASE / "data" / "evaluator_program.json"
_CLASSIFIER_PROGRAM_PATH = _BASE / "data" / "classifier_program.json"
_OPTIMIZE_LOG_PATH = _BASE / "data" / "optimize_runs.jsonl"
_OPTIMIZE_ERROR_LOG_PATH = _BASE / "data" / "dspy_errors.jsonl"


def _type_program_path(task_type: str) -> Path:
    """Return path for a per-task_type builder program file."""
    return _BASE / "data" / f"prompt_builder_{task_type}_program.json"


def _eval_type_program_path(task_type: str) -> Path:
    """Return path for a per-task_type evaluator program file."""
    return _BASE / "data" / f"evaluator_{task_type}_program.json"


# ---------------------------------------------------------------------------
# COPRO hyper-parameters — overridable via env
# ---------------------------------------------------------------------------

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

_COPRO_BREADTH     = _int_env("COPRO_BREADTH", 4)
_COPRO_DEPTH       = _int_env("COPRO_DEPTH", 2)
_COPRO_TEMPERATURE = _float_env("COPRO_TEMPERATURE", 0.9)
_COPRO_THREADS     = _int_env("COPRO_THREADS", 1)
_COPRO_MIN_PER_TYPE = _int_env("COPRO_MIN_PER_TYPE", 3)
_COPRO_PROMPT_MAX_TOKENS = _int_env("COPRO_PROMPT_MAX_TOKENS", 2000)


# ---------------------------------------------------------------------------
# Optimization run logger
# ---------------------------------------------------------------------------

# Module-level logger instance, initialised in main()
_logger: OptimizeLogger | None = None


def _emit(event: str, data: dict) -> None:
    if _logger is not None:
        _logger.emit(event, data)


def _emit_error(target: str, exc: BaseException, extra: dict | None = None) -> None:
    if _logger is not None:
        _logger.emit_error(target, exc, extra)


# ---------------------------------------------------------------------------
# Logging LM wrapper
# ---------------------------------------------------------------------------

class _LoggingDispatchLM(DispatchLM):
    """DispatchLM subclass that logs every forward() call to OptimizeLogger."""

    def __init__(self, model: str, cfg: dict, max_tokens: int, target: str, json_mode: bool = True) -> None:
        super().__init__(model, cfg, max_tokens, json_mode=json_mode)
        self._target = target
        self._call_num = 0
        self._call_num_lock = threading.Lock()

    def forward(self, prompt=None, messages=None, **kwargs):
        with self._call_num_lock:
            self._call_num += 1
            call_num = self._call_num

        # Reconstruct user message preview for logging (same logic as parent)
        user_parts: list[str] = []
        system = ""
        for m in messages or []:
            role = m.get("role", "")
            content = m.get("content", "") or ""
            if role == "system":
                system = content
            elif role in ("user", "human"):
                user_parts.append(content)
        user_msg = prompt or "\n\n".join(user_parts)

        t0 = time.monotonic()
        response = super().forward(prompt=prompt, messages=messages, **kwargs)
        elapsed = round(time.monotonic() - t0, 3)

        tok = self._last_tokens
        resp_text = response.choices[0].message.content if response.choices else ""

        _emit("lm_call", {
            "target": self._target,
            "call_num": call_num,
            "elapsed_s": elapsed,
            "input_tokens": tok.get("input", 0),
            "output_tokens": tok.get("output", 0),
            "system_len": len(system),
            "user_len": len(user_msg),
            "response_len": len(resp_text),
            "response_preview": resp_text[:300],
        })
        return response


# ---------------------------------------------------------------------------
# Model setup
# ---------------------------------------------------------------------------

def _get_optimizer_model() -> tuple[str, dict]:
    """Return (model_id, cfg) for the optimizer LM.

    Prefers MODEL_CLASSIFIER (fast, low-temperature) → MODEL_DEFAULT fallback.
    Loads full config from models.json.
    """
    models_path = _BASE / "models.json"
    with models_path.open() as fh:
        models_raw: dict = json.load(fh)

    profiles: dict = models_raw.get("_profiles", {})

    def _resolve(cfg: dict) -> dict:
        resolved = {}
        for k, v in cfg.items():
            if isinstance(v, str) and v in profiles:
                resolved[k] = profiles[v]
            else:
                resolved[k] = v
        return resolved

    all_cfgs = {k: _resolve(v) for k, v in models_raw.items() if not k.startswith("_")}

    model = (
        os.environ.get("MODEL_OPTIMIZER")
        or os.environ.get("MODEL_CLASSIFIER")
        or os.environ.get("MODEL_DEFAULT")
        or next(iter(all_cfgs), None)
    )
    if not model:
        raise RuntimeError("No model configured. Set MODEL_DEFAULT or MODEL_OPTIMIZER in .env")
    cfg = all_cfgs.get(model, {})
    return model, cfg


# ---------------------------------------------------------------------------
# Training set builders
# ---------------------------------------------------------------------------

def _builder_trainset(
    min_score: float = 0.7,
    task_type: str | None = None,
    max_per_type: int | None = None,
) -> list[dspy.Example]:
    """Build DSPy Examples for prompt_builder optimisation.

    Args:
        min_score: Minimum task score to include.
        task_type: If given, return only examples for that task type.
        max_per_type: Last N examples per task_type (guaranteed representation).
    """
    raw = get_trainset(min_score=min_score, max_per_type=max_per_type)
    examples = []
    for ex in raw:
        tt = ex.get("task_type", "default")
        if task_type is not None and tt != task_type:
            continue
        examples.append(
            dspy.Example(
                task_type=tt,
                task_text=ex.get("task_text", ""),
                graph_context=ex.get("graph_context", ""),
                addendum=ex.get("addendum", ""),
                score=ex.get("score", 1.0),
            ).with_inputs("task_type", "task_text", "graph_context")
        )
    return examples


def _builder_task_types(min_score: float = 0.7, max_per_type: int | None = None) -> dict[str, int]:
    """Return {task_type: count} for all types present in the trainset."""
    raw = get_trainset(min_score=min_score, max_per_type=max_per_type)
    counts: dict[str, int] = {}
    for ex in raw:
        tt = ex.get("task_type", "default")
        counts[tt] = counts.get(tt, 0) + 1
    return counts


def _evaluator_task_types(max_per_type: int | None = None) -> dict[str, int]:
    """Return {task_type: count} for all types present in the eval trainset."""
    real = get_eval_trainset(max_per_class=max_per_type)
    counts: dict[str, int] = {}
    for ex in real:
        tt = ex.get("task_type", "default")
        counts[tt] = counts.get(tt, 0) + 1
    return counts


def _classifier_trainset(min_score: float = 0.8, max_per_type: int | None = None) -> list[dspy.Example]:
    """Build DSPy Examples for classifier optimisation from builder examples."""
    raw = get_classifier_trainset(min_score=min_score, max_per_type=max_per_type)
    return [
        dspy.Example(
            task_text=ex["task_text"],
            vault_hint=ex.get("vault_hint", ""),
            task_type=ex["task_type"],
        ).with_inputs("task_text", "vault_hint")
        for ex in raw
    ]


def _evaluator_trainset(task_type: str | None = None, max_per_type: int | None = None) -> list[dspy.Example]:
    """Build DSPy Examples for evaluator optimisation.

    Uses real examples from data/dspy_eval_examples.jsonl if ≥ EVAL_THRESHOLD
    are available (collected automatically by main.py runs).
    Falls back to 4 hardcoded bootstrap examples otherwise.

    max_per_type: if set, applies balanced yes/no window (global pass only).
    Ground truth: expected_approved_str = "yes" if score == 1.0 else "no".
    """
    real = get_eval_trainset(max_per_class=max_per_type if task_type is None else None)
    if task_type is not None:
        real = [ex for ex in real if ex.get("task_type", "default") == task_type]
    if real:
        label = f"type={task_type!r}" if task_type else "global"
        print(f"[optimize] Evaluator trainset ({label}): {len(real)} real examples from data/dspy_eval_examples.jsonl")
        return [
            dspy.Example(
                task_text=ex["task_text"],
                task_type=ex["task_type"],
                proposed_outcome=ex["proposed_outcome"],
                agent_message=ex["agent_message"],
                done_ops=ex["done_ops"],
                completed_steps=ex["completed_steps"],
                skepticism_level=ex["skepticism_level"],
                reference_patterns=ex.get("reference_patterns", "(none)"),
                graph_insights=ex.get("graph_insights", "(none)"),
                approved_str=ex["expected_approved_str"],
                issues_str="",
                correction_hint="",
            ).with_inputs("task_text", "task_type", "proposed_outcome", "agent_message",
                          "done_ops", "completed_steps", "skepticism_level",
                          "reference_patterns", "graph_insights")
            for ex in real
        ]

    if task_type is not None:
        return []
    print("[optimize] Evaluator: using hardcoded bootstrap examples (run main.py to collect real ones)")
    # Bootstrap fallback: 2 approved + 2 rejected
    return [
        dspy.Example(
            task_text="Send an email to John Smith about the project update",
            task_type="email",
            proposed_outcome="OUTCOME_OK",
            agent_message="Email sent to john@example.com",
            done_ops="- WRITTEN: /outbox/5.json",
            completed_steps="- wrote outbox/5.json",
            skepticism_level="mid",
            reference_patterns="(none)",
            graph_insights="(none)",
            approved_str="yes",
            issues_str="",
            correction_hint="",
        ).with_inputs("task_text", "task_type", "proposed_outcome", "agent_message",
                      "done_ops", "completed_steps", "skepticism_level",
                      "reference_patterns", "graph_insights"),
        dspy.Example(
            task_text="What is the email of Maria Schulz?",
            task_type="lookup",
            proposed_outcome="OUTCOME_OK",
            agent_message="maria@acme.com",
            done_ops="(none)",
            completed_steps="- read contacts/cont_007.json",
            skepticism_level="mid",
            reference_patterns="(none)",
            graph_insights="(none)",
            approved_str="yes",
            issues_str="",
            correction_hint="",
        ).with_inputs("task_text", "task_type", "proposed_outcome", "agent_message",
                      "done_ops", "completed_steps", "skepticism_level",
                      "reference_patterns", "graph_insights"),
        dspy.Example(
            task_text="Delete all processed items from the archive folder",
            task_type="default",
            proposed_outcome="OUTCOME_OK",
            agent_message="Done",
            done_ops="(none)",
            completed_steps="- listed archive/",
            skepticism_level="mid",
            reference_patterns="(none)",
            graph_insights="(none)",
            approved_str="no",
            issues_str="OUTCOME_OK but task required file deletions and done_ops is empty",
            correction_hint="OUTCOME_NONE_CLARIFICATION",
        ).with_inputs("task_text", "task_type", "proposed_outcome", "agent_message",
                      "done_ops", "completed_steps", "skepticism_level",
                      "reference_patterns", "graph_insights"),
        dspy.Example(
            task_text="Pr...",
            task_type="inbox",
            proposed_outcome="OUTCOME_OK",
            agent_message="processed",
            done_ops="(none)",
            completed_steps="",
            skepticism_level="mid",
            reference_patterns="(none)",
            graph_insights="(none)",
            approved_str="no",
            issues_str="Task text is truncated/garbled — should be CLARIFICATION",
            correction_hint="OUTCOME_NONE_CLARIFICATION",
        ).with_inputs("task_text", "task_type", "proposed_outcome", "agent_message",
                      "done_ops", "completed_steps", "skepticism_level",
                      "reference_patterns", "graph_insights"),
    ]


# ---------------------------------------------------------------------------
# Optimisation runners
# ---------------------------------------------------------------------------

def _run_copro_builder(
    model: str,
    cfg: dict,
    trainset: list,
    save_path: Path,
    log_label: str,
) -> None:
    """Run one COPRO pass on trainset and save to save_path."""
    _emit("run_start", {
        "target": log_label,
        "model": model,
        "trainset_size": len(trainset),
        "copro": {
            "breadth": _COPRO_BREADTH,
            "depth": _COPRO_DEPTH,
            "temperature": _COPRO_TEMPERATURE,
            "threads": _COPRO_THREADS,
        },
    })

    _ollama_only = _ant_client is None and _or_client is None
    _adapter = dspy.ChatAdapter() if _ollama_only else dspy.JSONAdapter()
    lm = _LoggingDispatchLM(model, cfg, max_tokens=400, target=log_label, json_mode=not _ollama_only)
    prompt_lm = _LoggingDispatchLM(
        model, cfg, max_tokens=_COPRO_PROMPT_MAX_TOKENS,
        target=f"{log_label}/meta", json_mode=not _ollama_only,
    )
    dspy.configure(lm=lm, adapter=_adapter)

    program = dspy.Predict(PromptAddendum)
    teleprompter = COPRO(
        prompt_model=prompt_lm,
        metric=_scalar(builder_metric),
        breadth=_COPRO_BREADTH,
        depth=_COPRO_DEPTH,
        init_temperature=_COPRO_TEMPERATURE,
    )

    t0 = time.monotonic()
    status = "ok"
    try:
        compiled = teleprompter.compile(
            program,
            trainset=trainset,
            eval_kwargs={"num_threads": _COPRO_THREADS, "display_progress": True, "display_table": 0},
        )
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as exc:
        status = f"error: {exc}"
        _emit_error(log_label, exc, {
            "model": model,
            "trainset_size": len(trainset),
            "lm_call_num": lm._call_num,
            "prompt_lm_call_num": prompt_lm._call_num,
        })
        raise
    finally:
        _emit("run_end", {
            "target": log_label,
            "duration_s": round(time.monotonic() - t0, 2),
            "total_lm_calls": lm._call_num,
            "status": status,
        })

    save_path.parent.mkdir(exist_ok=True)
    compiled.save(str(save_path))
    print(f"[optimize] Builder program saved → {save_path}")


def optimize_builder(model: str, cfg: dict, min_score: float = 0.8, max_per_type: int | None = None) -> None:
    """Run COPRO on PromptAddendum: global pass + per-task_type passes.

    Global pass uses all examples and saves to prompt_builder_program.json.
    Per-type passes save to prompt_builder_{task_type}_program.json for each
    task type with at least COPRO_MIN_PER_TYPE examples.
    """
    all_trainset = _builder_trainset(min_score=min_score, max_per_type=max_per_type)
    if not all_trainset:
        print("[optimize] No training examples found. Run main.py first to collect examples.")
        sys.exit(1)

    print(f"[optimize] Builder trainset: {len(all_trainset)} examples total, model: {model}")

    # Global pass — fallback for task types without enough data
    _run_copro_builder(model, cfg, all_trainset, _BUILDER_PROGRAM_PATH, "builder/global")

    # Per-type passes
    type_counts = _builder_task_types(min_score=min_score, max_per_type=max_per_type)
    eligible = {tt: n for tt, n in type_counts.items() if n >= _COPRO_MIN_PER_TYPE}
    skipped = {tt: n for tt, n in type_counts.items() if n < _COPRO_MIN_PER_TYPE}

    if skipped:
        print(f"[optimize] Per-type skipped (< {_COPRO_MIN_PER_TYPE} examples): "
              + ", ".join(f"{tt}({n})" for tt, n in skipped.items()))

    failed: list[tuple[str, str]] = []
    for tt, n in sorted(eligible.items()):
        print(f"[optimize] Per-type: {tt!r} — {n} examples")
        type_trainset = _builder_trainset(min_score=min_score, task_type=tt, max_per_type=max_per_type)
        try:
            _run_copro_builder(model, cfg, type_trainset, _type_program_path(tt), f"builder/{tt}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"[optimize] Per-type {tt!r} FAILED — {msg}. Continuing with next type.")
            failed.append((tt, msg))

    if failed:
        print(f"[optimize] Per-type failures: {len(failed)} — "
              + ", ".join(f"{tt} ({msg.split(':', 1)[0]})" for tt, msg in failed))


def _run_copro_evaluator(
    model: str,
    cfg: dict,
    trainset: list,
    save_path: Path,
    log_label: str,
) -> None:
    """Run one COPRO pass on trainset and save to save_path."""
    _emit("run_start", {
        "target": log_label,
        "model": model,
        "trainset_size": len(trainset),
        "copro": {
            "breadth": _COPRO_BREADTH,
            "depth": _COPRO_DEPTH,
            "temperature": _COPRO_TEMPERATURE,
            "threads": _COPRO_THREADS,
        },
    })

    _ollama_only = _ant_client is None and _or_client is None
    _adapter = dspy.ChatAdapter() if _ollama_only else dspy.JSONAdapter()
    lm = _LoggingDispatchLM(model, cfg, max_tokens=600, target=log_label, json_mode=not _ollama_only)
    prompt_lm = _LoggingDispatchLM(
        model, cfg, max_tokens=_COPRO_PROMPT_MAX_TOKENS,
        target=f"{log_label}/meta", json_mode=not _ollama_only,
    )
    dspy.configure(lm=lm, adapter=_adapter)

    program = dspy.ChainOfThought(EvaluateCompletion)
    teleprompter = COPRO(
        prompt_model=prompt_lm,
        metric=_scalar(evaluator_metric),
        breadth=_COPRO_BREADTH,
        depth=_COPRO_DEPTH,
        init_temperature=_COPRO_TEMPERATURE,
    )

    t0 = time.monotonic()
    status = "ok"
    try:
        compiled = teleprompter.compile(
            program,
            trainset=trainset,
            eval_kwargs={"num_threads": _COPRO_THREADS, "display_progress": True, "display_table": 0},
        )
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as exc:
        status = f"error: {exc}"
        _emit_error(log_label, exc, {
            "model": model,
            "trainset_size": len(trainset),
            "lm_call_num": lm._call_num,
            "prompt_lm_call_num": prompt_lm._call_num,
        })
        raise
    finally:
        _emit("run_end", {
            "target": log_label,
            "duration_s": round(time.monotonic() - t0, 2),
            "total_lm_calls": lm._call_num,
            "status": status,
        })

    save_path.parent.mkdir(exist_ok=True)
    compiled.save(str(save_path))
    print(f"[optimize] Evaluator program saved → {save_path}")


def optimize_evaluator(model: str, cfg: dict, max_per_type: int | None = None) -> None:
    """Run COPRO on EvaluateCompletion: global pass + per-task_type passes.

    Global pass uses all examples and saves to evaluator_program.json.
    Per-type passes save to evaluator_{task_type}_program.json for each
    task type with at least COPRO_MIN_PER_TYPE examples.
    """
    print(f"[optimize] Model: {model}")

    # Global pass — balanced yes/no window applied here only
    global_trainset = _evaluator_trainset(max_per_type=max_per_type)
    if not global_trainset:
        print("[optimize] No evaluator training examples found. Run main.py first.")
        sys.exit(1)
    _run_copro_evaluator(model, cfg, global_trainset, _EVAL_PROGRAM_PATH, "evaluator/global")

    # Per-type passes — no window (per-type counts are already small)
    type_counts = _evaluator_task_types(max_per_type=max_per_type)
    eligible = {tt: n for tt, n in type_counts.items() if n >= _COPRO_MIN_PER_TYPE}
    skipped = {tt: n for tt, n in type_counts.items() if n < _COPRO_MIN_PER_TYPE}

    if skipped:
        print(f"[optimize] Per-type skipped (< {_COPRO_MIN_PER_TYPE} examples): "
              + ", ".join(f"{tt}({n})" for tt, n in skipped.items()))

    failed: list[tuple[str, str]] = []
    for tt, n in sorted(eligible.items()):
        print(f"[optimize] Per-type evaluator: {tt!r} — {n} examples")
        type_trainset = _evaluator_trainset(task_type=tt)
        try:
            _run_copro_evaluator(model, cfg, type_trainset, _eval_type_program_path(tt), f"evaluator/{tt}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"[optimize] Per-type evaluator {tt!r} FAILED — {msg}. Continuing with next type.")
            failed.append((tt, msg))

    if failed:
        print(f"[optimize] Per-type evaluator failures: {len(failed)} — "
              + ", ".join(f"{tt} ({msg.split(':', 1)[0]})" for tt, msg in failed))


def _run_copro_classifier(
    model: str,
    cfg: dict,
    trainset: list,
    save_path: Path,
    log_label: str,
) -> None:
    """Run one COPRO pass on classifier trainset and save to save_path."""
    _emit("run_start", {
        "target": log_label,
        "model": model,
        "trainset_size": len(trainset),
        "copro": {
            "breadth": _COPRO_BREADTH,
            "depth": _COPRO_DEPTH,
            "temperature": _COPRO_TEMPERATURE,
            "threads": _COPRO_THREADS,
        },
    })

    _ollama_only = _ant_client is None and _or_client is None
    _adapter = dspy.ChatAdapter() if _ollama_only else dspy.JSONAdapter()
    lm = _LoggingDispatchLM(model, cfg, max_tokens=64, target=log_label, json_mode=not _ollama_only)
    prompt_lm = _LoggingDispatchLM(
        model, cfg, max_tokens=_COPRO_PROMPT_MAX_TOKENS,
        target=f"{log_label}/meta", json_mode=not _ollama_only,
    )
    dspy.configure(lm=lm, adapter=_adapter)

    program = dspy.ChainOfThought(ClassifyTask)
    teleprompter = COPRO(
        prompt_model=prompt_lm,
        metric=_scalar(classifier_metric),
        breadth=_COPRO_BREADTH,
        depth=_COPRO_DEPTH,
        init_temperature=_COPRO_TEMPERATURE,
    )

    t0 = time.monotonic()
    status = "ok"
    try:
        compiled = teleprompter.compile(
            program,
            trainset=trainset,
            eval_kwargs={"num_threads": _COPRO_THREADS, "display_progress": True, "display_table": 0},
        )
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as exc:
        status = f"error: {exc}"
        _emit_error(log_label, exc, {
            "model": model,
            "trainset_size": len(trainset),
            "lm_call_num": lm._call_num,
            "prompt_lm_call_num": prompt_lm._call_num,
        })
        raise
    finally:
        _emit("run_end", {
            "target": log_label,
            "duration_s": round(time.monotonic() - t0, 2),
            "total_lm_calls": lm._call_num,
            "status": status,
        })

    save_path.parent.mkdir(exist_ok=True)
    compiled.save(str(save_path))
    print(f"[optimize] Classifier program saved → {save_path}")


def optimize_classifier(model: str, cfg: dict, min_score: float = 0.8, max_per_type: int | None = None) -> None:
    """Run COPRO on ClassifyTask: single global pass (per-type not applicable for classifiers)."""
    trainset = _classifier_trainset(min_score=min_score, max_per_type=max_per_type)
    if not trainset:
        print("[optimize] No classifier training examples found. Run main.py first to collect examples.")
        sys.exit(1)

    print(f"[optimize] Classifier trainset: {len(trainset)} examples, model: {model}")
    _run_copro_classifier(model, cfg, trainset, _CLASSIFIER_PROGRAM_PATH, "classifier/global")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    global _logger

    parser = argparse.ArgumentParser(
        description="DSPy COPRO optimizer for pac1-py prompt_builder and evaluator."
    )
    parser.add_argument(
        "--target",
        choices=["builder", "evaluator", "classifier", "all"],
        default="all",
        help="Which program to optimise (default: all)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.8,
        help="Minimum task score to include real examples (default: 0.8)",
    )
    parser.add_argument(
        "--max-per-type",
        type=int,
        default=None,
        dest="max_per_type",
        help="Last N examples per task type (builder/classifier) or per class (evaluator yes/no). (default: all)",
    )
    args = parser.parse_args()

    _logger = OptimizeLogger(_OPTIMIZE_LOG_PATH, _OPTIMIZE_ERROR_LOG_PATH)
    print(f"[optimize] Logging to {_OPTIMIZE_LOG_PATH}")
    print(f"[optimize] Errors   → {_OPTIMIZE_ERROR_LOG_PATH}")

    try:
        model, cfg = _get_optimizer_model()

        if args.target in ("builder", "all"):
            optimize_builder(model, cfg, min_score=args.min_score, max_per_type=args.max_per_type)

        if args.target in ("evaluator", "all"):
            optimize_evaluator(model, cfg, max_per_type=args.max_per_type)

        if args.target in ("classifier", "all"):
            optimize_classifier(model, cfg, min_score=args.min_score, max_per_type=args.max_per_type)

        print("[optimize] Done.")
    except KeyboardInterrupt:
        print("\n[optimize] Interrupted by user.")
        sys.exit(130)
    finally:
        _logger.close()


if __name__ == "__main__":
    main()
