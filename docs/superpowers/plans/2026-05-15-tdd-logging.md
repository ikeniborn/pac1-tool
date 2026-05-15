# TDD Logging & Test Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `context_snapshot` to `test_run` trace events, emit `tdd_warning` events for anti-pattern tests, increase error truncation to 2000 chars, and harden `test_gen.md` against fragile assertions.

**Architecture:** Four-file change. `test_runner.py` gains anti-pattern detection + new signature. `trace.py` gains two new log methods. `pipeline.py` wires both at both TDD call sites. `test_gen.md` adds anti-patterns section. Existing tests updated first to avoid mid-task breakage.

**Tech Stack:** Python 3.12, pytest, uv, regex

---

## File Map

| File | Change |
|------|--------|
| `agent/trace.py` | Add `context_snapshot: str = ""` to `log_test_run`; add `log_tdd_warning` method |
| `agent/test_runner.py` | Add `_ANSWER_ASSERT_RE`, `_HEADER_ASSERT_RE`, `_check_tdd_antipatterns`; change `run_tests` to 3-tuple return + `task_text` param; bump error limit 500→2000 |
| `tests/test_test_runner.py` | Update 5 existing unpacks to 3-tuple; add 5 new `_check_tdd_antipatterns` tests |
| `agent/pipeline.py` | Unpack 3-tuple at both `run_tests` call sites; pass `task_text`; add `context_snapshot` to `log_test_run`; call `log_tdd_warning` |
| `data/prompts/test_gen.md` | Add anti-patterns section; update `## What to generate` sql bullet; update `## Output format` `sql_tests` example |

---

### Task 1: Fix existing `test_test_runner.py` — 2-tuple → 3-tuple

**Files:**
- Modify: `tests/test_test_runner.py`

> Do this FIRST. All 5 existing tests unpack `run_tests` as `passed, err = ...`. Updating them now means the test file will be consistent before we change `run_tests` itself.

- [ ] **Step 1: Update all 5 unpacks**

Replace every `passed, err = run_tests(` with `passed, err, _ = run_tests(` in `tests/test_test_runner.py`.

The file has exactly these 5 call sites (lines 4, 12, 20, 28, 40-53):

```python
# test_passing_assert — line 4
passed, err, _ = run_tests(code, "test_sql", {"results": ["row1"]})

# test_failing_assert — line 12
passed, err, _ = run_tests(code, "test_sql", {"results": []})

# test_syntax_error_in_test_code — line 20
passed, err, _ = run_tests(code, "test_sql", {"results": [1]})

# test_timeout — line 28
passed, err, _ = run_tests(code, "test_sql", {"results": []})

# test_answer_tests_signature — lines 40-53
passed, err, _ = run_tests(
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
```

- [ ] **Step 2: Run — should FAIL (run_tests still returns 2-tuple)**

```bash
uv run pytest tests/test_test_runner.py -v
```

Expected: 5 FAILED with `not enough values to unpack (expected 3, got 2)` or similar.

- [ ] **Step 3: Commit checkpoint**

```bash
git add tests/test_test_runner.py
git commit -m "test: update run_tests unpacks to 3-tuple (pre-migration)"
```

---

### Task 2: Add `_check_tdd_antipatterns` tests (failing)

**Files:**
- Modify: `tests/test_test_runner.py`

- [ ] **Step 1: Append 5 new tests**

Add to the end of `tests/test_test_runner.py`:

```python
# ── _check_tdd_antipatterns tests ──────────────────────────────────────────

def test_antipattern_literal_in_answer_warns_when_in_task():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    task = "How many Cordless Drill Driver SKUs are active?"
    warnings = _check_tdd_antipatterns(code, task_text=task)
    assert any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_literal_not_in_task_no_warn():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    # task does NOT contain the literal
    warnings = _check_tdd_antipatterns(code, task_text="List active SKUs")
    assert not any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_no_task_text_no_answer_warn():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_answer(sql_results, answer):\n    assert 'Cordless Drill Driver' in answer['message']\n"
    # task_text omitted — answer anti-pattern check skipped
    warnings = _check_tdd_antipatterns(code)
    assert not any("Cordless Drill Driver" in w for w in warnings)


def test_antipattern_header_literal_always_warns():
    from agent.test_runner import _check_tdd_antipatterns
    code = "def test_sql(results):\n    header = results[0].split('\\n')[0].lower()\n    assert 'count' in header\n"
    warnings = _check_tdd_antipatterns(code)
    assert any("count" in w for w in warnings)


def test_antipattern_unescaped_opposite_quote_no_warn():
    """False-negative: regex does not match unescaped opposite-quote inside literal. Acceptable for MVP."""
    from agent.test_runner import _check_tdd_antipatterns
    # "Bob's Drill" — embedded apostrophe inside double-quoted string
    code = "def test_answer(sql_results, answer):\n    assert \"Bob's Drill\" in answer['message']\n"
    task = "Find Bob's Drill products"
    warnings = _check_tdd_antipatterns(code, task_text=task)
    # regex stops on the embedded ' — no match, no warning (documented false-negative)
    assert not warnings
```

- [ ] **Step 2: Run — should FAIL (function not defined)**

```bash
uv run pytest tests/test_test_runner.py::test_antipattern_literal_in_answer_warns_when_in_task -v
```

Expected: FAIL with `ImportError` or `cannot import name '_check_tdd_antipatterns'`.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_test_runner.py
git commit -m "test: add failing tests for _check_tdd_antipatterns"
```

---

### Task 3: Implement `_check_tdd_antipatterns` + update `run_tests`

**Files:**
- Modify: `agent/test_runner.py`

- [ ] **Step 1: Write the new `test_runner.py`**

Replace the entire file content:

```python
"""Subprocess test runner for TDD pipeline."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Regex: (?:[^'"\\]|\\.)* handles basic escape sequences (e.g. \', \").
# Known edge cases (acceptable for MVP):
#   False-negative: unescaped embedded opposite-quote inside string — e.g. assert "Bob's Drill" in answer[...]
#                   The [^'"\\] class stops on the embedded quote; regex fails to match.
#   False-positive: mismatched delimiters — e.g. assert 'foo" in answer[...]
#                   Acceptable since LLM-generated test code is expected to be syntactically valid.
_ANSWER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+answer\[""")
# _HEADER_ASSERT_RE matches `assert '<literal>' in header` only — not `in header[0]`, `in headers`,
# or any compound name.
# Known edge case (acceptable for MVP):
#   False-positive: non-aggregate column names (e.g. `sku`, `path`) also match and emit a warning.
_HEADER_ASSERT_RE = re.compile(r"""assert\s+['"]((?:[^'"\\]|\\.)*)['"]\s+in\s+header""")


def _check_tdd_antipatterns(test_code: str, task_text: str = "") -> list[str]:
    warnings = []
    if task_text:
        for lit in _ANSWER_ASSERT_RE.findall(test_code):
            if lit in task_text:
                warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    for col in _HEADER_ASSERT_RE.findall(test_code):
        warnings.append(
            f"hardcoded string in sql header assert: '{col}' — "
            "for aggregates use row/type check; for named columns this warning may be a false-positive"
        )
    return warnings


def run_tests(test_code: str, fn_name: str, context: dict, task_text: str = "") -> tuple[bool, str, list[str]]:
    """Run test_code in isolated subprocess. Returns (passed, error_message, warnings)."""
    warnings = _check_tdd_antipatterns(test_code, task_text)
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
            return True, "", warnings
        error = (result.stderr or result.stdout or "non-zero exit").strip()
        return False, error[:2000], warnings
    except subprocess.TimeoutExpired:
        return False, "test timeout", warnings
    except Exception as e:
        return False, str(e)[:2000], warnings
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 2: Run all `test_test_runner.py` tests**

```bash
uv run pytest tests/test_test_runner.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add agent/test_runner.py
git commit -m "feat: add _check_tdd_antipatterns + 3-tuple run_tests signature"
```

---

### Task 4: Update `trace.py` — add `context_snapshot` + `log_tdd_warning`

**Files:**
- Modify: `agent/trace.py`

- [ ] **Step 1: Update `log_test_run` signature and body**

Replace (line 141–148):
```python
    def log_test_run(self, cycle: int, suite: str, passed: bool, error: str) -> None:
        self._write({
            "type": "test_run",
            "cycle": cycle,
            "suite": suite,
            "passed": passed,
            "error": error,
        })
```

With:
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

- [ ] **Step 2: Add `log_tdd_warning` after `log_test_run`**

Insert after `log_test_run` (before `log_task_result`):

```python
    def log_tdd_warning(self, suite: str, warnings: list[str]) -> None:
        self._write({"type": "tdd_warning", "suite": suite, "warnings": warnings})
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS (no call sites changed yet so no breakage).

- [ ] **Step 4: Commit**

```bash
git add agent/trace.py
git commit -m "feat: add context_snapshot to log_test_run + log_tdd_warning"
```

---

### Task 5: Wire `pipeline.py` — 3-tuple, `context_snapshot`, `log_tdd_warning`

**Files:**
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Update SQL test call site (around line 634)**

Replace:
```python
                    sql_passed, sql_err = run_tests(
                        test_gen_out.sql_tests, "test_sql", {"results": sql_results}
                    )
                    if t := get_trace():
                        t.log_test_run(cycle + 1, "sql", sql_passed, sql_err)
                    if not sql_passed:
                        print(f"{CLI_YELLOW}[pipeline] SQL TEST failed: {sql_err[:80]}{CLI_CLR}")
                        last_error = sql_err[:500]
```

With:
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
                        print(f"{CLI_YELLOW}[pipeline] SQL TEST failed: {sql_err[:80]}{CLI_CLR}")
                        last_error = sql_err[:500]
```

- [ ] **Step 2: Update answer test call site (around line 676)**

Replace:
```python
                ans_passed, ans_err = run_tests(
                    test_gen_out.answer_tests, "test_answer",
                    {"sql_results": sql_results, "answer": answer_out.model_dump()},
                )
                if t := get_trace():
                    t.log_test_run(cycle + 1, "answer", ans_passed, ans_err)
                if not ans_passed:
                    print(f"{CLI_YELLOW}[pipeline] ANSWER TEST failed: {ans_err[:80]}{CLI_CLR}")
                    last_error = ans_err[:500]
```

With:
```python
                ans_passed, ans_err, ans_warns = run_tests(
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
                    print(f"{CLI_YELLOW}[pipeline] ANSWER TEST failed: {ans_err[:80]}{CLI_CLR}")
                    last_error = ans_err[:500]
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add agent/pipeline.py
git commit -m "feat: wire context_snapshot + tdd_warning to pipeline TDD call sites"
```

---

### Task 6: Update `data/prompts/test_gen.md`

**Files:**
- Modify: `data/prompts/test_gen.md`

- [ ] **Step 1: Update `## What to generate` first `test_sql` bullet**

Replace:
```
- Required columns are present in the header (e.g., `sku`, `path`, or `count`).
```

With:
```
- Required columns are present in the header (e.g., `sku`, `path`). For aggregate queries verify results are non-empty and the first data row contains a parseable integer — do not assert a specific column alias name.
```

- [ ] **Step 2: Add anti-patterns section before `## Output format`**

Insert the following block between `## Rules for test code` and `## Output format`:

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

- [ ] **Step 3: Update `## Output format` `sql_tests` example**

Replace the `"sql_tests"` line in the JSON block:

```json
  "sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    header = results[0].split('\\n')[0].lower()\n    assert 'sku' in header or 'count' in header, f'missing sku/count column: {header}'\n",
```

With:

```json
  "sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    rows = results[0].split('\\n')\n    assert len(rows) > 1, 'no data rows returned'\n",
```

- [ ] **Step 4: Run full test suite (no code changed — sanity)**

```bash
uv run pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add data/prompts/test_gen.md
git commit -m "docs: add anti-patterns section to test_gen.md prompt"
```

---

### Task 7: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all PASS, zero failures.

- [ ] **Step 2: Verify `test_run` JSONL structure**

```bash
python - <<'EOF'
from agent.trace import TraceLogger
from pathlib import Path
import tempfile, json

with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
    path = Path(f.name)

t = TraceLogger(path, "verify")
t.log_test_run(1, "sql", True, "", context_snapshot='{"results": ["a,b\\n1,2"]}')
t.log_test_run(1, "answer", False, "AssertionError", context_snapshot='{"sql_results": [], "answer": {}}')
t.log_tdd_warning("sql", ["hardcoded task literal in answer assert: 'Widget'"])
t.close()

for line in path.read_text().splitlines():
    rec = json.loads(line)
    if rec["type"] == "test_run":
        assert "context_snapshot" in rec, f"missing context_snapshot: {rec}"
    if rec["type"] == "tdd_warning":
        assert "warnings" in rec, f"missing warnings: {rec}"

print("PASS — all fields present")
path.unlink()
EOF
```

Expected: `PASS — all fields present`

- [ ] **Step 3: Verify error limit is 2000 in test_runner**

```bash
python - <<'EOF'
from agent.test_runner import run_tests

long_msg = "x" * 2500
code = f"def test_sql(results):\n    raise AssertionError('{long_msg}')\n"
_, err, _ = run_tests(code, "test_sql", {"results": []})
assert len(err) <= 2000, f"error too long: {len(err)}"
assert len(err) > 500, f"error too short (old 500-limit still in place): {len(err)}"
print(f"PASS — error len={len(err)}")
EOF
```

Expected: `PASS — error len=2000` (stderr ~2650 chars truncated to 2000).

- [ ] **Step 4: Final commit**

```bash
git add -p  # review any unstaged changes
git commit -m "chore: tdd-logging final verification complete" --allow-empty
```
