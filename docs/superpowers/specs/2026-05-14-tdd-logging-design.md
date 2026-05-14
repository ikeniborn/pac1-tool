# TDD Logging & Test Quality — Design Spec

**Date:** 2026-05-14  
**Status:** Approved  
**Scope:** Observability improvements for TDD pipeline + test_gen anti-pattern prevention

---

## Problem

When `test_run` events fail (sql or answer suite), the JSONL trace contains the traceback but NOT the context passed to the test function. This makes root-cause analysis impossible from logs alone.

**Concrete example (t10, cycle 3–7):** `test_answer` asserts `'Cordless Drill Driver' in answer['message']` and fails 5 consecutive cycles. The log shows the assertion error but not what `answer['message']` actually contained — the pipeline burns 5 cycles retrying SQL when the real problem is a brittle hardcoded string in the generated test.

**Secondary problem:** `test_gen.md` prompt does not explicitly prohibit exact-string matching of task literals, so LLMs generate fragile tests by default.

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

**Error truncation:** `run_tests` currently returns `error[:500]`. The 500-char limit applies to `last_error` passed back to LLM — this is correct. But the full error should be available separately for the trace. Change signature to return `(passed, short_error, full_error)` — or keep current tuple but return full error and let pipeline truncate for `last_error` only.

Simpler alternative (no signature change): increase limit to 2000 in `run_tests`, keep truncation in pipeline for `last_error`. This is sufficient since tracebacks are rarely >2000 chars.

**Warning scan:** Accept optional `task_text: str = ""`. After writing temp file but before subprocess call, scan `test_code` for hardcoded task literals in answer assertions:

```python
import re

def _check_tdd_antipatterns(test_code: str, task_text: str) -> list[str]:
    warnings = []
    # Detect literal strings from task embedded in assert ... in answer['message']
    literals = re.findall(r"assert ['\"]([^'\"]+)['\"] in answer\[", test_code)
    for lit in literals:
        if lit in task_text:
            warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    return warnings
```

Return warnings alongside the pass/fail result. Pipeline logs them as `tdd_warning` trace events and prints to terminal.

### 3. `pipeline.py` — wire context_snapshot and warnings

At each `run_tests` call site:

**SQL suite:**
```python
sql_passed, sql_err = run_tests(
    test_gen_out.sql_tests, "test_sql", {"results": sql_results},
    task_text=task_text,
)
if t := get_trace():
    t.log_test_run(
        cycle + 1, "sql", sql_passed, sql_err,
        context_snapshot=json.dumps({"results": sql_results})[:3000],
    )
```

**Answer suite:**
```python
ans_passed, ans_err = run_tests(
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
```

For anti-pattern warnings returned from `run_tests`, log each as:
```python
t._write({"type": "tdd_warning", "suite": suite, "warnings": warnings})
```
Also print to terminal with `CLI_YELLOW`.

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
```

---

## Files Changed

| File | Change |
|------|--------|
| `agent/trace.py` | `log_test_run` gains `context_snapshot: str = ""` |
| `agent/test_runner.py` | `run_tests` gains `task_text: str = ""`; increase error limit to 2000; add `_check_tdd_antipatterns` |
| `agent/pipeline.py` | Pass `context_snapshot` and `task_text` at both `run_tests` call sites; log `tdd_warning` events |
| `data/prompts/test_gen.md` | Add anti-patterns section |

---

## Success Criteria

- After a `test_run` failure, `context_snapshot` in the JSONL event shows the actual `answer['message']` value
- Pipeline prints `[TDD WARNING]` to terminal when anti-pattern detected in generated test
- `test_gen.md` prompt prevents LLM from generating exact-string asserts for product names
- No regressions in existing tests (`uv run pytest tests/ -v`)
