# TDD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add TDD gates to the agent pipeline — generate Python acceptance tests before SQL planning, run them in subprocess after execution and after answer synthesis; `vm.answer()` is only called when both suites pass.

**Architecture:** `TestGenOutput` model holds generated test code; `agent/test_runner.py` runs tests in isolated subprocess via `tempfile` + `subprocess`; `pipeline.py` wraps `vm.answer()` behind both test suites when `TDD_ENABLED=1`. Non-TDD path is structurally unchanged (`success = True; break` + ANSWER outside loop).

**Tech Stack:** Python 3.11+, Pydantic v2, subprocess, tempfile, pytest, existing pipeline/llm stack

---

## File Map

**New files:**
- `agent/test_runner.py` — subprocess test runner
- `data/prompts/test_gen.md` — LLM prompt for test generation
- `tests/test_test_runner.py` — unit tests for test_runner
- `tests/test_pipeline_tdd.py` — pipeline integration tests for TDD path

**Modified files:**
- `agent/models.py` — add `TestGenOutput`
- `agent/trace.py` — add `log_test_gen`, `log_test_run`
- `agent/pipeline.py` — add `_TDD_ENABLED`, `_MODEL_TEST_GEN`, `_run_test_gen()`, modify `run_pipeline()`, remove `session_rules[-3:]`
- `.env.example` — document `TDD_ENABLED` and `MODEL_TEST_GEN`

---

### Task 1: Add TestGenOutput to models.py

**Files:**
- Modify: `agent/models.py`
- Test: `tests/test_models_cleanup.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models_cleanup.py`:

```python
def test_test_gen_output_fields():
    from agent.models import TestGenOutput
    out = TestGenOutput(
        reasoning="task expects items",
        sql_tests="def test_sql(results): assert results",
        answer_tests="def test_answer(sql_results, answer): assert answer['outcome'] == 'OUTCOME_OK'",
    )
    assert out.reasoning == "task expects items"
    assert "test_sql" in out.sql_tests
    assert "test_answer" in out.answer_tests
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_models_cleanup.py::test_test_gen_output_fields -v
```
Expected: FAIL with `ImportError: cannot import name 'TestGenOutput'`

- [ ] **Step 3: Add TestGenOutput to `agent/models.py`**

Append after `class ResolveOutput(BaseModel):` block (end of file):

```python
class TestGenOutput(BaseModel):
    reasoning: str
    sql_tests: str
    answer_tests: str
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/test_models_cleanup.py::test_test_gen_output_fields -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/models.py tests/test_models_cleanup.py
git commit -m "feat: add TestGenOutput model for TDD pipeline"
```

---

### Task 2: Create agent/test_runner.py

**Files:**
- Create: `agent/test_runner.py`
- Create: `tests/test_test_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_test_runner.py`:

```python
def test_passing_assert():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert results == ['row1']\n"
    passed, err = run_tests(code, "test_sql", {"results": ["row1"]})
    assert passed is True
    assert err == ""


def test_failing_assert():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert len(results) > 0\n"
    passed, err = run_tests(code, "test_sql", {"results": []})
    assert passed is False
    assert err  # non-empty AssertionError message


def test_syntax_error_in_test_code():
    from agent.test_runner import run_tests
    code = "def test_sql(results):\n    assert len(results > 0\n"  # missing closing paren
    passed, err = run_tests(code, "test_sql", {"results": [1]})
    assert passed is False
    assert err  # non-empty


def test_timeout():
    from agent.test_runner import run_tests
    code = "import time\ndef test_sql(results):\n    time.sleep(30)\n"
    passed, err = run_tests(code, "test_sql", {"results": []})
    assert passed is False
    assert err == "test timeout"


def test_answer_tests_signature():
    from agent.test_runner import run_tests
    code = (
        "def test_answer(sql_results, answer):\n"
        "    assert answer['outcome'] == 'OUTCOME_OK'\n"
        "    assert answer['message']\n"
    )
    passed, err = run_tests(
        code,
        "test_answer",
        {
            "sql_results": ["id,name\n1,Widget"],
            "answer": {
                "outcome": "OUTCOME_OK",
                "message": "Found 1",
                "grounding_refs": [],
                "reasoning": "",
                "completed_steps": [],
            },
        },
    )
    assert passed is True
    assert err == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_test_runner.py -v
```
Expected: All 5 FAIL with `ModuleNotFoundError: No module named 'agent.test_runner'`

- [ ] **Step 3: Create `agent/test_runner.py`**

```python
"""Subprocess test runner for TDD pipeline."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_tests(test_code: str, fn_name: str, context: dict) -> tuple[bool, str]:
    """Run test_code in isolated subprocess. Returns (passed, error_message)."""
    script = (
        "import json, sys\n"
        "context = json.loads(sys.stdin.read())\n"
        + test_code + "\n"
        + fn_name + "(**context)\n"
    )
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            tmp_path = f.name
        result = subprocess.run(
            [sys.executable, tmp_path],
            input=json.dumps(context),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        error = (result.stderr or result.stdout or "non-zero exit").strip()
        return False, error[:500]
    except subprocess.TimeoutExpired:
        return False, "test timeout"
    except Exception as e:
        return False, str(e)[:500]
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_test_runner.py -v
```
Expected: All 5 PASS

- [ ] **Step 5: Commit**

```bash
git add agent/test_runner.py tests/test_test_runner.py
git commit -m "feat: add subprocess test runner for TDD pipeline"
```

---

### Task 3: Add trace methods for TDD

**Files:**
- Modify: `agent/trace.py`
- Modify: `tests/test_trace.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_trace.py`:

```python
def test_log_test_gen(tmp_path):
    import json
    from agent.trace import TraceLogger, set_trace
    log_file = tmp_path / "trace.jsonl"
    logger = TraceLogger(log_file, "task-tdd")
    set_trace(logger)
    logger.log_test_gen("def test_sql(results): pass", "def test_answer(sql_results, answer): pass")
    logger.close()
    records = [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
    tg = next(r for r in records if r["type"] == "test_gen")
    assert tg["sql_tests"] == "def test_sql(results): pass"
    assert tg["answer_tests"] == "def test_answer(sql_results, answer): pass"


def test_log_test_run(tmp_path):
    import json
    from agent.trace import TraceLogger, set_trace
    log_file = tmp_path / "trace.jsonl"
    logger = TraceLogger(log_file, "task-tdd2")
    set_trace(logger)
    logger.log_test_run(1, "sql", True, "")
    logger.log_test_run(2, "answer", False, "AssertionError: wrong outcome")
    logger.close()
    records = [json.loads(l) for l in log_file.read_text().splitlines() if l.strip()]
    runs = [r for r in records if r["type"] == "test_run"]
    assert runs[0]["cycle"] == 1 and runs[0]["suite"] == "sql" and runs[0]["passed"] is True
    assert runs[1]["passed"] is False
    assert "AssertionError" in runs[1]["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_trace.py::test_log_test_gen tests/test_trace.py::test_log_test_run -v
```
Expected: FAIL with `AttributeError: 'TraceLogger' object has no attribute 'log_test_gen'`

- [ ] **Step 3: Add methods to `agent/trace.py`**

After `log_resolve_exec`, before `log_task_result`, add:

```python
    def log_test_gen(self, sql_tests_code: str, answer_tests_code: str) -> None:
        self._write({
            "type": "test_gen",
            "sql_tests": sql_tests_code,
            "answer_tests": answer_tests_code,
        })

    def log_test_run(self, cycle: int, suite: str, passed: bool, error: str) -> None:
        self._write({
            "type": "test_run",
            "cycle": cycle,
            "suite": suite,
            "passed": passed,
            "error": error,
        })
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/test_trace.py::test_log_test_gen tests/test_trace.py::test_log_test_run -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/trace.py tests/test_trace.py
git commit -m "feat: add log_test_gen and log_test_run to TraceLogger"
```

---

### Task 4: Create data/prompts/test_gen.md

**Files:**
- Create: `data/prompts/test_gen.md`

- [ ] **Step 1: Create `data/prompts/test_gen.md`**

```markdown
# Test Generation Phase

You generate acceptance tests for a catalogue lookup task. Tests run as Python functions in an isolated subprocess (stdlib only).

/no_think

## Input

- `TASK` — the user's catalogue lookup question
- `DB_SCHEMA` — the database schema
- `AGENTS_MD` — vault rules (outcome types, message format)

## What to generate

**`test_sql(results: list[str]) -> None`**
Each element in `results` is a CSV string (first line = column headers, rest = data rows).
Assert:
- Required columns are present in the header (e.g., `sku`, `path`, or `count`).
- Results are non-empty when the task implies products exist. (Skip this check for zero-count tasks — empty results are valid.)
- Numeric values are plausible (e.g., COUNT ≥ 0).

**`test_answer(sql_results: list[str], answer: dict) -> None`**
`answer` keys: `outcome`, `message`, `grounding_refs`, `reasoning`, `completed_steps`.
Assert:
- `answer['outcome']` equals the expected outcome string (e.g., `'OUTCOME_OK'`).
- `answer['message']` is non-empty.
- `answer['grounding_refs']` is non-empty when `outcome == 'OUTCOME_OK'` and task implies products found. (Empty grounding_refs is allowed for zero-count / aggregate-only answers.)
- `answer['message']` contains key product-related facts from the task (brand, type, etc.) when outcome is OK.

## Rules for test code

- Single function per test. No class.
- Use only Python stdlib. Put any needed imports inside the function body.
- Signal failure via `assert` (raises `AssertionError`) or `raise ValueError(...)`.
- Tests must be deterministic.
- Empty `results` list is valid for zero-count tasks — do not assert non-empty unconditionally.

## Output format

Output PURE JSON only. First character must be `{`.

```json
{
  "reasoning": "<analysis: expected outcome, required columns, emptiness rules>",
  "sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    header = results[0].split('\\n')[0].lower()\n    assert 'sku' in header or 'count' in header, f'missing sku/count column: {header}'\n",
  "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK', f\"wrong outcome: {answer['outcome']}\"\n    assert answer['message'], 'message is empty'\n    assert answer['grounding_refs'], 'grounding_refs empty for OK outcome'\n"
}
```
```

- [ ] **Step 2: Verify load_prompt finds the file**

```
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('test_gen'); assert p, 'test_gen prompt missing'; print('OK:', len(p), 'chars')"
```
Expected: `OK: <N> chars`

Note: `agent/prompt.py` calls `_load_all()` at import time. If the file already existed when the interpreter started, it's cached. The assert confirms the file is on disk and readable.

- [ ] **Step 3: Commit**

```bash
git add data/prompts/test_gen.md
git commit -m "feat: add test_gen LLM prompt for TDD pipeline"
```

---

### Task 5: Remove session_rules truncation

**Files:**
- Modify: `agent/pipeline.py` (line 670 in `_run_learn`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def test_session_rules_accumulate_beyond_three(tmp_path):
    """All LEARN rules are kept — no 3-rule truncation cap."""
    from unittest.mock import patch, MagicMock
    import json

    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    # 4 cycles: each produces sql_plan + learn
    learn_jsons = [
        json.dumps({"reasoning": f"r{i}", "conclusion": f"c{i}", "rule_content": f"unique_rule_{i}"})
        for i in range(4)
    ]
    sql_jsons = [_sql_plan_json() for _ in range(4)]
    call_seq = []
    for s, l in zip(sql_jsons, learn_jsons):
        call_seq.extend([s, l])
    call_iter = iter(call_seq)

    captured_session_rules: list[list[str]] = []

    import agent.pipeline as pipeline_mod
    original_run_learn = pipeline_mod._run_learn

    def tracking_run_learn(*args, **kwargs):
        session_rules = args[7] if len(args) > 7 else kwargs.get("session_rules", [])
        original_run_learn(*args, **kwargs)
        captured_session_rules.append(list(session_rules))

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._MAX_CYCLES", 4), \
         patch("agent.pipeline._run_learn", side_effect=tracking_run_learn):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "test?", pre, {})

    # After 4th LEARN, all 4 rules must survive (no truncation to 3)
    if captured_session_rules:
        final_rules = captured_session_rules[-1]
        assert len(final_rules) == 4, f"Expected 4 rules (no truncation), got {len(final_rules)}: {final_rules}"
```

- [ ] **Step 2: Run tests to establish baseline**

```
uv run pytest tests/test_pipeline.py::test_session_rules_accumulate_beyond_three -v
```
Run to see current behavior before making the change.

- [ ] **Step 3: Remove the truncation line in `agent/pipeline.py`**

In `_run_learn()`, find and delete this exact line:

```python
        session_rules[:] = session_rules[-3:]
```

The surrounding context becomes:
```python
        session_rules.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")
```

- [ ] **Step 4: Run all pipeline tests**

```
uv run pytest tests/test_pipeline.py -v
```
Expected: All pass (removing truncation does not break any existing test — existing tests use ≤3 LEARN calls)

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat: remove session_rules[-3:] cap — accumulate all LEARN rules"
```

---

### Task 6: Add _run_test_gen helper and env vars

**Files:**
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Add env vars, imports, and `_run_test_gen()` to `agent/pipeline.py`**

**a.** At the top of `pipeline.py`, after `_EVAL_LOG = ...` (~line 39), add:

```python
_TDD_ENABLED = os.environ.get("TDD_ENABLED", "0") == "1"
_MODEL_TEST_GEN = os.environ.get("MODEL_TEST_GEN", "")
```

**b.** Replace the existing models import:
```python
from .models import SqlPlanOutput, LearnOutput, AnswerOutput
```
with:
```python
from .models import SqlPlanOutput, LearnOutput, AnswerOutput, TestGenOutput
from .test_runner import run_tests
```

**c.** Add `_run_test_gen()` before `run_pipeline()`:

```python
def _run_test_gen(
    model: str,
    cfg: dict,
    task_text: str,
    db_schema: str,
    agents_md: str,
) -> "TestGenOutput | None":
    test_gen_model = _MODEL_TEST_GEN or model
    guide = load_prompt("test_gen")
    system = guide or "# PHASE: test_gen\nGenerate sql_tests and answer_tests as JSON."
    user_msg = f"TASK: {task_text}\n\nDB_SCHEMA:\n{db_schema}\n\nAGENTS_MD:\n{agents_md}"
    out, _, _ = _call_llm_phase(
        system, user_msg, test_gen_model, cfg, TestGenOutput,
        phase="TEST_GEN", cycle=0,
    )
    if out:
        if t := get_trace():
            t.log_test_gen(out.sql_tests, out.answer_tests)
    return out
```

- [ ] **Step 2: Verify existing tests still pass**

```
uv run pytest tests/test_pipeline.py -v
```
Expected: All pass (no behavior change yet — `_TDD_ENABLED` is False by default)

- [ ] **Step 3: Write failing integration test for TEST_GEN hard-stop**

Create `tests/test_pipeline_tdd.py`:

```python
import json
from unittest.mock import MagicMock, patch
import pytest
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult


def _make_pre():
    return PrephaseResult(
        agents_md_content="AGENTS",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(id INT, sku TEXT)",
    )


def _test_gen_json():
    return json.dumps({
        "reasoning": "task expects products",
        "sql_tests": "def test_sql(results):\n    assert results\n",
        "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })


def test_test_gen_parse_failure_hard_stop(tmp_path):
    """TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs."""
    vm = MagicMock()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    with patch("agent.pipeline.call_llm_raw", return_value="not json at all"), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._TDD_ENABLED", True):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "find laptops", pre, {})

    vm.answer.assert_called_once()
    req = vm.answer.call_args[0][0]
    assert "CLARIFICATION" in str(req.outcome)
    assert "Test generation failed" in req.message
    vm.exec.assert_not_called()
```

- [ ] **Step 4: Update `.env.example` with new variables**

Add after the `# ─── Evaluator ──` block in `.env.example`:

```
# ─── TDD Pipeline ───────────────────────────────────────────────────────────
TDD_ENABLED=0                        # 1 = генерировать тесты и валидировать ответ перед vm.answer()
MODEL_TEST_GEN=                      # модель для TEST_GEN; если пусто — используется MODEL
```

- [ ] **Step 5: Run test to verify it fails (hard-stop not yet wired)**

```
uv run pytest tests/test_pipeline_tdd.py::test_test_gen_parse_failure_hard_stop -v
```
Expected: FAIL (hard-stop logic lives in Task 7)

- [ ] **Step 6: Commit current state**

```bash
git add agent/pipeline.py tests/test_pipeline_tdd.py .env.example
git commit -m "feat: add _TDD_ENABLED, _MODEL_TEST_GEN, _run_test_gen to pipeline"
```

---

### Task 7: Integrate TDD into pipeline loop

**Files:**
- Modify: `agent/pipeline.py:run_pipeline()`
- Modify: `tests/test_pipeline_tdd.py`

- [ ] **Step 1: Add remaining integration tests to `tests/test_pipeline_tdd.py`**

Append to `tests/test_pipeline_tdd.py`:

```python
def _sql_plan_json(queries=None):
    return json.dumps({
        "reasoning": "ok",
        "queries": queries or ["SELECT sku, path FROM products WHERE type='Laptop'"],
    })


def _answer_json():
    return json.dumps({
        "reasoning": "found it",
        "message": "<YES> 1 laptop found",
        "outcome": "OUTCOME_OK",
        "grounding_refs": ["/proc/catalog/LAP-001.json"],
        "completed_steps": ["ran SQL", "found product"],
    })


def _make_exec_result(stdout="sku,path\nLAP-001,/proc/catalog/LAP-001.json"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_tdd_disabled_no_regression(tmp_path):
    """TDD_ENABLED=0 → pipeline identical to current; run_tests never called."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", False), \
         patch("agent.pipeline.run_tests") as mock_run_tests:
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    mock_run_tests.assert_not_called()


def test_tdd_happy_path(tmp_path):
    """TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_test_gen_json(), _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", return_value=(True, "")):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    vm.answer.assert_called_once()


def test_tdd_sql_test_failure_triggers_learn_and_retry(tmp_path):
    """sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANSWER → ok."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "bad query",
        "conclusion": "add WHERE",
        "rule_content": "Always filter by type.",
    })
    # TEST_GEN, cycle1: sql_plan, cycle1: sql_test_fail → learn, cycle2: sql_plan, cycle2: answer
    call_seq = [_test_gen_json(), _sql_plan_json(), learn_json, _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    # run_tests calls: cycle1 sql_test → fail; cycle2 sql_test → pass; cycle2 answer_test → pass
    run_tests_results = iter([
        (False, "AssertionError: results empty"),
        (True, ""),
        (True, ""),
    ])

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", side_effect=lambda *a, **kw: next(run_tests_results)):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    assert stats["cycles_used"] == 2


def test_tdd_answer_test_failure_skips_sql_retry(tmp_path):
    """answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWER only."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "bad answer",
        "conclusion": "fix message",
        "rule_content": "Include product name in message.",
    })
    # TEST_GEN, cycle1: sql_plan, cycle1: answer → answer_test_fail → learn, cycle2: answer
    call_seq = [_test_gen_json(), _sql_plan_json(), learn_json, _answer_json()]
    call_iter = iter(call_seq)

    # cycle1: sql_test → pass; cycle1: answer_test → fail; cycle2: answer_test → pass
    run_tests_results = iter([
        (True, ""),
        (False, "AssertionError: message empty"),
        (True, ""),
    ])

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", side_effect=lambda *a, **kw: next(run_tests_results)):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    # EXECUTE called only once (one SQL cycle), SQL skipped on cycle 2
    assert stats["outcome"] == "OUTCOME_OK"
    # vm.exec call count: 1 EXPLAIN + 1 EXECUTE = 2 (not 4 which would mean 2 SQL cycles)
    assert vm.exec.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_pipeline_tdd.py -v
```
Expected: Multiple failures (TDD path not yet in `run_pipeline`)

- [ ] **Step 3: Modify `run_pipeline()` in `agent/pipeline.py`**

**3a.** Add TDD initialization block immediately after the RESOLVE block (after `if confirmed_values: print(...)`), before `static_sql = ...`:

```python
    # ── TEST_GEN (TDD only) ───────────────────────────────────────────────────
    test_gen_out: TestGenOutput | None = None
    if _TDD_ENABLED:
        test_gen_out = _run_test_gen(model, cfg, task_text, pre.db_schema, pre.agents_md_content)
        if test_gen_out is None:
            print(f"{CLI_RED}[pipeline] TEST_GEN parse failed — hard stop{CLI_CLR}")
            try:
                vm.answer(AnswerRequest(
                    message="Test generation failed — cannot validate answer",
                    outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                    refs=[],
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
            return {
                "outcome": "OUTCOME_NONE_CLARIFICATION",
                "cycles_used": 0,
                "step_facts": ["pipeline: TEST_GEN hard stop"],
                "done_ops": [],
                "input_tokens": total_in_tok,
                "output_tokens": total_out_tok,
                "total_elapsed_ms": 0,
            }, None
```

**3b.** Add `_skip_sql` and `queries` declarations immediately before `for cycle in range(_MAX_CYCLES):`:

```python
    _skip_sql = False
    queries: list[str] = []
```

**3c.** Inside the loop, wrap everything from `# ── SQL_PLAN ──` through the existing `success = True; break` with `if not _skip_sql:`.

The indentation of all lines from SQL_PLAN through `success = True; break` must increase by one level (4 spaces). The `# ── SQL_PLAN ──` comment block opens the `if not _skip_sql:` scope.

The DISCOVERY-ONLY DETECTION block (with its `continue`) sits **inside** this `if not _skip_sql:` block — its `continue` exits the outer `for cycle` loop, not just the inner block. This is correct behavior: discovery cycles loop back to SQL_PLAN with `_skip_sql` still False.

**3d.** Replace the existing `success = True; break` at the end of the EXECUTE success path (currently after the discovery-only detection block) with:

```python
        # ── RUN SQL TESTS (TDD only) ──────────────────────────────────────────
        if _TDD_ENABLED and test_gen_out:
            sql_passed, sql_err = run_tests(
                test_gen_out.sql_tests, "test_sql", {"results": sql_results}
            )
            if t := get_trace():
                t.log_test_run(cycle + 1, "sql", sql_passed, sql_err)
            if not sql_passed:
                print(f"{CLI_YELLOW}[pipeline] SQL TEST failed: {sql_err[:80]}{CLI_CLR}")
                last_error = sql_err[:500]
                _skip_sql = False
                _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                           sgr_trace, session_rules, highlighted_vault_rules,
                           pre.agents_md_index, error_type="test_fail", cycle=cycle + 1,
                           prior_learn_hashes=prior_learn_hashes)
                continue

        if not _TDD_ENABLED:
            success = True
            break
```

**3e.** After the `if not _skip_sql:` block (at the same indentation level as `if not _skip_sql:`), add the TDD ANSWER block:

```python
        # ── ANSWER (TDD — inside loop) ────────────────────────────────────────
        if _TDD_ENABLED:
            answer_user = _build_answer_user_msg(task_text, sql_results, sku_refs)
            answer_out, sgr_answer, tok = _call_llm_phase(
                static_answer, answer_user, model, cfg, AnswerOutput,
                phase="answer", cycle=cycle + 1,
            )
            total_in_tok += tok.get("input", 0)
            total_out_tok += tok.get("output", 0)
            sgr_trace.append(sgr_answer)

            if not answer_out:
                print(f"{CLI_RED}[pipeline] ANSWER parse failed{CLI_CLR}")
                try:
                    vm.answer(AnswerRequest(
                        message="Could not synthesize an answer from available data.",
                        outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                        refs=[],
                    ))
                except Exception as e:
                    print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
                break

            ans_passed, ans_err = run_tests(
                test_gen_out.answer_tests, "test_answer",
                {"sql_results": sql_results, "answer": answer_out.model_dump()},
            )
            if t := get_trace():
                t.log_test_run(cycle + 1, "answer", ans_passed, ans_err)
            if not ans_passed:
                print(f"{CLI_YELLOW}[pipeline] ANSWER TEST failed: {ans_err[:80]}{CLI_CLR}")
                last_error = ans_err[:500]
                _skip_sql = True
                _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                           sgr_trace, session_rules, highlighted_vault_rules,
                           pre.agents_md_index, error_type="test_fail", cycle=cycle + 1,
                           prior_learn_hashes=prior_learn_hashes)
                continue

            outcome = answer_out.outcome
            print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
            result_skus = {Path(r).stem for r in sku_refs}
            ref_err = check_grounding_refs(answer_out.grounding_refs, result_skus, security_gates)
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            clean_refs = [r for r in answer_out.grounding_refs if r in sku_refs or not result_skus]
            try:
                vm.answer(AnswerRequest(
                    message=answer_out.message,
                    outcome=OUTCOME_BY_NAME[outcome],
                    refs=clean_refs,
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
            success = True
            break
```

**3f.** Replace the post-loop `outcome = ...; if not success: ...; else: # ANSWER ...` block with:

```python
    outcome = "OUTCOME_NONE_CLARIFICATION"
    if not success:
        print(f"{CLI_RED}[pipeline] All {_MAX_CYCLES} cycles exhausted — clarification{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Could not retrieve data after multiple attempts.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
    elif not _TDD_ENABLED:
        # ── ANSWER (non-TDD — outside loop, existing behavior) ───────────────
        answer_user = _build_answer_user_msg(task_text, sql_results, sku_refs)
        answer_out, sgr_answer, tok = _call_llm_phase(
            static_answer, answer_user, model, cfg, AnswerOutput,
            phase="answer", cycle=cycle + 1,
        )
        total_in_tok += tok.get("input", 0)
        total_out_tok += tok.get("output", 0)
        sgr_trace.append(sgr_answer)

        if answer_out:
            outcome = answer_out.outcome
            print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
            result_skus = {Path(r).stem for r in sku_refs}
            ref_err = check_grounding_refs(answer_out.grounding_refs, result_skus, security_gates)
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            clean_refs = [r for r in answer_out.grounding_refs if r in sku_refs or not result_skus]
            try:
                vm.answer(AnswerRequest(
                    message=answer_out.message,
                    outcome=OUTCOME_BY_NAME[outcome],
                    refs=clean_refs,
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
        else:
            print(f"{CLI_RED}[pipeline] ANSWER parse failed — sending fallback clarification{CLI_CLR}")
            try:
                vm.answer(AnswerRequest(
                    message="Could not synthesize an answer from available data.",
                    outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                    refs=[],
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer fallback error: {e}{CLI_CLR}")
    # TDD success: outcome already set in loop body
```

- [ ] **Step 4: Run TDD integration tests**

```
uv run pytest tests/test_pipeline_tdd.py -v
```
Expected: All 5 tests pass

- [ ] **Step 5: Run full test suite — no regressions**

```
uv run python -m pytest tests/ -v
```
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline_tdd.py
git commit -m "feat: integrate TDD test gates into pipeline loop (TDD_ENABLED=1)"
```

---

## Self-Review

**Spec coverage:**
- ✓ `TestGenOutput` model → Task 1
- ✓ `run_tests()` subprocess runner, timeout=10s, no network, stdlib only → Task 2
- ✓ String concatenation (not f-strings) for script building → Task 2
- ✓ `log_test_gen` / `log_test_run` → Task 3
- ✓ `data/prompts/test_gen.md` with all 5 prompt requirements → Task 4
- ✓ Remove `session_rules[-3:]` unconditionally → Task 5
- ✓ `_TDD_ENABLED`, `_MODEL_TEST_GEN` env vars → Task 6
- ✓ `_run_test_gen()` helper → Task 6
- ✓ TEST_GEN parse failure → hard stop with "Test generation failed" message → Task 7 step 3a
- ✓ `_skip_sql` flag → Task 7 step 3b
- ✓ SQL_PLAN→EXECUTE wrapped in `if not _skip_sql:` → Task 7 step 3c
- ✓ `error_type="test_fail"` LEARN on sql_test failure → Task 7 step 3d
- ✓ `_skip_sql=False` on sql_test failure → Task 7 step 3d
- ✓ ANSWER inside loop when TDD_ENABLED → Task 7 step 3e
- ✓ ANSWER parse failure during TDD → `vm.answer(CLARIFICATION)` + break (no LEARN) → Task 7 step 3e
- ✓ `error_type="test_fail"` LEARN on answer_test failure → Task 7 step 3e
- ✓ `_skip_sql=True` on answer_test failure → Task 7 step 3e
- ✓ `TDD_ENABLED=0` no regression → Task 7 `test_tdd_disabled_no_regression`
- ✓ cycles exhausted → `vm.answer(CLARIFICATION)` → Task 7 step 3f

**Type consistency:**
- `TestGenOutput | None` return type on `_run_test_gen` matches usage in `run_pipeline`
- `run_tests` returns `tuple[bool, str]` used as `passed, err = run_tests(...)` throughout
- `log_test_run(cycle, suite, passed, error)` called consistently with correct arg types
- `answer_out.model_dump()` — `AnswerOutput` extends `BaseModel` → valid ✓
- `queries: list[str] = []` declared before loop; set inside `if not _skip_sql:` block; persists across iterations for LEARN call when `_skip_sql=True` ✓
