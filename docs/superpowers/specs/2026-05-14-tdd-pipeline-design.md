# TDD Pipeline: Test Generation and Validation

**Date:** 2026-05-14  
**Status:** Approved

## Overview

Add a TDD step to the agent pipeline: before SQL planning, a separate LLM call generates Python acceptance tests from the task description. Tests run in an isolated subprocess after SQL execution (sql_tests) and after answer synthesis (answer_tests). The answer is sent to `vm.answer()` only if both test suites pass.

## Goals

- Validate SQL result correctness against business rules before synthesizing the answer.
- Validate answer correctness (outcome, message, grounding_refs) before sending.
- Use the existing LEARN mechanism to correct failures — no new retry machinery.
- Feature is opt-in; zero impact on existing pipeline when disabled.

## Non-Goals

- Persistent test storage across runs.
- Tests written to disk or version-controlled.
- Replacing existing security/schema gates.

---

## Pipeline Flow

```
RESOLVE
→ TEST_GEN  [once, if TDD_ENABLED=1, model MODEL_TEST_GEN]
  input:  task_text + db_schema + agents_md
  output: TestGenOutput { sql_tests: str, answer_tests: str }

→ _skip_sql = False

→ [cycle × MAX_STEPS]:

    if not _skip_sql:
        SQL_PLAN → AGENTS.MD check → SECURITY → SCHEMA → VALIDATE → EXECUTE
        → any failure → LEARN(error_type=...) → _skip_sql=False → continue

        RUN_SQL_TESTS(sql_results)          [subprocess, timeout=10s]
        → failure → LEARN(error_type="test_fail") → _skip_sql=False → continue

    ANSWER
    → parse failure → vm.answer(OUTCOME_NONE_CLARIFICATION) → break

    RUN_ANSWER_TESTS(sql_results, answer)   [subprocess, timeout=10s]
    → failure → LEARN(error_type="test_fail") → _skip_sql=True → continue

    vm.answer(answer) → break

→ cycles exhausted → vm.answer(OUTCOME_NONE_CLARIFICATION)
```

**Smart retry logic:**
- `sql_tests` failure → `_skip_sql=False` → next cycle redoes SQL_PLAN from scratch.
- `answer_tests` failure → `_skip_sql=True` → next cycle skips SQL, reruns ANSWER only with same `sql_results`.

**When `TDD_ENABLED=0`:** ANSWER stays outside the cycle loop (current behavior). No regression.

---

## Session Rules: No Limit

Current code truncates session rules to last 3: `session_rules[:] = session_rules[-3:]`.

Remove the slice. With TDD, a single run may generate up to `MAX_STEPS * 2` LEARN calls (sql_test fail + answer_test fail per cycle). Dropping earlier rules causes the model to repeat corrected mistakes.

Change: `session_rules[:] = session_rules[-3:]` → delete line, accumulate all rules.

---

## New Components

### `agent/models.py` — TestGenOutput

```python
class TestGenOutput(BaseModel):
    reasoning: str
    sql_tests: str    # Python code: def test_sql(results: list[str]) -> None
    answer_tests: str # Python code: def test_answer(sql_results: list[str], answer: dict) -> None
```

### `agent/test_runner.py` — subprocess runner

```python
def run_tests(test_code: str, fn_name: str, context: dict) -> tuple[bool, str]:
    """
    Writes a self-contained Python script to a temp file.
    Script: imports json, reads stdin as context, calls fn_name(**context).
    Runs in subprocess with timeout=10s, no network, stdlib only.
    Returns (passed: bool, error_message: str).
    """
```

The generated test code must be a standalone function. The runner wraps it with:

```python
import json, sys
context = json.loads(sys.stdin.read())
{test_code}
{fn_name}(**context)
```

Test signals failure via `assert` (raises `AssertionError`) or `raise`. Non-zero exit = failure.

### `data/prompts/test_gen.md` — LLM prompt

Instructs the model to:
1. Analyze task_text to determine expected outcome (OUTCOME_OK / OUTCOME_NONE_*).
2. Write `test_sql(results: list[str]) -> None`: asserts required columns present, result non-empty if answer expected, values plausible.
3. Write `test_answer(sql_results: list[str], answer: dict) -> None`: asserts correct `outcome`, `message` non-empty, `grounding_refs` non-empty when outcome=OUTCOME_OK, message contains key facts from task.
4. Tests must be deterministic, use only stdlib, handle edge cases (empty results = valid for zero-count tasks).
5. Output pure JSON: `{"reasoning": "...", "sql_tests": "...", "answer_tests": "..."}`.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `TDD_ENABLED` | `0` | Enable TEST_GEN + RUN_TESTS phases |
| `MODEL_TEST_GEN` | `""` | Model for TEST_GEN. Falls back to `MODEL` if empty. |

---

## Changes to Existing Files

| File | Change |
|---|---|
| `agent/pipeline.py` | Add `_run_test_gen()`. Add `_skip_sql` flag. Move ANSWER inside cycle when TDD_ENABLED. Add RUN_SQL_TESTS and RUN_ANSWER_TESTS call sites. Remove `session_rules[-3:]` truncation. |
| `agent/models.py` | Add `TestGenOutput`. |
| `agent/test_runner.py` | New file. |
| `data/prompts/test_gen.md` | New file. |

---

## Error Handling

- `TEST_GEN` parse failure → log warning, set `sql_tests = ""` and `answer_tests = ""` → pipeline runs without tests (graceful degradation).
- `run_tests()` subprocess timeout → treat as test failure, error_message = `"test timeout"`.
- `run_tests()` exception (OS error, file write fail) → treat as test failure, log and continue.
- Test code generated by LLM may have syntax errors → caught by subprocess stderr, reported as failure.

---

## Trace Logging

Add to `trace.py`:
- `log_test_gen(cycle, sql_tests_code, answer_tests_code)` — records generated test code.
- `log_test_run(cycle, suite, passed, error)` — records test execution result (suite = "sql" | "answer").

---

## Testing the Feature

Unit tests in `tests/test_test_runner.py`:
- `run_tests` with passing assert → returns `(True, "")`.
- `run_tests` with failing assert → returns `(False, error_msg)`.
- `run_tests` with syntax error in test code → returns `(False, ...)`.
- `run_tests` with timeout → returns `(False, "test timeout")`.

Integration: `TDD_ENABLED=1 MODEL_TEST_GEN=... uv run python main.py`
