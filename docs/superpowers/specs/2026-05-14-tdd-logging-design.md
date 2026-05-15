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

### 1. `trace.py` — context_snapshot in test_run events + log_tdd_warning

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

def log_tdd_warning(self, suite: str, warnings: list[str]) -> None:
    self._write({"type": "tdd_warning", "suite": suite, "warnings": warnings})
```

Resulting log entry gains `context_snapshot` field — truncated JSON of `results` (sql suite) or `{"sql_results": ..., "answer": ...}` (answer suite). Cap 3000 chars to bound log size.

### 2. `test_runner.py` — full error + task_text warning scan

**Error truncation:** Increase the `error[:500]` limit in `run_tests` to `error[:2000]`. The 500-char truncation in `last_error` (passed to LLM) stays in `pipeline.py` — pipeline truncates to 500 before feeding to LLM. No signature change needed.

**Warning scan:** Add `_check_tdd_antipatterns(test_code: str, task_text: str = "") -> list[str]` as a module-level helper. Call it inside `run_tests` before the subprocess, return warnings as a third tuple element: `(passed, err, warnings)`.

**Existing test compatibility:** `tests/test_test_runner.py` already contains 5 tests that unpack `run_tests` as 2-tuple (`passed, err = run_tests(...)`). All 5 must be updated to 3-tuple unpack (`passed, err, _ = run_tests(...)`).

> **NOTE:** Update existing 5 tests before adding new ones — otherwise the existing suite breaks immediately.

```python
import re

# Regex: (?:[^'"\\]|\\.)* handles basic escape sequences (e.g. \', \").
# Known edge cases (acceptable for MVP):
#   False-negative: unescaped embedded opposite-quote inside string — e.g. assert "Bob's Drill" in answer[...]
#                   The [^'"\\] class stops on the embedded quote; regex fails to match.
#   False-positive: mismatched delimiters — e.g. assert 'foo" in answer[...]
#                   Opening ' and closing " both match ['"], so regex fires on invalid Python syntax.
#                   Acceptable since LLM-generated test code is expected to be syntactically valid.
_ANSWER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+answer\[""")
# _HEADER_ASSERT_RE matches `assert '<literal>' in header` only — not `in header[0]`, `in headers`,
# or any compound name. Acceptable for MVP: LLM-generated tests use plain `header` variable.
# Known edge case (acceptable for MVP):
#   False-positive: non-aggregate column names (e.g. `sku`, `path`) also match and emit a warning.
#                   These are valid for non-aggregate queries (see §4 NOTE); the warning is advisory
#                   and the message is intentionally generic to cover both aggregate and non-aggregate cases.
_HEADER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+header""")

def _check_tdd_antipatterns(test_code: str, task_text: str = "") -> list[str]:
    warnings = []
    # Hardcoded task literal in answer['message'] assert — only when task_text provided
    if task_text:
        for lit in _ANSWER_ASSERT_RE.findall(test_code):
            if lit in task_text:
                warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    # Hardcoded column name/alias in SQL header assert — always checked, task_text not needed
    for col in _HEADER_ASSERT_RE.findall(test_code):
        warnings.append(f"hardcoded string in sql header assert: '{col}' — for aggregates use row/type check; for named columns this warning may be a false-positive")
    return warnings


def run_tests(test_code: str, fn_name: str, context: dict, task_text: str = "") -> tuple[bool, str, list[str]]:
    warnings = _check_tdd_antipatterns(test_code, task_text)
    # ... existing subprocess logic ...
    error = captured_output[:2000]  # truncate here; pipeline.py further truncates to 500 for LLM
    return passed, error, warnings
```

### 3. `pipeline.py` — wire context_snapshot and warnings

All call sites unpack 3-tuple `(passed, err, warnings)`. Truncate `err` to 500 when feeding `last_error` to LLM.

**SQL suite** (`task_text` is already a parameter of `run_pipeline()` — pass it through to both call sites):
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
        t.log_tdd_warning("sql", sql_warns)
if sql_warns:
    print(f"{CLI_YELLOW}[TDD WARNING] sql: {sql_warns}{CLI_CLR}")
if not sql_passed:
    last_error = sql_err[:500]
    ...
```

**Answer suite:**
```python
ans_passed, ans_err, ans_warns = run_tests(  # task_text passed through, same as sql suite
    test_gen_out.answer_tests, "test_answer",
    {"sql_results": sql_results, "answer": answer_out.model_dump()},
    task_text=task_text,
)
if t := get_trace():
    snapshot = json.dumps({
        "sql_results": sql_results,
        "answer": answer_out.model_dump(),
    })[:3000]
    t.log_test_run(cycle + 1, "answer", ans_passed, ans_err, context_snapshot=snapshot)
    if ans_warns:
        t.log_tdd_warning("answer", ans_warns)
if ans_warns:
    print(f"{CLI_YELLOW}[TDD WARNING] answer: {ans_warns}{CLI_CLR}")
if not ans_passed:
    last_error = ans_err[:500]
    ...
```

### 4. `data/prompts/test_gen.md` — anti-patterns section

Append after the last bullet in `## Rules for test code` (before `## Output format`):

```markdown
## Anti-patterns — never do this

**BAD** — exact string from task, case-sensitive:
~~~python
assert 'Cordless Drill Driver' in answer['message']
~~~

**GOOD** — case-insensitive, partial keyword check:
~~~python
msg = answer['message'].lower()
assert 'cordless' in msg or 'drill' in msg, f'missing product type: {msg[:200]}'
~~~

Rules:
- Never assert exact product names/brands copied from TASK text.
- Use `.lower()` + individual keyword checks for product presence.
- For COUNT tasks: check `<COUNT:` format, not the numeric value.
- Include the actual value in the assertion message for easier debugging.
- Never hardcode a specific column alias (e.g. `'count'`, `'total'`) in SQL header checks. Check that results are non-empty and the first data row contains a parseable integer, not that the header contains a specific word.
```

**Also update `## What to generate`** — first `test_sql` bullet, replace:

```
- Required columns are present in the header (e.g., `sku`, `path`, or `count`).
```

→

```
- Required columns are present in the header (e.g., `sku`, `path`). For aggregate queries verify results are non-empty and the first data row contains a parseable integer — do not assert a specific column alias name.
```

**Also update `## Output format`** — replace the `sql_tests` value in the JSON example:

```json
"sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    header = results[0].split('\\n')[0].lower()\n    assert 'sku' in header or 'count' in header, f'missing sku/count column: {header}'\n",
```

→

```json
"sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    rows = results[0].split('\\n')\n    assert len(rows) > 1, 'no data rows returned'\n",
```

> **NOTE:** This example shows an aggregate query (no named column to check). For non-aggregate queries that return labelled columns (e.g. `sku`, `path`) the test may still assert `'sku' in header` — what is prohibited is hardcoding a calculated alias (`count`, `total`) that the SQL engine may name differently.

---

## Files Changed

| File | Change |
|------|--------|
| `agent/trace.py` | `log_test_run` gains `context_snapshot: str = ""`; add `log_tdd_warning(suite, warnings)` |
| `agent/test_runner.py` | `run_tests` signature: `task_text: str = ""`, returns `(bool, str, list[str])`; error limit 2000; add `_check_tdd_antipatterns`, `_ANSWER_ASSERT_RE`, `_HEADER_ASSERT_RE` |
| `agent/pipeline.py` | Pass `context_snapshot` and `task_text` at both `run_tests` call sites; call `t.log_tdd_warning(...)` |
| `data/prompts/test_gen.md` | Add anti-patterns section; update `## What to generate` first `test_sql` bullet (remove `count` from header-check example, add aggregate guidance); update `## Output format` `sql_tests` example to remove hardcoded column alias check |
| `tests/test_test_runner.py` | Existing file: update 5 existing `run_tests` call sites from 2-tuple to 3-tuple unpack (`passed, err, _ = run_tests(...)`); add new tests for `_check_tdd_antipatterns` — literal-in-task warns, any `in header` literal warns unconditionally (false-positive for `sku`/`path` is advisory, documented in §2), no-match returns empty, unescaped opposite-quote inside literal (e.g. `"Bob's Drill"`) — regex no-match, no warning emitted (false-negative documented as acceptable for MVP) |

---

## Success Criteria

- Every `test_run` JSONL event (pass or fail) contains `context_snapshot` with truncated JSON of actual context; for answer suite this includes `answer['message']`
- Pipeline prints `[TDD WARNING]` to terminal when anti-pattern detected in generated test
- JSONL trace contains `{"type": "tdd_warning", "suite": "<sql|answer>", "warnings": [...]}` event whenever `log_tdd_warning` is called; `log_tdd_warning` is called from `pipeline.py` only when warnings list is non-empty (guard in caller — `if sql_warns:` / `if ans_warns:` — not inside `log_tdd_warning` itself)
- Unit test in `tests/test_test_runner.py`: `_check_tdd_antipatterns` returns warning for code with hardcoded product literal (only when `task_text` provided and literal appears in it); returns warning for any hardcoded string in `in header` assert unconditionally (regardless of `task_text`) — note: this includes non-aggregate column names like `sku` (known false-positive, advisory only); returns empty list when neither anti-pattern present
- `test_gen.md` anti-patterns section present with both bad/good examples (product name + column alias)
- `test_run` JSONL `error` field truncated at 2000 chars (sourced from `test_runner.py`), not 500; `last_error` fed to LLM remains 500-char truncation in `pipeline.py`
- `_check_tdd_antipatterns` test suite includes a case with an unescaped opposite-quote character inside a string literal (e.g. `"Bob's Drill"`) to document the known false-negative edge case: regex does not match, no warning emitted — acceptable for MVP
- Test suite does NOT need to cover mismatched-delimiter false-positive (e.g. `assert 'foo" in answer[...]`) — invalid Python, LLMs don't generate it
- No regressions in existing tests (`uv run pytest tests/ -v`)
