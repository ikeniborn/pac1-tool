# GEPA Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Внедрить GEPA как альтернативный DSPy-оптимизатор рядом с COPRO для трёх цепочек (`prompt_builder`, `evaluator`, `classifier`) с env-driven per-target переключением, детерминированным feedback и опциональным ConfidenceAdapter для classifier.

**Architecture:** Новый пакет `agent/optimization/` с adapter-протоколом `OptimizerProtocol` и двумя бэкендами (`CoproBackend`, `GepaBackend`). `scripts/optimize_prompts.py` сжимается до CLI + диспатчера. Метрики возвращают `dspy.Prediction(score, feedback)`; feedback строится по правилам без доп LLM-вызовов.

**Tech Stack:** Python 3.12, DSPy ≥2.5 (с extra `[gepa]`), pytest, pydantic.

**Spec source:** `docs/superpowers/specs/2026-04-26-gepa-integration-design.md`

---

## File structure

**Новые файлы:**
- `agent/optimization/__init__.py` — re-exports
- `agent/optimization/base.py` — `OptimizerProtocol`, `CompileResult`, `BackendError`
- `agent/optimization/logger.py` — `OptimizeLogger` (перенос из `scripts/optimize_prompts.py`)
- `agent/optimization/feedback.py` — `build_builder_feedback`, `build_evaluator_feedback`, `build_classifier_feedback`
- `agent/optimization/metrics.py` — `builder_metric`, `evaluator_metric`, `classifier_metric` (возвращают `dspy.Prediction`)
- `agent/optimization/budget.py` — `resolve_budget()`
- `agent/optimization/copro_backend.py` — `CoproBackend`
- `agent/optimization/gepa_backend.py` — `GepaBackend`
- `tests/test_optimization_feedback.py`
- `tests/test_optimization_backend_select.py`
- `tests/test_optimization_budget.py`
- `tests/test_optimization_smoke.py` (slow-marked)

**Модифицируемые файлы:**
- `scripts/optimize_prompts.py` — заменяет внутренние `_run_copro_*` на универсальный диспатчер
- `agent/dspy_examples.py` — `record_example()` принимает `stall_detected`, `write_scope_violations`
- `main.py` — пробрасывает новые поля в `record_example()`
- `agent/dispatch.py` — в `openrouter_complete`/`ollama_complete` пробрасывает `logprobs=True` при наличии флага
- `pyproject.toml` — добавить extra `dspy-ai[gepa]`
- `.env.example` — новые env-переменные
- `CLAUDE.md` — раздел "Optimization Workflow"
- `docs/architecture/04-dspy-optimization.md` — обновить под двухбэкендную архитектуру

---

## Task 1: Scaffold optimization package + protocol + logger move

**Files:**
- Create: `agent/optimization/__init__.py`
- Create: `agent/optimization/base.py`
- Create: `agent/optimization/logger.py`
- Modify: `scripts/optimize_prompts.py:113-205` (удалить класс `OptimizeLogger`, импортировать из `agent.optimization.logger`)

- [ ] **Step 1: Create empty package marker**

```python
# agent/optimization/__init__.py
"""DSPy optimizer backends (COPRO + GEPA) with shared infrastructure."""
from agent.optimization.base import OptimizerProtocol, CompileResult, BackendError
from agent.optimization.logger import OptimizeLogger

__all__ = ["OptimizerProtocol", "CompileResult", "BackendError", "OptimizeLogger"]
```

- [ ] **Step 2: Create base.py with protocol and result types**

```python
# agent/optimization/base.py
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
```

- [ ] **Step 3: Move OptimizeLogger to logger.py**

Move the entire `class OptimizeLogger` (lines 113-190 of scripts/optimize_prompts.py) into `agent/optimization/logger.py` verbatim, prepending:

```python
"""Append-only JSONL logger for optimization runs."""
from __future__ import annotations

import json
import threading
import traceback as _traceback
from datetime import datetime, timezone
from pathlib import Path
```

Keep the class body 100% identical (signatures of `__init__`, `emit`, `emit_error`, `close`).

- [ ] **Step 4: Update scripts/optimize_prompts.py to import from new location**

Remove the `class OptimizeLogger` definition (lines 113-190). Add import near top (after the `import dspy` block):

```python
from agent.optimization.logger import OptimizeLogger
```

Remove now-unused imports `threading`, `traceback as _traceback` from `scripts/optimize_prompts.py` only if no other code uses them (re-grep before removing). Module-level `_logger` and helper functions `_emit`, `_emit_error` stay where they are.

- [ ] **Step 5: Verify imports work**

Run: `uv run python -c "from agent.optimization import OptimizeLogger, OptimizerProtocol, CompileResult, BackendError; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Run existing test suite to verify no regression**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same pass/fail as before (smoke).

- [ ] **Step 7: Commit**

```bash
git add agent/optimization/__init__.py agent/optimization/base.py agent/optimization/logger.py scripts/optimize_prompts.py
git commit -m "refactor(optimization): scaffold package + extract OptimizeLogger"
```

---

## Task 2: Move metrics into metrics.py (no feedback yet)

**Files:**
- Create: `agent/optimization/metrics.py`
- Modify: `scripts/optimize_prompts.py` — заменить три внутренние метрики на импорт

- [ ] **Step 1: Create metrics.py with the three metric functions**

```python
# agent/optimization/metrics.py
"""Metrics for the three DSPy targets.

All metrics return `dspy.Prediction(score, feedback)`. COPRO consumes only the
scalar via a wrapper in CoproBackend; GEPA uses both fields.

Feedback is intentionally empty in this module — it is filled in by feedback.py
once that module is wired in (see Task 3).
"""
from __future__ import annotations

import dspy


def builder_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Score addendum: 1.0 if source score >= 0.8 and bullet_count >= 2; 0.5 sparse; 0.0 if source bad."""
    source_score: float = getattr(example, "score", 1.0)
    if source_score < 0.8:
        score = 0.0
    else:
        addendum: str = getattr(prediction, "addendum", "") or ""
        bullet_count = sum(1 for line in addendum.splitlines() if line.strip().startswith("-"))
        score = 0.5 if bullet_count < 2 else 1.0
    return dspy.Prediction(score=score, feedback="")


def evaluator_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Exact-match between predicted approved_str and expected."""
    expected: str = getattr(example, "approved_str", "yes")
    predicted: str = (getattr(prediction, "approved_str", "") or "").strip().lower()
    score = 1.0 if predicted == expected.lower() else 0.0
    return dspy.Prediction(score=score, feedback="")


def classifier_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Exact-match between predicted task_type and expected."""
    expected: str = getattr(example, "task_type", "default")
    predicted: str = (getattr(prediction, "task_type", "") or "").strip().lower()
    score = 1.0 if predicted == expected else 0.0
    return dspy.Prediction(score=score, feedback="")
```

- [ ] **Step 2: Replace inline metrics in scripts/optimize_prompts.py**

Delete the existing `_builder_metric`, `_evaluator_metric`, `_classifier_metric` functions (lines ~301-353). Add import below the new logger import:

```python
from agent.optimization.metrics import builder_metric, evaluator_metric, classifier_metric
```

In every `teleprompter = COPRO(metric=_builder_metric, ...)` invocation, replace `_builder_metric` with a thin wrapper that extracts `.score` (COPRO can't read Prediction):

```python
def _scalar(metric):
    def _wrapped(ex, pr, trace=None):
        return metric(ex, pr, trace).score
    return _wrapped
```

Place `_scalar` near the top of the file. Use `metric=_scalar(builder_metric)` etc. in all three `_run_copro_*` functions.

The `_emit("metric_eval", ...)` calls inside the old metric bodies are deleted — moving to a logging wrapper is out of scope; we now log at backend level only.

- [ ] **Step 3: Run optimizer end-to-end on a tiny trainset to confirm parity**

Run: `OPTIMIZER_DEFAULT=copro uv run python scripts/optimize_prompts.py --target classifier --max-per-type 2`

Expected: completes without error, writes `data/classifier_program.json` (overwrites existing). No new env-var support yet — `OPTIMIZER_DEFAULT` is a no-op at this step.

- [ ] **Step 4: Run existing test suite**

Run: `uv run python -m pytest tests/test_classifier.py tests/test_evaluator.py -q`
Expected: PASS (same as before — these tests don't depend on the optimizer).

- [ ] **Step 5: Commit**

```bash
git add agent/optimization/metrics.py scripts/optimize_prompts.py
git commit -m "refactor(optimization): move metrics into metrics.py with Prediction return type"
```

---

## Task 3: feedback.py + unit tests (TDD)

**Files:**
- Create: `tests/test_optimization_feedback.py`
- Create: `agent/optimization/feedback.py`
- Modify: `agent/optimization/metrics.py` — wire feedback builders in

### 3.1 Builder feedback

- [ ] **Step 1: Write failing tests for build_builder_feedback**

```python
# tests/test_optimization_feedback.py
"""Unit tests for deterministic feedback builders."""
from agent.optimization.feedback import (
    build_builder_feedback,
    build_evaluator_feedback,
    build_classifier_feedback,
)


def _ex(**kw):
    """Tiny SimpleNamespace-like shim — feedback builders read attributes."""
    class _E: pass
    e = _E()
    for k, v in kw.items():
        setattr(e, k, v)
    return e


# -------- builder --------

def test_builder_score_one_with_three_bullets():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b\n- c")
    fb = build_builder_feedback(ex, pred, score=1.0)
    assert "score=1.0" in fb
    assert "≥3" in fb or "3-5" in fb


def test_builder_score_one_with_one_bullet():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a")
    fb = build_builder_feedback(ex, pred, score=1.0)
    assert "1 bullets" in fb or "only 1" in fb
    assert "3-5" in fb


def test_builder_failed_with_stall():
    ex = _ex(task_type="email", score=0.0, stall_detected=True, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "stall" in fb.lower()
    assert "anti-loop" in fb.lower()


def test_builder_failed_with_write_scope():
    ex = _ex(task_type="email", score=0.0, stall_detected=False, write_scope_violations=True)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "write" in fb.lower()
    assert "outbox" in fb.lower()


def test_builder_failed_generic():
    ex = _ex(task_type="lookup", score=0.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="- a\n- b")
    fb = build_builder_feedback(ex, pred, score=0.0)
    assert "task_type=lookup" in fb


def test_builder_no_bullets():
    ex = _ex(task_type="email", score=1.0, stall_detected=False, write_scope_violations=False)
    pred = _ex(addendum="some plain text")
    fb = build_builder_feedback(ex, pred, score=0.5)
    assert "bullet" in fb.lower()
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `uv run python -m pytest tests/test_optimization_feedback.py -v`
Expected: FAIL with `ModuleNotFoundError: agent.optimization.feedback`.

- [ ] **Step 3: Implement build_builder_feedback**

Create `agent/optimization/feedback.py`:

```python
"""Deterministic feedback builders for GEPA metrics.

Each builder is a pure function that produces a short (~400 char) string
describing why the prediction succeeded or failed, using only fields available
on the trace example. No LLM calls.
"""
from __future__ import annotations


_TASK_TYPE_HINTS = {
    "email":    "email tasks must end in /outbox/",
    "inbox":    "inbox tasks require classification before write",
    "queue":    "queue tasks process pending items in order",
    "lookup":   "lookup tasks are read-only — no writes",
    "capture":  "capture tasks save to /capture/",
    "crm":      "crm tasks update /contacts/ records",
    "temporal": "temporal tasks require date/time anchoring",
    "preject":  "preject tasks set up project scaffolding",
    "think":    "think tasks return reasoning, no side effects",
    "distill":  "distill tasks produce concise summaries",
    "default":  "follow vault discovery and write-scope rules",
}


def build_builder_feedback(example, prediction, score: float) -> str:
    """Return short feedback for prompt_builder metric."""
    task_type = getattr(example, "task_type", "default")
    addendum = (getattr(prediction, "addendum", "") or "")
    bullet_count = sum(1 for line in addendum.splitlines() if line.strip().startswith("-"))
    source_score = float(getattr(example, "score", 1.0))
    stall = bool(getattr(example, "stall_detected", False))
    scope_bad = bool(getattr(example, "write_scope_violations", False))

    if bullet_count == 0:
        return "Addendum has no bullet structure — bullets ('- ...') are required."

    if source_score >= 0.8:
        if bullet_count >= 3:
            return f"OK: addendum led to score=1.0; keep bullet density ≥3."
        return (f"Score=1.0 but addendum has only {bullet_count} bullets — "
                f"terse may regress on harder cases; aim for 3-5.")

    # source_score < 0.8 — failure case
    if stall:
        return (f"Task failed (stall detected). Addendum did not surface "
                f"anti-loop guidance for task_type={task_type}.")
    if scope_bad:
        return (f"Task failed: agent wrote outside the allowed scope for "
                f"task_type={task_type}. Addendum should encode the write-scope rule "
                f"({_TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS['default'])}).")
    hint = _TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS["default"])
    return (f"Task failed. Addendum produced {bullet_count} bullets for "
            f"task_type={task_type}; consider mentioning: {hint}.")


def build_evaluator_feedback(example, prediction, score: float) -> str:
    """Return short feedback for evaluator metric."""
    expected = (getattr(example, "approved_str", "yes") or "").strip().lower()
    predicted = (getattr(prediction, "approved_str", "") or "").strip().lower()
    task_type = getattr(example, "task_type", "default")
    proposed = getattr(example, "proposed_outcome", "")
    done_ops = (getattr(example, "done_ops", "") or "").strip()
    task_text = getattr(example, "task_text", "") or ""

    if predicted == expected:
        return f"Correct: {expected}."

    refusal_set = {"OUTCOME_NONE_CLARIFICATION", "OUTCOME_NONE_UNSUPPORTED", "OUTCOME_DENIED_SECURITY"}
    if predicted == "yes" and expected == "no":
        if proposed == "OUTCOME_OK" and (not done_ops or done_ops == "(none)"):
            return (f"False approve: agent claimed OUTCOME_OK without any write/delete ops. "
                    f"Tighten the 'side-effects required' check for task_type={task_type}.")
        if len(task_text) < 30 or task_text.endswith("..."):
            return ("False approve: task_text was ambiguous/truncated and agent answered "
                    "without clarification. Should have rejected → CLARIFICATION.")
        return f"False approve for task_type={task_type}; outcome did not match the task constraint."

    if predicted == "no" and expected == "yes":
        ops_short = done_ops[:80] if done_ops else "(no ops)"
        if proposed in refusal_set:
            return (f"False reject: refusal {proposed} was actually correct "
                    f"(benchmark score=1.0). Refusal-acceptance rules should be more lenient.")
        return (f"False reject: outcome was actually correct (benchmark score=1.0). "
                f"Avoid over-skepticism on task_type={task_type}; the {ops_short} were sufficient.")

    return f"Mismatch: predicted={predicted}, expected={expected}, task_type={task_type}."


_CONFUSED_PAIRS = {
    ("lookup", "email"): ("Misclassified: task implies sending an email "
                          "(action verb 'send/write/email'); lookup is read-only. "
                          "Hint: presence of recipient name → email."),
    ("default", "inbox"): ("Misclassified: task references /inbox/ items implicitly via "
                           "'process'/'classify'/'sort'; default is too generic."),
    ("think", "temporal"): ("Misclassified: temporal markers ('next week', 'before Friday', "
                            "explicit date in task_text); think is for open-ended reasoning."),
}


def build_classifier_feedback(example, prediction, score: float) -> str:
    """Return short feedback for classifier metric."""
    expected = (getattr(example, "task_type", "default") or "").strip().lower()
    predicted = (getattr(prediction, "task_type", "") or "").strip().lower()
    task_text = (getattr(example, "task_text", "") or "")[:120]

    if predicted == expected:
        return f"Correct: {expected}."

    pair_msg = _CONFUSED_PAIRS.get((predicted, expected))
    if pair_msg:
        return pair_msg

    return (f"Misclassified: predicted={predicted}, expected={expected}. "
            f"Task text: {task_text!r}.")
```

- [ ] **Step 4: Run tests — expect 6 PASS**

Run: `uv run python -m pytest tests/test_optimization_feedback.py -v -k builder`
Expected: 6 passed.

- [ ] **Step 5: Add evaluator and classifier tests**

Append to `tests/test_optimization_feedback.py`:

```python
# -------- evaluator --------

def test_evaluator_correct():
    ex = _ex(approved_str="yes", task_type="email", proposed_outcome="OUTCOME_OK",
             done_ops="- WRITTEN: /outbox/x.json", task_text="Send mail to John")
    pred = _ex(approved_str="yes")
    assert build_evaluator_feedback(ex, pred, 1.0) == "Correct: yes."


def test_evaluator_false_approve_no_ops():
    ex = _ex(approved_str="no", task_type="default", proposed_outcome="OUTCOME_OK",
             done_ops="(none)", task_text="Delete archive items")
    pred = _ex(approved_str="yes")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "False approve" in fb
    assert "side-effects" in fb


def test_evaluator_false_approve_truncated():
    ex = _ex(approved_str="no", task_type="inbox", proposed_outcome="OUTCOME_OK",
             done_ops="- read inbox/1.json", task_text="Pr...")
    pred = _ex(approved_str="yes")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "ambiguous" in fb or "truncated" in fb.lower()


def test_evaluator_false_reject():
    ex = _ex(approved_str="yes", task_type="lookup", proposed_outcome="OUTCOME_OK",
             done_ops="- read contacts/cont_007.json", task_text="What is Maria's email?")
    pred = _ex(approved_str="no")
    fb = build_evaluator_feedback(ex, pred, 0.0)
    assert "False reject" in fb
    assert "lookup" in fb


# -------- classifier --------

def test_classifier_correct():
    ex = _ex(task_type="email", task_text="Send X to Y")
    pred = _ex(task_type="email")
    assert build_classifier_feedback(ex, pred, 1.0) == "Correct: email."


def test_classifier_confused_pair_email_vs_lookup():
    ex = _ex(task_type="email", task_text="Send mail to John")
    pred = _ex(task_type="lookup")
    fb = build_classifier_feedback(ex, pred, 0.0)
    assert "lookup is read-only" in fb


def test_classifier_generic_mismatch():
    ex = _ex(task_type="capture", task_text="capture this idea")
    pred = _ex(task_type="email")
    fb = build_classifier_feedback(ex, pred, 0.0)
    assert "predicted=email" in fb
    assert "expected=capture" in fb
```

- [ ] **Step 6: Run all feedback tests**

Run: `uv run python -m pytest tests/test_optimization_feedback.py -v`
Expected: 13 passed.

- [ ] **Step 7: Wire feedback builders into metrics.py**

Edit `agent/optimization/metrics.py`. Replace `feedback=""` literals with calls:

```python
from agent.optimization.feedback import (
    build_builder_feedback, build_evaluator_feedback, build_classifier_feedback,
)


def builder_metric(example, prediction, trace=None) -> dspy.Prediction:
    source_score: float = getattr(example, "score", 1.0)
    if source_score < 0.8:
        score = 0.0
    else:
        addendum: str = getattr(prediction, "addendum", "") or ""
        bullet_count = sum(1 for line in addendum.splitlines() if line.strip().startswith("-"))
        score = 0.5 if bullet_count < 2 else 1.0
    return dspy.Prediction(
        score=score,
        feedback=build_builder_feedback(example, prediction, score),
    )


def evaluator_metric(example, prediction, trace=None) -> dspy.Prediction:
    expected: str = getattr(example, "approved_str", "yes")
    predicted: str = (getattr(prediction, "approved_str", "") or "").strip().lower()
    score = 1.0 if predicted == expected.lower() else 0.0
    return dspy.Prediction(
        score=score,
        feedback=build_evaluator_feedback(example, prediction, score),
    )


def classifier_metric(example, prediction, trace=None) -> dspy.Prediction:
    expected: str = getattr(example, "task_type", "default")
    predicted: str = (getattr(prediction, "task_type", "") or "").strip().lower()
    score = 1.0 if predicted == expected else 0.0
    return dspy.Prediction(
        score=score,
        feedback=build_classifier_feedback(example, prediction, score),
    )
```

- [ ] **Step 8: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same pass/fail as before + 13 new passes.

- [ ] **Step 9: Commit**

```bash
git add agent/optimization/feedback.py agent/optimization/metrics.py tests/test_optimization_feedback.py
git commit -m "feat(optimization): deterministic feedback builders for GEPA metrics"
```

---

## Task 4: Add stall_detected/write_scope_violations to record_example

**Files:**
- Modify: `agent/dspy_examples.py:27-60` (`record_example` signature + JSONL entry)
- Modify: `main.py` around line 301 (pass new fields)

- [ ] **Step 1: Extend record_example signature**

Edit `agent/dspy_examples.py`. Update `record_example`:

```python
def record_example(
    task_text: str,
    task_type: str,
    addendum: str,
    score: float,
    graph_context: str = "",
    stall_detected: bool = False,
    write_scope_violations: bool = False,
) -> None:
    """Append one (task, addendum, score) tuple to the JSONL example log.

    stall_detected / write_scope_violations are read by the GEPA feedback
    builder to produce targeted addendum-improvement hints.
    """
    _DATA.mkdir(parents=True, exist_ok=True)
    entry = {
        "task_text": task_text,
        "task_type": task_type,
        "graph_context": graph_context,
        "addendum": addendum,
        "score": score,
        "stall_detected": stall_detected,
        "write_scope_violations": write_scope_violations,
    }
    with _EXAMPLES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # rest unchanged
    count = _count_examples()
    if count == _THRESHOLD:
        print(
            f"[dspy] {_THRESHOLD} real builder examples collected "
            "→ run: uv run python scripts/optimize_prompts.py --target builder"
        )
```

- [ ] **Step 2: Update main.py to pass the new fields**

Find the `_record_dspy_example(...)` call near `main.py:301`. Update it:

```python
_record_dspy_example(
    task_text=trial.instruction,
    task_type=token_stats.get("task_type", "default"),
    addendum=token_stats["builder_addendum"],
    score=_score_f,
    graph_context=token_stats.get("graph_context", ""),
    stall_detected=bool(token_stats.get("stall_hints")),
    write_scope_violations=bool(token_stats.get("write_scope_blocks")),
)
```

`stall_hints` already exists in `token_stats` (loop.py:855). `write_scope_blocks` may not — verify by grepping; if absent, default to False is fine for now and a follow-up adds it. Run:

Run: `grep -n "write_scope_blocks\|st\.write_scope" agent/loop.py`
If no result: keep `bool(token_stats.get("write_scope_blocks"))` — it returns False, feedback gracefully degrades to generic.

- [ ] **Step 3: Update _builder_trainset loader to surface fields on Example**

Edit `scripts/optimize_prompts.py` `_builder_trainset` function (around lines 359-386). Add the two fields when constructing `dspy.Example`:

```python
examples.append(
    dspy.Example(
        task_type=tt,
        task_text=ex.get("task_text", ""),
        graph_context=ex.get("graph_context", ""),
        addendum=ex.get("addendum", ""),
        score=ex.get("score", 1.0),
        stall_detected=ex.get("stall_detected", False),
        write_scope_violations=ex.get("write_scope_violations", False),
    ).with_inputs("task_type", "task_text", "graph_context")
)
```

- [ ] **Step 4: Smoke test — record one example, read it back**

Run:

```bash
uv run python -c "
from agent.dspy_examples import record_example, load_examples
import os, pathlib, tempfile
# tmpdir to avoid polluting real data
record_example('test task', 'email', '- a\n- b\n- c', 1.0, stall_detected=True)
ex = load_examples(min_score=0.0)[-1]
assert ex.get('stall_detected') is True, ex
assert ex.get('write_scope_violations') is False, ex
print('ok')
"
```

Expected: `ok` printed. Then revert the appended row:

```bash
# Remove the last line we just added (it's a real-data file)
head -n -1 data/dspy_examples.jsonl > data/dspy_examples.jsonl.tmp && mv data/dspy_examples.jsonl.tmp data/dspy_examples.jsonl
```

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 3.

- [ ] **Step 6: Commit**

```bash
git add agent/dspy_examples.py main.py scripts/optimize_prompts.py
git commit -m "feat(dspy): record stall_detected and write_scope_violations on builder examples"
```

---

## Task 5: copro_backend.py — refactor existing code

**Files:**
- Create: `agent/optimization/copro_backend.py`
- Modify: `scripts/optimize_prompts.py` — remove inline `_run_copro_*`, use backend

- [ ] **Step 1: Create copro_backend.py**

```python
# agent/optimization/copro_backend.py
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
```

- [ ] **Step 2: Refactor scripts/optimize_prompts.py to use the backend**

Replace the three `_run_copro_builder`, `_run_copro_evaluator`, `_run_copro_classifier` functions with a single helper at module level:

```python
from agent.optimization.copro_backend import CoproBackend


def _run_target(
    program_factory,
    trainset: list,
    metric,
    save_path: Path,
    log_label: str,
    *,
    model: str,
    cfg: dict,
    task_max_tokens: int,
) -> None:
    """Universal runner: pick backend, compile, save."""
    _emit("run_start", {
        "target": log_label,
        "model": model,
        "trainset_size": len(trainset),
    })

    _ollama_only = _ant_client is None and _or_client is None
    adapter = dspy.ChatAdapter() if _ollama_only else dspy.JSONAdapter()
    task_lm = _LoggingDispatchLM(model, cfg, max_tokens=task_max_tokens, target=log_label,
                                 json_mode=not _ollama_only)
    prompt_lm = _LoggingDispatchLM(model, cfg, max_tokens=_COPRO_PROMPT_MAX_TOKENS,
                                   target=f"{log_label}/meta", json_mode=not _ollama_only)

    backend = CoproBackend()  # Task 8 will replace this with _select_backend(target)

    t0 = time.monotonic()
    status = "ok"
    try:
        result = backend.compile(
            program_factory(),
            trainset, metric, save_path, log_label,
            task_lm=task_lm, prompt_lm=prompt_lm, adapter=adapter, threads=_COPRO_THREADS,
        )
    except KeyboardInterrupt:
        status = "interrupted"
        raise
    except Exception as exc:
        status = f"error: {exc}"
        _emit_error(log_label, exc, {
            "model": model, "trainset_size": len(trainset),
            "lm_call_num": task_lm._call_num,
            "prompt_lm_call_num": prompt_lm._call_num,
        })
        raise
    finally:
        _emit("run_end", {
            "target": log_label,
            "duration_s": round(time.monotonic() - t0, 2),
            "total_lm_calls": task_lm._call_num,
            "status": status,
        })

    print(f"[optimize] {log_label} program saved → {save_path}")
```

Update `optimize_builder`/`optimize_evaluator`/`optimize_classifier` to call `_run_target` instead of the deleted `_run_copro_*`:

```python
def optimize_builder(model, cfg, min_score=0.8, max_per_type=None):
    all_trainset = _builder_trainset(min_score=min_score, max_per_type=max_per_type)
    if not all_trainset:
        print("[optimize] No training examples found. Run main.py first.")
        sys.exit(1)
    print(f"[optimize] Builder trainset: {len(all_trainset)} examples, model: {model}")

    _run_target(
        lambda: dspy.Predict(PromptAddendum),
        all_trainset, builder_metric,
        _BUILDER_PROGRAM_PATH, "builder/global",
        model=model, cfg=cfg, task_max_tokens=400,
    )

    type_counts = _builder_task_types(min_score=min_score, max_per_type=max_per_type)
    eligible = {tt: n for tt, n in type_counts.items() if n >= _COPRO_MIN_PER_TYPE}
    skipped = {tt: n for tt, n in type_counts.items() if n < _COPRO_MIN_PER_TYPE}
    if skipped:
        print(f"[optimize] Per-type skipped (< {_COPRO_MIN_PER_TYPE}): "
              + ", ".join(f"{tt}({n})" for tt, n in skipped.items()))

    failed = []
    for tt, n in sorted(eligible.items()):
        print(f"[optimize] Per-type: {tt!r} — {n} examples")
        ts = _builder_trainset(min_score=min_score, task_type=tt, max_per_type=max_per_type)
        try:
            _run_target(
                lambda: dspy.Predict(PromptAddendum),
                ts, builder_metric,
                _type_program_path(tt), f"builder/{tt}",
                model=model, cfg=cfg, task_max_tokens=400,
            )
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[optimize] Per-type {tt!r} FAILED — {exc}")
            failed.append((tt, str(exc)))
    if failed:
        print(f"[optimize] Per-type failures: {len(failed)}")
```

Apply the same shape to `optimize_evaluator` (use `dspy.ChainOfThought(EvaluateCompletion)`, `evaluator_metric`, `task_max_tokens=600`, `_EVAL_PROGRAM_PATH`/`_eval_type_program_path`) and `optimize_classifier` (use `dspy.ChainOfThought(ClassifyTask)`, `classifier_metric`, `task_max_tokens=64`, `_CLASSIFIER_PROGRAM_PATH`).

- [ ] **Step 3: Smoke run — classifier on minimal trainset**

Run: `uv run python scripts/optimize_prompts.py --target classifier --max-per-type 2`
Expected: completes without error; `data/classifier_program.json` updated; stdout shows `[optimize] classifier/global program saved → ...`.

- [ ] **Step 4: Verify the saved program loads in agent**

Run: `uv run python -c "from agent.classifier import classify_task; print(classify_task('test task', 'AGENTS.MD: ...'))"`
Expected: prints a task type without error.

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 4.

- [ ] **Step 6: Commit**

```bash
git add agent/optimization/copro_backend.py scripts/optimize_prompts.py
git commit -m "refactor(optimization): extract CoproBackend, unify _run_target dispatcher"
```

---

## Task 6: budget.py + tests (TDD)

**Files:**
- Create: `tests/test_optimization_budget.py`
- Create: `agent/optimization/budget.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_optimization_budget.py
"""Tests for GEPA budget resolution."""
import os
import pytest

from agent.optimization.budget import resolve_budget


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("GEPA_AUTO", "GEPA_BUDGET_OVERRIDE"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_light():
    assert resolve_budget() == {"auto": "light"}


def test_auto_medium(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "medium")
    assert resolve_budget() == {"auto": "medium"}


def test_auto_heavy_uppercase(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "HEAVY")
    assert resolve_budget() == {"auto": "heavy"}


def test_override_max_full_evals(monkeypatch):
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", "max_full_evals=20")
    assert resolve_budget() == {"max_full_evals": 20}


def test_override_max_metric_calls_with_spaces(monkeypatch):
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", " max_metric_calls = 200 ")
    assert resolve_budget() == {"max_metric_calls": 200}


def test_override_beats_auto(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "heavy")
    monkeypatch.setenv("GEPA_BUDGET_OVERRIDE", "max_full_evals=5")
    assert resolve_budget() == {"max_full_evals": 5}


def test_invalid_auto_falls_back_to_light(monkeypatch):
    monkeypatch.setenv("GEPA_AUTO", "extreme")
    assert resolve_budget() == {"auto": "light"}
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `uv run python -m pytest tests/test_optimization_budget.py -v`
Expected: FAIL with ModuleNotFoundError.

- [ ] **Step 3: Implement budget.py**

```python
# agent/optimization/budget.py
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
```

- [ ] **Step 4: Run tests — expect 7 PASS**

Run: `uv run python -m pytest tests/test_optimization_budget.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/optimization/budget.py tests/test_optimization_budget.py
git commit -m "feat(optimization): GEPA budget resolution with auto preset and override"
```

---

## Task 7: gepa_backend.py basic + dspy[gepa] dep

**Files:**
- Modify: `pyproject.toml` — add extra
- Create: `agent/optimization/gepa_backend.py`

- [ ] **Step 1: Add GEPA extra dependency**

Edit `pyproject.toml`. Find the dependencies list and update the dspy entry:

```toml
"dspy-ai[gepa]>=2.5",
```

Then run:

```bash
uv sync
```

Expected: install succeeds. If GEPA is bundled as a separate optional extra and the syntax differs, run instead:

```bash
uv add gepa
```

Verify availability:

```bash
uv run python -c "from dspy.teleprompt import GEPA; print('ok')"
```
Expected: `ok`. If ImportError — fall back to `from gepa import GEPA` and import in gepa_backend.py with try/except.

- [ ] **Step 2: Implement gepa_backend.py (basic — no Pareto, no ConfidenceAdapter)**

```python
# agent/optimization/gepa_backend.py
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
```

- [ ] **Step 3: Smoke import**

Run: `uv run python -c "from agent.optimization.gepa_backend import GepaBackend; print(GepaBackend().name)"`
Expected: `gepa`.

- [ ] **Step 4: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as before (no GEPA-specific tests yet).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock agent/optimization/gepa_backend.py
git commit -m "feat(optimization): GepaBackend basic (no Pareto, no ConfidenceAdapter yet)"
```

---

## Task 8: Backend selection routing + tests

**Files:**
- Create: `tests/test_optimization_backend_select.py`
- Modify: `agent/optimization/__init__.py` — export `select_backend`
- Modify: `scripts/optimize_prompts.py` — use `select_backend`

- [ ] **Step 1: Write failing tests for select_backend**

```python
# tests/test_optimization_backend_select.py
"""Tests for env-driven backend selection."""
import pytest

from agent.optimization import select_backend


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("OPTIMIZER_DEFAULT", "OPTIMIZER_BUILDER",
              "OPTIMIZER_EVALUATOR", "OPTIMIZER_CLASSIFIER"):
        monkeypatch.delenv(k, raising=False)


def test_default_is_copro():
    assert select_backend("builder").name == "copro"


def test_optimizer_default_gepa(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "gepa")
    assert select_backend("builder").name == "gepa"
    assert select_backend("evaluator").name == "gepa"


def test_per_target_beats_default(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "gepa")
    monkeypatch.setenv("OPTIMIZER_BUILDER", "copro")
    assert select_backend("builder").name == "copro"
    assert select_backend("evaluator").name == "gepa"


def test_uppercase_value(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_BUILDER", "GEPA")
    assert select_backend("builder").name == "gepa"


def test_unknown_target_uses_default(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_DEFAULT", "copro")
    assert select_backend("misc").name == "copro"


def test_invalid_value_falls_back_to_copro(monkeypatch):
    monkeypatch.setenv("OPTIMIZER_BUILDER", "supersonic")
    assert select_backend("builder").name == "copro"


def test_target_label_with_slash(monkeypatch):
    """log_label like 'builder/global' or 'builder/email' should map to OPTIMIZER_BUILDER."""
    monkeypatch.setenv("OPTIMIZER_BUILDER", "gepa")
    assert select_backend("builder/global").name == "gepa"
    assert select_backend("builder/email").name == "gepa"
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `uv run python -m pytest tests/test_optimization_backend_select.py -v`
Expected: FAIL with `cannot import name 'select_backend'`.

- [ ] **Step 3: Implement select_backend in __init__.py**

Edit `agent/optimization/__init__.py`:

```python
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
```

- [ ] **Step 4: Run tests — expect 7 PASS**

Run: `uv run python -m pytest tests/test_optimization_backend_select.py -v`
Expected: 7 passed.

- [ ] **Step 5: Wire select_backend into _run_target**

Edit `scripts/optimize_prompts.py`. Replace the line `backend = CoproBackend()` in `_run_target` with:

```python
from agent.optimization import select_backend
backend = select_backend(log_label)
print(f"[optimize] {log_label}: backend={backend.name}")
```

(Add the `from agent.optimization import select_backend` import at the top with other optimization imports; remove the now-unused direct `CoproBackend` import.)

- [ ] **Step 6: Smoke run — verify default still uses COPRO**

Run: `uv run python scripts/optimize_prompts.py --target classifier --max-per-type 2`
Expected: stdout contains `classifier/global: backend=copro`.

- [ ] **Step 7: Smoke run — verify env switches to GEPA**

Run: `OPTIMIZER_CLASSIFIER=gepa uv run python scripts/optimize_prompts.py --target classifier --max-per-type 2`
Expected: stdout contains `classifier/global: backend=gepa`. The compile may take longer; if it succeeds and writes `data/classifier_program.json`, the basic GEPA path works. If GEPA fails on a small trainset (some optimizers require ≥N examples), bump `--max-per-type 5` and retry. If it still fails, capture the error and mark this step as a known limitation in the commit message — actual GEPA tuning is out of scope here, we only validate the wiring.

- [ ] **Step 8: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 7 + 7 new passes.

- [ ] **Step 9: Commit**

```bash
git add agent/optimization/__init__.py scripts/optimize_prompts.py tests/test_optimization_backend_select.py
git commit -m "feat(optimization): env-driven per-target backend selection"
```

---

## Task 9: Pareto frontier persistence

**Files:**
- Modify: `agent/optimization/gepa_backend.py` — implement `_extract_pareto` and `_save_pareto`

- [ ] **Step 1: Inspect GEPA compiled program structure**

Run: `OPTIMIZER_BUILDER=gepa uv run python -c "
import dspy
from dspy.teleprompt import GEPA
g = GEPA(metric=lambda *a, **k: 1.0, reflection_lm=None, auto='light', track_stats=True)
print([attr for attr in dir(g) if 'pareto' in attr.lower() or 'stat' in attr.lower()])
"`
Expected: list of attributes; look for `pareto_programs`, `stats`, `frontier`, or similar. Document actual attribute name in commit message.

- [ ] **Step 2: Implement _extract_pareto and _save_pareto**

Edit `agent/optimization/gepa_backend.py`. Add helper methods to `GepaBackend`:

```python
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
```

Update `compile()` body — after `compiled.save(str(save_path))`:

```python
        pareto = self._extract_pareto(compiled, teleprompter)
        index = self._save_pareto(pareto, save_path)

        return CompileResult(
            compiled=compiled,
            pareto_programs=pareto or None,
            stats={"budget": budget_kwargs, "pareto_count": len(pareto), "pareto_index": index},
        )
```

- [ ] **Step 3: Smoke run — verify Pareto directory is created**

Run: `OPTIMIZER_CLASSIFIER=gepa uv run python scripts/optimize_prompts.py --target classifier --max-per-type 3`
Expected: completes; `ls data/classifier_program_pareto/` shows at least `index.json` plus N `.json` files (or empty index if GEPA produced no frontier on tiny trainset — also acceptable).

Run: `cat data/classifier_program_pareto/index.json`
Expected: valid JSON dict.

- [ ] **Step 4: Smoke run — verify COPRO does NOT create Pareto dir**

Delete the dir: `rm -rf data/classifier_program_pareto`
Run: `OPTIMIZER_CLASSIFIER=copro uv run python scripts/optimize_prompts.py --target classifier --max-per-type 2`
Expected: `ls data/classifier_program_pareto 2>&1` shows "No such file or directory".

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 8.

- [ ] **Step 6: Commit**

```bash
git add agent/optimization/gepa_backend.py
git commit -m "feat(optimization): persist GEPA Pareto frontier alongside main program"
```

---

## Task 10: ConfidenceAdapter routing + dispatch.py logprobs

**Files:**
- Modify: `agent/optimization/gepa_backend.py` — `_maybe_confidence_adapter`
- Modify: `agent/dispatch.py` — pass `logprobs=True` to OpenRouter/Ollama when capability flag is set

- [ ] **Step 1: Identify provider for the optimizer model**

Edit `agent/optimization/gepa_backend.py`. Add at module level:

```python
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
```

- [ ] **Step 2: Implement _maybe_confidence_adapter**

Add to `GepaBackend`:

```python
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
```

Update `compile()` body — after `dspy.configure(lm=task_lm, adapter=adapter)` line, change to:

```python
        eff_adapter = self._maybe_confidence_adapter(program, adapter, task_lm)
        dspy.configure(lm=task_lm, adapter=eff_adapter)
```

- [ ] **Step 3: Wire logprobs flag in dispatch.py (OpenRouter)**

Open `agent/dispatch.py` and find `openrouter_complete` / OpenRouter request body construction. Locate the request payload (`{"model": ..., "messages": ..., "max_tokens": ...}`).

Add a parameter to the function signature: `logprobs: bool = False`. In the payload assembly:

```python
if logprobs:
    payload["logprobs"] = True
    payload["top_logprobs"] = 1
```

(If a parameter named `logprobs` already exists, skip.) Same change in `ollama_complete` — Ollama accepts `options.logprobs`:

```python
if logprobs:
    payload.setdefault("options", {})["logprobs"] = 1
```

- [ ] **Step 4: Plumb logprobs into DispatchLM**

Open `agent/dspy_lm.py` (or wherever `DispatchLM` lives — grep `class DispatchLM`). Add `logprobs: bool = False` to `__init__`. In the `forward` method, pass it through to the underlying client call.

- [ ] **Step 5: Plumb in scripts/optimize_prompts.py**

In `_LoggingDispatchLM`, accept `logprobs=False` and pass to super. In `_run_target`, set `logprobs=True` when `select_backend(log_label).name == "gepa"` AND `log_label.startswith("classifier")`:

```python
needs_logprobs = backend.name == "gepa" and log_label.startswith("classifier")
task_lm = _LoggingDispatchLM(model, cfg, max_tokens=task_max_tokens, target=log_label,
                             json_mode=not _ollama_only, logprobs=needs_logprobs)
```

- [ ] **Step 6: Smoke run — Anthropic model (no logprobs)**

Run: `MODEL_OPTIMIZER=claude-haiku-4-5-20251001 OPTIMIZER_CLASSIFIER=gepa uv run python scripts/optimize_prompts.py --target classifier --max-per-type 3`
Expected: completes without errors. `_maybe_confidence_adapter` returns fallback (Anthropic provider — no logprobs support). No `[optimize] ConfidenceAdapter unavailable` message.

- [ ] **Step 7: Smoke run — verify fallback path on missing ConfidenceAdapter**

If `from dspy import ConfidenceAdapter` is not available in the installed DSPy version, the `try/except` in `_maybe_confidence_adapter` should print the warning. Test by temporarily renaming the import in code (or simulate via a mock). Confirm the run still completes.

- [ ] **Step 8: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 9.

- [ ] **Step 9: Commit**

```bash
git add agent/optimization/gepa_backend.py agent/dispatch.py agent/dspy_lm.py scripts/optimize_prompts.py
git commit -m "feat(optimization): ConfidenceAdapter routing for classifier when logprobs available"
```

---

## Task 11: Smoke test (slow) — both backends compile

**Files:**
- Create: `tests/test_optimization_smoke.py`

- [ ] **Step 1: Write smoke test using DummyLM**

```python
# tests/test_optimization_smoke.py
"""Slow smoke tests: both backends compile a trivial program without errors.

Skipped by default — run with: pytest tests/test_optimization_smoke.py -m slow
"""
import pytest
import dspy

from agent.optimization import CoproBackend, GepaBackend
from agent.optimization.metrics import classifier_metric


pytestmark = pytest.mark.slow


class _ClassifySig(dspy.Signature):
    """Classify task into one of: a, b, c."""
    task_text: str = dspy.InputField()
    task_type: str = dspy.OutputField(desc="one of: a, b, c")


def _trainset():
    return [
        dspy.Example(task_text="apples are red", task_type="a").with_inputs("task_text"),
        dspy.Example(task_text="bananas are yellow", task_type="b").with_inputs("task_text"),
        dspy.Example(task_text="cherries are sweet", task_type="c").with_inputs("task_text"),
    ]


def _dummy_lm():
    """Real DummyLM only available in some DSPy versions; skip cleanly otherwise."""
    try:
        return dspy.utils.DummyLM(["a", "b", "c", "a", "b", "c"] * 20)
    except AttributeError:
        pytest.skip("dspy.utils.DummyLM unavailable in this DSPy version")


def test_copro_backend_smoke(tmp_path):
    lm = _dummy_lm()
    program = dspy.Predict(_ClassifySig)
    backend = CoproBackend()
    save_path = tmp_path / "out.json"
    result = backend.compile(
        program, _trainset(), classifier_metric, save_path, "test/copro",
        task_lm=lm, prompt_lm=lm, adapter=dspy.ChatAdapter(), threads=1,
    )
    assert save_path.exists()
    assert result.compiled is not None
    assert result.pareto_programs is None


def test_gepa_backend_smoke(tmp_path):
    pytest.importorskip("dspy.teleprompt", reason="GEPA may need extra")
    try:
        from dspy.teleprompt import GEPA  # noqa: F401
    except ImportError:
        pytest.skip("GEPA not installed")
    lm = _dummy_lm()
    program = dspy.Predict(_ClassifySig)
    backend = GepaBackend()
    save_path = tmp_path / "out.json"
    result = backend.compile(
        program, _trainset(), classifier_metric, save_path, "test/gepa",
        task_lm=lm, prompt_lm=lm, adapter=dspy.ChatAdapter(), threads=1,
    )
    assert save_path.exists()
    assert result.compiled is not None
```

- [ ] **Step 2: Register the slow marker in pyproject.toml or conftest.py**

If not already registered, append to `tests/conftest.py`:

```python
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow integration smoke tests")
```

- [ ] **Step 3: Run the smoke tests**

Run: `uv run python -m pytest tests/test_optimization_smoke.py -v -m slow`
Expected: 2 passed (or 2 skipped if DummyLM/GEPA unavailable — that's also acceptable).

- [ ] **Step 4: Run full test suite (without slow marker — default)**

Run: `uv run python -m pytest tests/ -x -q`
Expected: same as Task 10 (smoke tests are skipped without `-m slow`).

- [ ] **Step 5: Commit**

```bash
git add tests/test_optimization_smoke.py tests/conftest.py
git commit -m "test(optimization): smoke tests for both backends with DummyLM"
```

---

## Task 12: Documentation updates

**Files:**
- Modify: `.env.example`
- Modify: `CLAUDE.md` (Optimization Workflow section)
- Modify: `docs/architecture/04-dspy-optimization.md`

- [ ] **Step 1: Update .env.example**

Append at the end of `.env.example`:

```ini
# ---------------------------------------------------------------------------
# DSPy optimizer selection (gepa | copro). Per-target overrides default.
# Set to gepa to use Genetic-Pareto Reflective Prompt Evolution; copro stays
# as the legacy/baseline. Each target can be set independently for A/B.
# ---------------------------------------------------------------------------
OPTIMIZER_DEFAULT=copro
# OPTIMIZER_BUILDER=gepa
# OPTIMIZER_EVALUATOR=copro
# OPTIMIZER_CLASSIFIER=gepa

# GEPA budget — auto preset; light=≈2× COPRO baseline, heavy=≈10×
GEPA_AUTO=light
# Optional fine-grained override; e.g. "max_full_evals=30" or "max_metric_calls=400"
# GEPA_BUDGET_OVERRIDE=

# Optional: separate reflection model (default: same as MODEL_OPTIMIZER)
# MODEL_GEPA_REFLECTION=
```

- [ ] **Step 2: Update CLAUDE.md "Optimization Workflow" section**

Edit `CLAUDE.md`. Find the "Optimization Workflow" section. Replace it:

````markdown
## Optimization Workflow

PAC1-tool supports two DSPy optimizer backends — **COPRO** (legacy) and **GEPA** (Genetic-Pareto Reflective Prompt Evolution). Selection is per-target via env:

| Env | Default | Effect |
|---|---|---|
| `OPTIMIZER_DEFAULT` | `copro` | Fallback for all targets |
| `OPTIMIZER_BUILDER` | (inherits) | Override for `prompt_builder` |
| `OPTIMIZER_EVALUATOR` | (inherits) | Override for `evaluator` |
| `OPTIMIZER_CLASSIFIER` | (inherits) | Override for `classifier` |
| `GEPA_AUTO` | `light` | `light|medium|heavy` budget preset |
| `GEPA_BUDGET_OVERRIDE` | (unset) | Fine-grained: `max_full_evals=N` or `max_metric_calls=N` |

1. Collect real examples — auto-saved to `data/dspy_examples.jsonl` (with `stall_detected`/`write_scope_violations` for richer GEPA feedback):
   ```bash
   uv run python main.py
   ```

2. Run optimizer (per-target backend selection):
   ```bash
   # Default: all targets via COPRO
   uv run python scripts/optimize_prompts.py --target builder

   # Mix-and-match: GEPA for builder, COPRO for evaluator
   OPTIMIZER_BUILDER=gepa uv run python scripts/optimize_prompts.py --target all
   ```

3. Compiled programs saved to `data/{builder,evaluator,classifier}_program.json` (and per-task_type variants). GEPA additionally saves Pareto frontier to `data/<target>_program_pareto/{0..N}.json` + `index.json` (advisory; agent loads only the main program).

4. Programs are loaded at agent startup automatically.

**Migration tips:**
- A/B comparison: run twice with different `OPTIMIZER_*` settings, compare benchmark scores.
- Roll back: unset `OPTIMIZER_*=gepa`; the existing COPRO-compiled JSON keeps working.
- Logs at `data/optimize_runs.jsonl` differentiate `target=builder/global` (task LM), `/meta` (COPRO prompt LM), `/reflection` (GEPA reflection LM).
````

- [ ] **Step 3: Update docs/architecture/04-dspy-optimization.md**

Open the file, find the section describing the COPRO pipeline. Add a new subsection:

```markdown
## Two-backend architecture (since 2026-04)

`agent/optimization/` is a small package with two interchangeable optimizer backends behind a common `OptimizerProtocol`:

- `CoproBackend` — wraps `dspy.teleprompt.COPRO`; baseline.
- `GepaBackend` — wraps `dspy.teleprompt.GEPA`; reads `dspy.Prediction.feedback` from metrics, persists Pareto frontier, optionally uses `ConfidenceAdapter` for `classifier` when the task LM provider supports logprobs (OpenRouter open-weight, Ollama).

`scripts/optimize_prompts.py` resolves backend per target via `OPTIMIZER_<TARGET>` env vars (see CLAUDE.md). Metrics in `agent/optimization/metrics.py` always return `dspy.Prediction(score, feedback)`; CoproBackend extracts `.score` via a wrapper, GepaBackend uses both fields.

Feedback construction is deterministic and rule-based (`agent/optimization/feedback.py`) — no extra LLM calls. Sources:
- `score`, `addendum`, `stall_detected`, `write_scope_violations` (builder)
- `proposed_outcome`, `done_ops`, `task_text` (evaluator)
- `task_text`, `vault_hint` (classifier)

For details and motivations see `docs/superpowers/specs/2026-04-26-gepa-integration-design.md`.
```

- [ ] **Step 4: Verify docs render**

Run: `cat CLAUDE.md | grep -A 2 "Optimization Workflow"`
Expected: shows the new section header and table.

- [ ] **Step 5: Commit**

```bash
git add .env.example CLAUDE.md docs/architecture/04-dspy-optimization.md
git commit -m "docs(optimization): document COPRO/GEPA two-backend architecture and env vars"
```

---

## Task 13: Final verification

- [ ] **Step 1: Full pytest including slow**

Run: `uv run python -m pytest tests/ -v --tb=short`
Expected: all green (or known pre-existing failures only).

Run: `uv run python -m pytest tests/ -v -m slow`
Expected: 2 smoke tests pass or skip cleanly.

- [ ] **Step 2: COPRO parity check**

Run a full COPRO-only optimization and confirm output is the same shape as before:

```bash
OPTIMIZER_DEFAULT=copro uv run python scripts/optimize_prompts.py --target classifier --max-per-type 3
```
Expected: completes; `data/classifier_program.json` updated; no `*_pareto/` directory.

- [ ] **Step 3: GEPA wiring check**

```bash
OPTIMIZER_BUILDER=gepa uv run python scripts/optimize_prompts.py --target builder --max-per-type 3
```
Expected: completes; backend logs `gepa`; `data/prompt_builder_program.json` updated; possibly `data/prompt_builder_program_pareto/` created.

- [ ] **Step 4: Agent loads compiled programs**

Run: `uv run python -c "
from agent.classifier import classify_task
from agent.prompt_builder import build_dynamic_addendum
from agent.evaluator import evaluate_completion
print('classifier:', classify_task('test', ''))
print('builder:', build_dynamic_addendum('email', 'send mail to John', ''))
print('evaluator import:', evaluate_completion is not None)
"`
Expected: no exceptions.

- [ ] **Step 5: Benchmark regression check (optional, requires harness)**

Run: `make task TASKS='t01,t05,t11'`
Expected: scores match baseline (no >5% regression).

- [ ] **Step 6: Final acceptance**

Confirm against `docs/superpowers/specs/2026-04-26-gepa-integration-design.md` § 10:
- [x] `OPTIMIZER_*=copro` parity
- [x] `OPTIMIZER_BUILDER=gepa` works, saves main + Pareto
- [x] Unit tests `test_optimization_feedback.py`, `test_optimization_backend_select.py`, `test_optimization_budget.py` green
- [x] Documentation updated

If any unchecked — open follow-up issue, do not silently mark complete.

---

## Self-review notes

- Spec § 1 cели: ✓ all targets covered (Tasks 1-10), per-target env (Task 8).
- Spec § 2 architecture: ✓ Tasks 1, 5, 7, 8.
- Spec § 3 metrics & feedback: ✓ Tasks 2, 3.
- Spec § 4 GEPA: ✓ Tasks 7, 9, 10. § 4.4 logprobs research note → captured in spec, not actionable (no surrogate impl in scope).
- Spec § 5 COPRO: ✓ Task 5.
- Spec § 6 migration: ✓ Tasks ordered identically to spec migration list.
- Spec § 7 optimize_prompts.py shrink: ✓ Tasks 5, 8.
- Spec § 8 tests: ✓ Tasks 3, 6, 8, 11.
- Spec § 9 env vars: ✓ Task 12.
- Spec § 10 acceptance: ✓ Task 13.
- Spec § 11 follow-ups: explicitly out of scope per spec.
