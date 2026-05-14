# Active Eval Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `propose_optimizations.py` validates each recommendation by re-running the original task with the recommendation injected, writing the file only if score does not regress.

**Architecture:** Add 3 injection params (`injected_session_rules`, `injected_prompt_addendum`, `injected_security_gates`) through `run_agent → run_pipeline → _build_static_system`. Add `task_id` to `EvalInput`/eval_log. Add `validate_recommendation()` + `read_original_score()` to `propose_optimizations.py`; gate file writes on validation result. Disable eval inside the script via `os.environ["EVAL_ENABLED"]="0"` before agent imports.

**Tech Stack:** Python, Pydantic, pytest, PyYAML, bitgn protobuf harness client.

---

## File Map

| File | Change |
|---|---|
| `agent/evaluator.py` | Add `task_id: str = ""` to `EvalInput`; write to log entry |
| `agent/pipeline.py` | `_build_static_system` gets `injected_prompt_addendum`; `run_pipeline` gets `task_id` + 3 injection params; security gates merge; `_run_evaluator_safe` gets `task_id` |
| `agent/orchestrator.py` | `run_agent` gets 3 injection params, passes to `run_pipeline` |
| `scripts/propose_optimizations.py` | `EVAL_ENABLED=0` before imports; add `read_original_score()`, `validate_recommendation()`, `_dedup_by_content_per_task()`; restructure main() to validate before writing |
| `tests/test_evaluator.py` | Update: assert `task_id` in log entry |
| `tests/test_pipeline.py` | Add: injection params tests |
| `tests/test_propose_optimizations.py` | Add: `read_original_score`, `validate_recommendation`, dedup tests; update existing `main(dry_run=False)` tests with `validate_recommendation` mock |

---

## Task 1: evaluator.py — Add task_id to EvalInput and eval_log

**Files:**
- Modify: `agent/evaluator.py:18-29` (EvalInput dataclass)
- Modify: `agent/evaluator.py:151-167` (_append_log)
- Test: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_evaluator.py — add after existing tests
def test_task_id_written_to_log(tmp_path):
    eval_json = json.dumps({
        "reasoning": "ok", "score": 8, "comment": "fine",
        "prompt_optimization": [], "rule_optimization": [], "security_optimization": [],
    })
    log_path = tmp_path / "eval_log.jsonl"
    inp = EvalInput(
        task_id="t07",
        task_text="How many products?",
        agents_md="rules",
        db_schema="CREATE TABLE products(id INT)",
        sgr_trace=[],
        cycles=1,
        final_outcome="OUTCOME_OK",
    )
    with patch("agent.evaluator.call_llm_raw", return_value=eval_json), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        run_evaluator(inp, model="test-model", cfg={})
    line = json.loads(log_path.read_text().strip())
    assert line["task_id"] == "t07"
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
uv run pytest tests/test_evaluator.py::test_task_id_written_to_log -v
```

Expected: `TypeError` or `AttributeError` (field doesn't exist yet)

- [ ] **Step 3: Implement — add task_id to EvalInput**

In `agent/evaluator.py`, change `EvalInput`:

```python
@dataclass
class EvalInput:
    task_text: str
    agents_md: str
    db_schema: str
    sgr_trace: list[dict]
    cycles: int
    final_outcome: str
    task_id: str = ""                          # NEW
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    sql_plan_outputs: list = field(default_factory=list)
    executed_queries: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Implement — write task_id to log entry**

In `_append_log`, add `"task_id": eval_input.task_id` to the entry dict:

```python
def _append_log(eval_input: EvalInput, result: PipelineEvalOutput, metrics: dict) -> None:
    entry = {
        "task_id": eval_input.task_id,        # NEW
        "task_text": eval_input.task_text,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "score": result.score,
        "comment": result.comment,
        "prompt_optimization": result.prompt_optimization,
        "rule_optimization": result.rule_optimization,
        "security_optimization": result.security_optimization,
        "agents_md_coverage": metrics["agents_md_coverage"],
        "schema_grounding": metrics["schema_grounding"],
        "reasoning": result.reasoning,
    }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 5: Run test — confirm PASS**

```bash
uv run pytest tests/test_evaluator.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/evaluator.py tests/test_evaluator.py
git commit -m "feat(eval): add task_id to EvalInput and eval_log entries"
```

---

## Task 2: pipeline.py — _build_static_system injected_prompt_addendum

**Files:**
- Modify: `agent/pipeline.py:190-240` (_build_static_system)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_pipeline.py — add to existing file
from agent.pipeline import _build_static_system
from agent.rules_loader import RulesLoader
from unittest.mock import patch, MagicMock

def _make_rules_loader():
    rl = MagicMock(spec=RulesLoader)
    rl.get_rules_markdown.return_value = ""
    return rl

def test_injected_prompt_addendum_appended():
    blocks = _build_static_system(
        phase="sql_plan",
        agents_md="",
        agents_md_index={},
        db_schema="",
        schema_digest={},
        rules_loader=_make_rules_loader(),
        security_gates=[],
        injected_prompt_addendum="USE indexed columns",
    )
    guide_block = blocks[-1]["text"]
    assert "# INJECTED OPTIMIZATION" in guide_block
    assert "USE indexed columns" in guide_block

def test_no_addendum_no_injection():
    blocks = _build_static_system(
        phase="sql_plan",
        agents_md="",
        agents_md_index={},
        db_schema="",
        schema_digest={},
        rules_loader=_make_rules_loader(),
        security_gates=[],
        injected_prompt_addendum="",
    )
    guide_block = blocks[-1]["text"]
    assert "# INJECTED OPTIMIZATION" not in guide_block
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
uv run pytest tests/test_pipeline.py::test_injected_prompt_addendum_appended -v
```

Expected: `TypeError: _build_static_system() got unexpected keyword argument`

- [ ] **Step 3: Implement**

In `agent/pipeline.py`, update `_build_static_system` signature and guide block:

```python
def _build_static_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    task_text: str = "",
    injected_prompt_addendum: str = "",       # NEW
) -> list[dict]:
```

Replace the final `blocks.append` (lines 234-239):

```python
    guide = load_prompt(phase)
    guide_text = guide or f"# PHASE: {phase}"
    if injected_prompt_addendum:
        guide_text += f"\n\n# INJECTED OPTIMIZATION\n{injected_prompt_addendum}"
    blocks.append({
        "type": "text",
        "text": guide_text,
        "cache_control": {"type": "ephemeral"},
    })
    return blocks
```

- [ ] **Step 4: Run test — confirm PASS**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): add injected_prompt_addendum to _build_static_system"
```

---

## Task 3: pipeline.py — run_pipeline injection params + security gates merge

**Files:**
- Modify: `agent/pipeline.py:359-790` (run_pipeline, _run_evaluator_safe)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pipeline.py — add
from unittest.mock import patch, MagicMock, call
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult

def _make_pre():
    return PrephaseResult(
        agents_md_content="",
        agents_md_index={},
        db_schema="CREATE TABLE t(id INT)",
        schema_digest={"tables": {}},
    )

def test_injected_session_rules_prepopulated(tmp_path):
    """injected_session_rules appear in first SQL_PLAN user_msg."""
    captured_user_msgs = []

    def fake_call_llm(system, user_msg, model, cfg, **kw):
        captured_user_msgs.append(user_msg)
        return None  # fail fast — we only care about user_msg content

    vm = MagicMock()
    with patch("agent.pipeline.call_llm_raw", side_effect=fake_call_llm), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline._get_rules_loader", return_value=_make_rules_loader()), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._EVAL_ENABLED", False):
        run_pipeline(vm, "m", "task text", _make_pre(), {},
                     injected_session_rules=["Always use LIMIT 100"])

    assert any("Always use LIMIT 100" in m for m in captured_user_msgs)

def test_injected_security_gates_merged():
    """injected gate blocks query that matches its pattern."""
    from agent.pipeline import _get_security_gates
    extra_gate = {"id": "test-gate", "pattern": r"DROP\s+TABLE", "message": "no drop", "verified": True}
    vm = MagicMock()
    sql_out = '{"queries": ["DROP TABLE t"], "agents_md_refs": [], "reasoning": ""}'
    with patch("agent.pipeline.call_llm_raw", return_value=sql_out), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline._get_rules_loader", return_value=_make_rules_loader()), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._EVAL_ENABLED", False):
        stats, _ = run_pipeline(vm, "m", "drop table t", _make_pre(), {},
                                injected_security_gates=[extra_gate])
    # security gate blocked — vm.answer called with clarification
    vm.answer.assert_called()
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/test_pipeline.py::test_injected_session_rules_prepopulated tests/test_pipeline.py::test_injected_security_gates_merged -v
```

Expected: `TypeError: run_pipeline() got unexpected keyword argument`

- [ ] **Step 3: Implement — run_pipeline signature**

Change `run_pipeline` signature:

```python
def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
    task_id: str = "",
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
) -> tuple[dict, threading.Thread | None]:
    """Phase-based SQL pipeline. Returns (stats dict, eval Thread or None)."""
    rules_loader = _get_rules_loader()
    security_gates = _get_security_gates() + (injected_security_gates or [])   # CHANGED
    session_rules: list[str] = list(injected_session_rules or [])              # CHANGED
    highlighted_vault_rules: list[str] = []
```

- [ ] **Step 4: Implement — pass injected_prompt_addendum to _build_static_system calls**

Find the 3 calls to `_build_static_system` in `run_pipeline` (lines ~414-427) and add `injected_prompt_addendum=injected_prompt_addendum` to each:

```python
    static_sql = _build_static_system(
        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
        injected_prompt_addendum=injected_prompt_addendum,             # NEW
    )
    static_learn = _build_static_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
        injected_prompt_addendum=injected_prompt_addendum,             # NEW
    )
    static_answer = _build_static_system(
        "answer", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        injected_prompt_addendum=injected_prompt_addendum,             # NEW
    )
```

Note: the discovery-only detection rebuilds `static_sql` at line ~597 — add `injected_prompt_addendum` there too:

```python
                    static_sql = _build_static_system(
                        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
                        pre.schema_digest, rules_loader, security_gates,
                        confirmed_values=confirmed_values, task_text=task_text,
                        injected_prompt_addendum=injected_prompt_addendum,   # NEW
                    )
```

- [ ] **Step 5: Implement — pass task_id to _run_evaluator_safe**

In the eval thread creation block (~line 762), add `task_id=task_id` to kwargs:

```python
        eval_thread = threading.Thread(
            target=_run_evaluator_safe,
            kwargs={
                "task_id": task_id,                  # NEW
                "task_text": task_text,
                "agents_md": pre.agents_md_content,
                "agents_md_index": pre.agents_md_index,
                "db_schema": pre.db_schema,
                "schema_digest": pre.schema_digest,
                "sgr_trace": sgr_trace,
                "cycles": cycles_used,
                "final_outcome": outcome,
                "sql_plan_outputs": sql_plan_outputs,
                "executed_queries": executed_queries,
                "model": _MODEL_EVALUATOR,
                "cfg": cfg,
            },
            daemon=False,
        )
```

- [ ] **Step 6: Implement — _run_evaluator_safe task_id param**

Update `_run_evaluator_safe` signature and EvalInput call:

```python
def _run_evaluator_safe(
    task_text: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    sgr_trace: list[dict],
    cycles: int,
    final_outcome: str,
    sql_plan_outputs: list,
    executed_queries: list[str],
    model: str,
    cfg: dict,
    task_id: str = "",              # NEW
) -> None:
    try:
        from .evaluator import run_evaluator, EvalInput
        run_evaluator(
            EvalInput(
                task_id=task_id,   # NEW
                task_text=task_text,
                agents_md=agents_md,
                db_schema=db_schema,
                sgr_trace=sgr_trace,
                cycles=cycles,
                final_outcome=final_outcome,
            ),
            model=model,
            cfg=cfg,
        )
    except Exception as e:
        print(f"{CLI_YELLOW}[pipeline] evaluator error (non-fatal): {e}{CLI_CLR}")
```

- [ ] **Step 7: Run all tests — confirm PASS**

```bash
uv run pytest tests/test_pipeline.py tests/test_evaluator.py -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add agent/pipeline.py
git commit -m "feat(pipeline): add injection params and task_id to run_pipeline"
```

---

## Task 4: orchestrator.py — run_agent injection params

**Files:**
- Modify: `agent/orchestrator.py`
- Test: `tests/test_orchestrator_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_orchestrator_pipeline.py — add
def test_run_agent_passes_injection_params():
    from agent.orchestrator import run_agent
    from unittest.mock import patch, MagicMock

    mock_pre = MagicMock()
    mock_pre.agents_md_content = ""
    mock_pre.agents_md_index = {}
    mock_pre.db_schema = ""
    mock_pre.schema_digest = {"tables": {}}

    with patch("agent.orchestrator.EcomRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre), \
         patch("agent.orchestrator.run_pipeline", return_value=({"outcome": "OUTCOME_OK", "cycles_used": 1, "step_facts": [], "done_ops": [], "input_tokens": 0, "output_tokens": 0, "total_elapsed_ms": 0}, None)) as mock_pipeline:
        run_agent(
            model_configs={},
            harness_url="http://localhost",
            task_text="test",
            task_id="t01",
            injected_session_rules=["rule1"],
            injected_prompt_addendum="addon",
            injected_security_gates=[{"id": "g1"}],
        )
    _, kwargs = mock_pipeline.call_args
    assert kwargs["task_id"] == "t01"
    assert kwargs["injected_session_rules"] == ["rule1"]
    assert kwargs["injected_prompt_addendum"] == "addon"
    assert kwargs["injected_security_gates"] == [{"id": "g1"}]
```

- [ ] **Step 2: Run test — confirm FAIL**

```bash
uv run pytest tests/test_orchestrator_pipeline.py::test_run_agent_passes_injection_params -v
```

Expected: `TypeError: run_agent() got unexpected keyword argument`

- [ ] **Step 3: Implement**

Replace `agent/orchestrator.py` content:

```python
"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import os

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.pipeline import run_pipeline

_MODEL = os.environ.get("MODEL", "")


def run_agent(
    model_configs: dict,
    harness_url: str,
    task_text: str,
    task_id: str = "",
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
) -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)
    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}
    pre = run_prephase(vm, task_text)
    stats, eval_thread = run_pipeline(
        vm, model, task_text, pre, cfg,
        task_id=task_id,
        injected_session_rules=injected_session_rules or [],
        injected_prompt_addendum=injected_prompt_addendum,
        injected_security_gates=injected_security_gates or [],
    )
    if eval_thread is not None:
        eval_thread.join(timeout=30)
        if eval_thread.is_alive():
            print("[orchestrator] evaluator timeout — log may be incomplete")
    stats["model_used"] = model
    stats["task_type"] = "lookup"
    return stats
```

- [ ] **Step 4: Run all tests — confirm PASS**

```bash
uv run pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator_pipeline.py
git commit -m "feat(orchestrator): forward injection params through run_agent"
```

---

## Task 5: propose_optimizations.py — EVAL_ENABLED=0, env vars, read_original_score

**Files:**
- Modify: `scripts/propose_optimizations.py:1-20` (top of file)
- Test: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests for read_original_score**

```python
# tests/test_propose_optimizations.py — add
import json, time
from pathlib import Path

def test_read_original_score_found(tmp_path):
    logs_dir = tmp_path / "logs"
    run_dir = logs_dir / "20240101_120000_model"
    run_dir.mkdir(parents=True)
    task_file = run_dir / "t01.jsonl"
    task_file.write_text(
        json.dumps({"type": "llm_call", "phase": "sql_plan"}) + "\n" +
        json.dumps({"type": "task_result", "score": 0.75, "outcome": "OUTCOME_OK"}) + "\n"
    )
    score = po.read_original_score("t01", logs_dir=logs_dir)
    assert score == 0.75

def test_read_original_score_excludes_validate_dirs(tmp_path):
    logs_dir = tmp_path / "logs"
    # validate- dir has score 1.0, real dir has score 0.5
    validate_dir = logs_dir / "validate-20240101"
    validate_dir.mkdir(parents=True)
    (validate_dir / "t01.jsonl").write_text(
        json.dumps({"type": "task_result", "score": 1.0}) + "\n"
    )
    # real dir is older — still should be picked (validate- excluded)
    time.sleep(0.01)
    real_dir = logs_dir / "20240101_120000_model"
    real_dir.mkdir()
    (real_dir / "t01.jsonl").write_text(
        json.dumps({"type": "task_result", "score": 0.5}) + "\n"
    )
    score = po.read_original_score("t01", logs_dir=logs_dir)
    assert score == 0.5

def test_read_original_score_not_found_returns_none(tmp_path):
    logs_dir = tmp_path / "logs"
    run_dir = logs_dir / "20240101_120000_model"
    run_dir.mkdir(parents=True)
    # no t99.jsonl in this dir
    score = po.read_original_score("t99", logs_dir=logs_dir)
    assert score is None

def test_read_original_score_no_logs_dir(tmp_path):
    score = po.read_original_score("t01", logs_dir=tmp_path / "nonexistent")
    assert score is None
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/test_propose_optimizations.py::test_read_original_score_found -v
```

Expected: `AttributeError: module has no attribute 'read_original_score'`

- [ ] **Step 3: Implement — EVAL_ENABLED=0 before imports**

At the very top of `scripts/propose_optimizations.py`, before any `from agent` import, add:

```python
import os
os.environ["EVAL_ENABLED"] = "0"   # disable eval during validation re-runs
```

The current file starts with:
```python
#!/usr/bin/env python3
"""Synthesize eval_log optimization entries into candidate files."""
from __future__ import annotations

import argparse
import hashlib
...
```

After change (lines 1-10 become):
```python
#!/usr/bin/env python3
"""Synthesize eval_log optimization entries into candidate files."""
from __future__ import annotations

import os
os.environ["EVAL_ENABLED"] = "0"   # must be before agent imports

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import knowledge_loader
from agent.llm import call_llm_raw
```

- [ ] **Step 4: Implement — env vars + read_original_score**

After the existing module-level constants (after `_MODELS_JSON = ...`), add:

```python
_BITGN_URL = os.getenv("BENCHMARK_HOST") or "https://api.bitgn.com"
_BENCHMARK_ID = os.getenv("BENCHMARK_ID") or "bitgn/pac1-dev"
_BITGN_API_KEY = os.getenv("BITGN_API_KEY") or ""
_LOGS_DIR = _ROOT / "logs"


def read_original_score(task_id: str, logs_dir: Path | None = None) -> float | None:
    """Scan logs/ for latest non-validate run, extract task_result.score for task_id."""
    if logs_dir is None:
        logs_dir = _LOGS_DIR
    if not logs_dir.exists():
        return None
    dirs = [d for d in logs_dir.iterdir() if d.is_dir() and not d.name.startswith("validate-")]
    if not dirs:
        return None
    latest = max(dirs, key=lambda d: d.stat().st_mtime)
    task_file = latest / f"{task_id}.jsonl"
    if not task_file.exists():
        return None
    for line in task_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
            if ev.get("type") == "task_result":
                return float(ev["score"])
        except Exception:
            continue
    return None
```

- [ ] **Step 5: Run tests — confirm PASS**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add EVAL_ENABLED=0 guard and read_original_score"
```

---

## Task 6: propose_optimizations.py — validate_recommendation

**Files:**
- Modify: `scripts/propose_optimizations.py` (add function)
- Test: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_propose_optimizations.py — add
from unittest.mock import patch, MagicMock

def _make_harness_mocks(task_id="t01", trial_score=0.9, trial_ids=None):
    """Build mock harness client chain for validate_recommendation tests."""
    if trial_ids is None:
        trial_ids = ["trial-1", "trial-2"]

    mock_run = MagicMock()
    mock_run.run_id = "run-abc"
    mock_run.trial_ids = trial_ids

    def fake_start_trial(req):
        resp = MagicMock()
        # First trial matches task_id, second doesn't
        resp.task_id = task_id if req.trial_id == trial_ids[0] else "other-task"
        resp.trial_id = req.trial_id
        resp.harness_url = "http://fake"
        resp.instruction = "How many items?"
        return resp

    mock_end = MagicMock()
    mock_end.score = trial_score

    client = MagicMock()
    client.start_run.return_value = mock_run
    client.start_trial.side_effect = fake_start_trial
    client.end_trial.return_value = mock_end
    return client


def test_validate_recommendation_accepted(tmp_path):
    """validation_score >= original_score → returns (original, validation)."""
    logs_dir = tmp_path / "logs"
    run_dir = logs_dir / "20240101_120000_model"
    run_dir.mkdir(parents=True)
    (run_dir / "t01.jsonl").write_text(
        json.dumps({"type": "task_result", "score": 0.7}) + "\n"
    )
    client = _make_harness_mocks(task_id="t01", trial_score=0.9)

    with patch.object(po, "_LOGS_DIR", logs_dir), \
         patch("bitgn.harness_connect.HarnessServiceClientSync", return_value=client), \
         patch("agent.run_agent") as mock_run_agent:
        original, validation = po.validate_recommendation(
            "t01", injected_session_rules=["Never use SELECT *"]
        )

    assert original == pytest.approx(0.7)
    assert validation == pytest.approx(0.9)
    mock_run_agent.assert_called_once()
    call_kw = mock_run_agent.call_args[1]
    assert call_kw["injected_session_rules"] == ["Never use SELECT *"]
    assert call_kw["task_id"] == "t01"


def test_validate_recommendation_rejected(tmp_path):
    """validation_score < original_score → returns (original, lower_validation)."""
    logs_dir = tmp_path / "logs"
    run_dir = logs_dir / "20240101_120000_model"
    run_dir.mkdir(parents=True)
    (run_dir / "t01.jsonl").write_text(
        json.dumps({"type": "task_result", "score": 1.0}) + "\n"
    )
    client = _make_harness_mocks(task_id="t01", trial_score=0.5)

    with patch.object(po, "_LOGS_DIR", logs_dir), \
         patch("bitgn.harness_connect.HarnessServiceClientSync", return_value=client), \
         patch("agent.run_agent"):
        original, validation = po.validate_recommendation("t01")

    assert original == pytest.approx(1.0)
    assert validation == pytest.approx(0.5)


def test_validate_recommendation_task_not_in_trials(tmp_path):
    """task_id not found in any trial → validation_score is None."""
    logs_dir = tmp_path / "logs"
    run_dir = logs_dir / "20240101_120000_model"
    run_dir.mkdir(parents=True)
    (run_dir / "t01.jsonl").write_text(
        json.dumps({"type": "task_result", "score": 0.8}) + "\n"
    )
    # both trials have different task_id
    client = _make_harness_mocks(task_id="other", trial_score=0.0, trial_ids=["trial-1"])

    with patch.object(po, "_LOGS_DIR", logs_dir), \
         patch("bitgn.harness_connect.HarnessServiceClientSync", return_value=client), \
         patch("agent.run_agent") as mock_run_agent:
        original, validation = po.validate_recommendation("t01")

    assert original == pytest.approx(0.8)
    assert validation is None
    mock_run_agent.assert_not_called()


def test_validate_recommendation_no_baseline(tmp_path):
    """No baseline score → original is None."""
    client = _make_harness_mocks(task_id="t99", trial_score=0.9)

    with patch.object(po, "_LOGS_DIR", tmp_path / "empty"), \
         patch("bitgn.harness_connect.HarnessServiceClientSync", return_value=client), \
         patch("agent.run_agent"):
        original, validation = po.validate_recommendation("t99")

    assert original is None
    assert validation == pytest.approx(0.9)
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/test_propose_optimizations.py::test_validate_recommendation_accepted -v
```

Expected: `AttributeError: module has no attribute 'validate_recommendation'`

- [ ] **Step 3: Implement validate_recommendation**

> **Verify harness API style before implementing:** check whether `bitgn.harness_connect.HarnessServiceClientSync` methods accept keyword args directly (`client.start_trial(trial_id=trial_id)`) or require Request objects (`StartTrialRequest(trial_id=trial_id)`). Adjust imports and calls accordingly. Run `grep -r "HarnessServiceClientSync" tests/` to find existing usage patterns.

Add after `read_original_score` in `scripts/propose_optimizations.py`:

```python
def validate_recommendation(
    task_id: str,
    *,
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
) -> tuple[float | None, float | None]:
    """Re-run task with recommendation injected. Returns (original_score, validation_score).

    Either value can be None: original if no baseline found, validation if task not in trials.
    """
    import datetime
    from bitgn.harness_connect import HarnessServiceClientSync
    from bitgn.harness_pb2 import StartRunRequest, StartTrialRequest, EndTrialRequest, SubmitRunRequest
    from agent import run_agent

    original_score = read_original_score(task_id)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    client = HarnessServiceClientSync(_BITGN_URL)
    run = client.start_run(StartRunRequest(
        name=f"validate-{timestamp}",
        benchmark_id=_BENCHMARK_ID,
        api_key=_BITGN_API_KEY,
    ))

    validation_score: float | None = None
    for trial_id in run.trial_ids:
        trial = client.start_trial(StartTrialRequest(trial_id=trial_id))
        if trial.task_id != task_id:
            client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
            continue
        run_agent(
            model_configs={},
            harness_url=trial.harness_url,
            task_text=trial.instruction,
            task_id=trial.task_id,
            injected_session_rules=injected_session_rules or [],
            injected_prompt_addendum=injected_prompt_addendum,
            injected_security_gates=injected_security_gates or [],
        )
        result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
        validation_score = float(result.score)
        break

    client.submit_run(SubmitRunRequest(run_id=run.run_id, force=True))

    if validation_score is None:
        print(f"[validate] WARNING: task_id={task_id!r} not found in trial_ids — skipping")

    return original_score, validation_score
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add validate_recommendation with harness re-run"
```

---

## Task 7: propose_optimizations.py — main() validation gating + content-hash dedup

**Files:**
- Modify: `scripts/propose_optimizations.py:282-402` (main function)
- Test: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_propose_optimizations.py — add

def test_validation_gates_file_write_accepted(tmp_path):
    """Accepted recommendation (score doesn't regress) → file written."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    entry = _eval_entry(rule_opts=["Never use SELECT *"])
    entry["task_id"] = "t01"
    _write_eval_log(eval_log, [entry])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "validate_recommendation", return_value=(0.7, 0.9)) as mock_val:
        po.main(dry_run=False)

    mock_val.assert_called_once_with(
        "t01",
        injected_session_rules=["Never use SELECT *"],
        injected_prompt_addendum="",
        injected_security_gates=[],
    )
    assert len(list(rules_dir.glob("*.yaml"))) == 1


def test_validation_gates_file_write_rejected(tmp_path):
    """Rejected recommendation (score regresses) → no file written."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    entry = _eval_entry(rule_opts=["Never use SELECT *"])
    entry["task_id"] = "t01"
    _write_eval_log(eval_log, [entry])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "validate_recommendation", return_value=(1.0, 0.5)):
        po.main(dry_run=False)

    assert len(list(rules_dir.glob("*.yaml"))) == 0


def test_dry_run_skips_validation(tmp_path):
    """--dry-run skips validate_recommendation entirely."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    entry = _eval_entry(rule_opts=["Never use SELECT *"])
    entry["task_id"] = "t01"
    _write_eval_log(eval_log, [entry])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "validate_recommendation") as mock_val:
        po.main(dry_run=True)

    mock_val.assert_not_called()


def test_no_baseline_score_writes_with_warning(tmp_path):
    """original_score is None → write file anyway, log WARNING."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    entry = _eval_entry(rule_opts=["Never use SELECT *"])
    entry["task_id"] = "t01"
    _write_eval_log(eval_log, [entry])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "validate_recommendation", return_value=(None, 0.8)):
        po.main(dry_run=False)

    assert len(list(rules_dir.glob("*.yaml"))) == 1


def test_content_hash_dedup_per_task(tmp_path):
    """Same rec text for same task_id validated only once."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    # Two entries, same task_id, same rec text
    entry1 = _eval_entry(rule_opts=["Never use SELECT *"])
    entry1["task_id"] = "t01"
    entry2 = _eval_entry(rule_opts=["Never use SELECT *"])
    entry2["task_id"] = "t01"
    _write_eval_log(eval_log, [entry1, entry2])

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "validate_recommendation", return_value=(0.7, 0.9)) as mock_val:
        po.main(dry_run=False)

    # validated exactly once despite two entries
    assert mock_val.call_count == 1
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
uv run pytest tests/test_propose_optimizations.py::test_validation_gates_file_write_accepted tests/test_propose_optimizations.py::test_validation_gates_file_write_rejected -v
```

Expected: FAIL (validate_recommendation not called yet)

- [ ] **Step 3: Implement — _dedup_by_content_per_task helper**

Add before `main()` in `scripts/propose_optimizations.py`:

```python
def _dedup_by_content_per_task(
    items: list[tuple[str, dict, str]],
) -> tuple[list[tuple[str, dict, str]], list[str]]:
    """Remove exact-duplicate recs within the same task_id.

    Returns (deduplicated_items, skipped_hashes).
    """
    seen: set[tuple[str, str]] = set()
    result = []
    skipped: list[str] = []
    for rec, entry, h in items:
        key = (entry.get("task_id", ""), rec)
        if key in seen:
            skipped.append(h)
        else:
            seen.add(key)
            result.append((rec, entry, h))
    return result, skipped
```

- [ ] **Step 4: Implement — restructure main() to validate before writing**

Replace the three channel processing blocks in `main()`. The key change is: after `_synthesize_*`, call `validate_recommendation` when not dry_run, then decide whether to write. Here is the complete replacement for the rule channel block (and similarly for security and prompt):

**Rule channel block (replaces lines ~328-347):**

```python
    for raw_rec, entry, all_hashes in rule_clusters:
        task_id = entry.get("task_id", "")
        print(f"[rule] {raw_rec[:80]}...")
        content = _synthesize_rule(raw_rec, rules_md, model, cfg)
        if content is None:
            new_processed.update(all_hashes)
            print("  → skip (null/duplicate)")
            continue
        conflict = _check_contradiction(content, rules_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_RULES_DIR, "sql-")
        if dry_run:
            print(f"  → [DRY RUN] sql-{num:03d}.yaml: {content[:100]}")
            new_processed.update(all_hashes)
        else:
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[raw_rec],
                injected_prompt_addendum="",
                injected_security_gates=[],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
                # intentionally not updating new_processed — retry on next run
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
                # intentionally not updating new_processed — retry on next run when baseline may change
```

**Security channel block (replaces lines ~349-368):**

```python
    for raw_rec, entry, all_hashes in security_clusters:
        task_id = entry.get("task_id", "")
        print(f"[security] {raw_rec[:80]}...")
        gate_spec = _synthesize_security_gate(raw_rec, security_md, model, cfg)
        if gate_spec is None:
            new_processed.update(all_hashes)
            print("  → skip (null/not-applicable)")
            continue
        conflict = _check_contradiction(gate_spec.get("message", ""), security_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_SECURITY_DIR, "sec-")
        if dry_run:
            print(f"  → [DRY RUN] sec-{num:03d}.yaml: {gate_spec.get('message', '')}")
            new_processed.update(all_hashes)
        else:
            injected_gate = {
                "id": f"val-{num:03d}", "pattern": gate_spec.get("pattern", ""),
                "check_name": gate_spec.get("check", ""),
                "message": gate_spec["message"], "verified": True,
            }
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[],
                injected_prompt_addendum="",
                injected_security_gates=[injected_gate],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
                # intentionally not updating new_processed — retry on next run
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
                # intentionally not updating new_processed — retry on next run when baseline may change
```

**Prompt channel block (replaces lines ~370-388):**

```python
    for raw_rec, entry, all_hashes in prompt_clusters:
        task_id = entry.get("task_id", "")
        print(f"[prompt] {raw_rec[:80]}...")
        patch_result = _synthesize_prompt_patch(raw_rec, prompts_md, model, cfg)
        if patch_result is None:
            new_processed.update(all_hashes)
            print("  → skip (null/vague)")
            continue
        conflict = _check_contradiction(patch_result.get("content", ""), prompts_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        if dry_run:
            print(f"  → [DRY RUN] {patch_result['target_file']}: {patch_result['content'][:80]}")
            new_processed.update(all_hashes)
        else:
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[],
                injected_prompt_addendum=raw_rec,
                injected_security_gates=[],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
                # intentionally not updating new_processed — retry on next run
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
                # intentionally not updating new_processed — retry on next run when baseline may change
```

- [ ] **Step 5: Implement — add content-hash dedup after item flattening**

In `main()`, insert after the three `*_items` list comprehensions (~lines 303-321) and **before** the three `_cluster_recs` calls (~lines 323-325). Context:

```python
    # existing — end of items block
    prompt_items: list[tuple[str, dict, str]] = [...]

    # INSERT HERE ↓
    rule_items, rule_dup_hashes = _dedup_by_content_per_task(rule_items)
    ...

    # existing — clustering
    rule_clusters = _cluster_recs(rule_items, ...)
```

Full block to insert:

```python
    # Content-hash dedup: within same task_id, identical recs validated once
    rule_items, rule_dup_hashes = _dedup_by_content_per_task(rule_items)
    new_processed.update(rule_dup_hashes)
    security_items, sec_dup_hashes = _dedup_by_content_per_task(security_items)
    new_processed.update(sec_dup_hashes)
    prompt_items, prompt_dup_hashes = _dedup_by_content_per_task(prompt_items)
    new_processed.update(prompt_dup_hashes)
```

- [ ] **Step 6: Update existing tests that call `po.main(dry_run=False)`**

After Task 7 changes, `main()` calls `validate_recommendation()` for every non-dry-run entry. Existing tests that call `po.main(dry_run=False)` without mocking it will try to hit the real harness.

In `tests/test_propose_optimizations.py`, add `patch.object(po, "validate_recommendation", return_value=(0.8, 0.9))` to every test that calls `po.main(dry_run=False)`. Affected tests (search with `grep -n "dry_run=False" tests/test_propose_optimizations.py`):

```python
# Pattern — wrap existing `with patches[...]` context with one more patch:
         patch.object(po, "validate_recommendation", return_value=(0.8, 0.9)):
    po.main(dry_run=False)
```

- [ ] **Step 7: Run all tests — confirm PASS**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all PASS

- [ ] **Step 8: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 9: Smoke test dry-run**

```bash
uv run python scripts/propose_optimizations.py --dry-run
```

Expected: runs without error, prints `[DRY RUN]` entries or "No eval log"

- [ ] **Step 10: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): gate file writes on validation score; dedup by content hash per task_id"
```

---

## Self-Review Against Spec

### Spec Coverage Check

| Spec Requirement | Task |
|---|---|
| `EvalInput.task_id` field, written to eval_log | Task 1 |
| `injected_session_rules` → prepopulates `session_rules` | Task 3 |
| `injected_prompt_addendum` → appended to guide block | Task 2 |
| `injected_security_gates` → merged with `_get_security_gates()` result | Task 3 |
| `run_agent` gets 3 injection params | Task 4 |
| `EVAL_ENABLED=0` before agent imports in propose_optimizations | Task 5 |
| `read_original_score` — excludes `validate-*`, picks latest by mtime | Task 5 |
| `validate_recommendation` — harness start_run/trial loop | Task 6 |
| `validate-{timestamp}` run name | Task 6 |
| Skip trials where `trial.task_id != task_id`, end them | Task 6 |
| `submit_run(force=True)` after loop | Task 6 |
| Scoring: `None` baseline → write + WARNING | Task 7 |
| Scoring: `validation >= original` → write ACCEPTED | Task 7 |
| Scoring: `validation < original` → skip REJECTED | Task 7 |
| `--dry-run` skips validation, writes unconditionally | Task 7 |
| Dedup by content hash per task_id before validation | Task 7 |
| Each `prompt_optimization` element validated separately | Task 7 (raw_rec passed as prompt_addendum per element, clustering handles separately) |
| Each `rule_optimization` element validated as single-element list | Task 7 (raw_rec passed as `[raw_rec]` to injected_session_rules) |

### Placeholder Check

No TBD/TODO in plan. All code blocks complete.

### Type Consistency

- `validate_recommendation` returns `tuple[float | None, float | None]` — used as `original, validation = validate_recommendation(...)` in Task 7 ✓
- `run_pipeline` injection params: `list[str] | None`, `str`, `list[dict] | None` — match `run_agent` signature in Task 4 ✓
- `_dedup_by_content_per_task` returns `tuple[list[...], list[str]]` — destructured as `items, dup_hashes` in Task 7 ✓
- `EvalInput.task_id: str = ""` — passed as `task_id=task_id` in `_run_evaluator_safe` Task 3 ✓

### Known Risks

- **Harness API style (Task 6):** implementation assumes Request-object style (`StartTrialRequest(...)`). Verify against actual `bitgn` API before coding — may need kwargs style instead.
- **Existing tests (Task 7 Step 6):** run `grep -n "dry_run=False" tests/test_propose_optimizations.py` to get full list of tests requiring `validate_recommendation` mock.
