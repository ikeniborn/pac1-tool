# TDD Logging & Test Quality — Design Spec

**Date:** 2026-05-14  
**Status:** Approved  
**Scope:** Observability improvements for TDD pipeline + test_gen anti-pattern prevention

---

## Problem

When `test_run` events fail (sql or answer suite), the JSONL trace contains the traceback but NOT the context passed to the test function. This makes root-cause analysis impossible from logs alone.

**Concrete example (t10, cycle 3–7):** `test_answer` asserts `'Cordless Drill Driver' in answer['message']` and fails 5 consecutive cycles. The log shows the assertion error but not what `answer['message']` actually contained — the pipeline burns 5 cycles retrying SQL when the real problem is a brittle hardcoded string in the generated test.

**Secondary problem:** `test_gen.md` prompt does not explicitly prohibit exact-string matching of task literals, so LLMs generate fragile tests by default. Two anti-patterns found in t10:
- `assert 'Cordless Drill Driver' in answer['message']` — exact product name from task
- `assert 'count' in header` — hardcoded column alias; SQL used `total` instead

---

## Design

### 1. `trace.py` — context_snapshot in test_run events

Add optional `context_snapshot: str = ""` to `log_test_run`. Callers pass `json.dumps(context)[:3000]`.

```python
def log_test_run(
    self,
    cycle: int,
    suite: str,
    passed: bool,
    error: str,
    context_snapshot: str = "",
) -> None:
    self._write({
        "type": "test_run",
        "cycle": cycle,
        "suite": suite,
        "passed": passed,
        "error": error,
        "context_snapshot": context_snapshot,
    })
```

Resulting log entry gains `context_snapshot` field — truncated JSON of `results` (sql suite) or `{"sql_results": ..., "answer": ...}` (answer suite). Cap 3000 chars to bound log size.

### 2. `test_runner.py` — full error + task_text warning scan

**Error truncation:** Increase the `error[:500]` limit in `run_tests` to `error[:2000]`. The 500-char truncation in `last_error` (passed to LLM) stays in `pipeline.py` — pipeline truncates to 500 before feeding to LLM. No signature change needed.

**Warning scan:** Add `_check_tdd_antipatterns(test_code: str, task_text: str) -> list[str]` as a module-level helper. Call it inside `run_tests` before the subprocess, return warnings as a third tuple element: `(passed, error, warnings)`.

```python
import re

def _check_tdd_antipatterns(test_code: str, task_text: str) -> list[str]:
    warnings = []
    # Hardcoded task literal in answer['message'] assert
    for lit in re.findall(r"assert\s+['\"]([^'\"]+)['\"]\s+in\s+answer\[", test_code):
        if lit in task_text:
            warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    # Hardcoded column name in SQL header assert (e.g. assert 'count' in header)
    for col in re.findall(r"assert\s+['\"]([^'\"]+)['\"]\s+in\s+header", test_code):
        warnings.append(f"hardcoded column alias in sql header assert: '{col}' — use numeric type check instead")
    return warnings


def run_tests(test_code: str, fn_name: str, context: dict, task_text: str = "") -> tuple[bool, str, list[str]]:
    warnings = _check_tdd_antipatterns(test_code, task_text) if task_text else []
    # ... existing subprocess logic, error[:2000] ...
    return passed, error, warnings
```

### 3. `pipeline.py` — wire context_snapshot and warnings

All call sites unpack 3-tuple `(passed, err, warnings)`. Truncate `err` to 500 when feeding `last_error` to LLM.

**SQL suite:**
```python
sql_passed, sql_err, sql_warns = run_tests(
    test_gen_out.sql_tests, "test_sql", {"results": sql_results},
    task_text=task_text,
)
if t := get_trace():
    t.log_test_run(
        cycle + 1, "sql", sql_passed, sql_err,
        context_snapshot=json.dumps({"results": sql_results})[:3000],
    )
    if sql_warns:
        t._write({"type": "tdd_warning", "suite": "sql", "warnings": sql_warns})
if sql_warns:
    print(f"{CLI_YELLOW}[TDD WARNING] sql: {sql_warns}{CLI_CLR}")
if not sql_passed:
    last_error = sql_err[:500]
    ...
```

**Answer suite:**
```python
ans_passed, ans_err, ans_warns = run_tests(
    test_gen_out.answer_tests, "test_answer",
    {"sql_results": sql_results, "answer": answer_out.model_dump()},
    task_text=task_text,
)
if t := get_trace():
    snapshot = json.dumps({
        "answer": answer_out.model_dump(),
        "sql_results": sql_results,
    })[:3000]
    t.log_test_run(cycle + 1, "answer", ans_passed, ans_err, context_snapshot=snapshot)
    if ans_warns:
        t._write({"type": "tdd_warning", "suite": "answer", "warnings": ans_warns})
if ans_warns:
    print(f"{CLI_YELLOW}[TDD WARNING] answer: {ans_warns}{CLI_CLR}")
```

### 4. `data/prompts/test_gen.md` — anti-patterns section

Add to "Rules for test code":

```markdown
## Anti-patterns — never do this

**BAD** — exact string from task, case-sensitive:
```python
assert 'Cordless Drill Driver' in answer['message']
```

**GOOD** — case-insensitive, partial keyword check:
```python
msg = answer['message'].lower()
assert 'cordless' in msg or 'drill' in msg, f'missing product type: {msg[:200]}'
```

Rules:
- Never assert exact product names/brands copied from TASK text.
- Use `.lower()` + individual keyword checks for product presence.
- For COUNT tasks: check `<COUNT:` format, not the numeric value.
- Include the actual value in the assertion message for easier debugging.
- Never hardcode a specific column alias (e.g. `'count'`, `'total'`) in SQL header checks. Instead verify the result has at least one numeric-looking column: `assert any(c.strip().isdigit() or results[1:] for ...)` or simply check `results` is non-empty with plausible row count.
```

---

## Files Changed

| File | Change |
|------|--------|
| `agent/trace.py` | `log_test_run` gains `context_snapshot: str = ""` |
| `agent/test_runner.py` | `run_tests` signature: `task_text: str = ""`, returns `(bool, str, list[str])`; error limit 2000; add `_check_tdd_antipatterns` |
| `agent/pipeline.py` | Pass `context_snapshot` and `task_text` at both `run_tests` call sites; log `tdd_warning` events |
| `data/prompts/test_gen.md` | Add anti-patterns section |

---

## Success Criteria

- After a `test_run` failure, `context_snapshot` in the JSONL event shows the actual `answer['message']` value
- Pipeline prints `[TDD WARNING]` to terminal when anti-pattern detected in generated test
- Unit test: `_check_tdd_antipatterns` returns warning for code with hardcoded product literal and for hardcoded column alias
- `test_gen.md` anti-patterns section present with both bad/good examples (product name + column alias)
- No regressions in existing tests (`uv run pytest tests/ -v`)
