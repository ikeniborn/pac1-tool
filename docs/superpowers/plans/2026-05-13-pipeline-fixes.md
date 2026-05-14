# Pipeline Systemic Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three systemic pipeline failures: RESOLVE storing only one confirmed value per field, silent vm.answer() skip when ANSWER parse fails, and discovery-only detection firing too late due to syntactic DISTINCT check.

**Architecture:** Five targeted edits across two code files, two prompt files, and one test file. No new abstractions — each change is a minimal surgical fix. TDD: tests written first for code changes, prompts verified via re-run after.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, uv

---

## File Map

| File | Change |
|------|--------|
| `agent/resolve.py` | Replace `_first_value` → `_all_values`; update `_run` to store all rows |
| `tests/test_resolve.py` | Rename `_first_value` tests → `_all_values`; add multi-value test |
| `agent/pipeline.py` | Add answer fallback; replace discovery-only condition |
| `data/prompts/resolve.md` | Add attr_value coverage section |
| `data/prompts/pipeline_evaluator.md` | Add assess items 8–9 |

---

## Task 1: `resolve.py` — replace `_first_value` with `_all_values`

**Files:**
- Modify: `agent/resolve.py:42-47` (function body), `:122-130` (caller)
- Test: `tests/test_resolve.py`

### Step 1: Write failing tests

Add these tests to `tests/test_resolve.py` (keep all existing tests, add below them):

```python
def test_all_values_returns_all_rows():
    csv_text = "value_text\n3XL\nL\nXL\nXXL\n"
    assert _all_values(csv_text) == ["3XL", "L", "XL", "XXL"]


def test_all_values_returns_empty_for_header_only():
    assert _all_values("brand\n") == []


def test_all_values_returns_empty_for_empty_string():
    assert _all_values("") == []


def test_all_values_strips_quotes():
    csv_text = 'brand\n"Heco GmbH"\n"Maker Inc"'
    assert _all_values(csv_text) == ["Heco GmbH", "Maker Inc"]


def test_run_resolve_stores_all_matching_values():
    """When discovery returns 3XL, L, XL, XXL — all four must be in confirmed_values."""
    vm = MagicMock()
    exec_r = MagicMock()
    exec_r.stdout = "value_text\n3XL\nL\nXL\nXXL\n"
    vm.exec.return_value = exec_r

    raw = json.dumps({
        "reasoning": "size values",
        "candidates": [{"term": "L", "field": "attr_value",
                         "discovery_query": "SELECT DISTINCT value_text FROM product_properties WHERE key = 'size' AND value_text LIKE '%L%' LIMIT 10"}]
    })
    with patch("agent.resolve.call_llm_raw", return_value=raw):
        result = run_resolve(vm, "model", "find size L product", _make_pre(), {})

    assert "attr_value" in result
    assert "L" in result["attr_value"]
    assert "3XL" in result["attr_value"]
```

- [ ] **Step 1a:** Add the import line at top of `tests/test_resolve.py`:
  - Change line 3 from:
    ```python
    from agent.resolve import _security_check, _first_value, run_resolve
    ```
  - To:
    ```python
    import json
    from unittest.mock import MagicMock, patch
    from agent.resolve import _security_check, _all_values, run_resolve
    ```
  - (`json`, `MagicMock`, `patch` may already be imported — add only what's missing; `_first_value` intentionally omitted — shim exists but tests no longer need it)

- [ ] **Step 1b:** Append the five new test functions above to end of `tests/test_resolve.py`

- [ ] **Step 1c:** Run new tests to confirm they fail:
  ```bash
  cd /home/ikeniborn/Documents/Project/ecom1-agent
  uv run pytest tests/test_resolve.py::test_all_values_returns_all_rows tests/test_resolve.py::test_run_resolve_stores_all_matching_values -v
  ```
  Expected: `ImportError: cannot import name '_all_values'`

### Step 2: Implement `_all_values` in `agent/resolve.py`

- [ ] **Step 2a:** In `agent/resolve.py`, replace lines 42–47 (the `_first_value` function) with:

```python
def _all_values(csv_text: str) -> list[str]:
    lines = [ln.strip() for ln in csv_text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    return [
        parts[0].strip().strip('"')
        for line in lines[1:]
        for parts in [line.split(",")]
        if parts[0].strip().strip('"')
    ]


def _first_value(csv_text: str) -> str | None:
    """Deprecated shim — kept for test backward compat. Use _all_values."""
    vals = _all_values(csv_text)
    return vals[0] if vals else None
```

  Keep `_first_value` as a shim so existing tests don't break.

- [ ] **Step 2b:** In `agent/resolve.py`, find and replace the block starting with `value = _first_value(result_txt)` (originally lines 122–130, shifted after Step 2a). Replace this block:

```python
        values = _all_values(result_txt)
        if t := get_trace():
            t.log_resolve_exec(candidate.discovery_query, result_txt, values[0] if values else "")
        for value in values:
            field = candidate.field
            if field not in confirmed_values:
                confirmed_values[field] = []
            if value not in confirmed_values[field]:
                confirmed_values[field].append(value)
```

  Note: `log_resolve_exec` still receives `values[0]` as `value_extracted` — keeps `test_trace_resolve.py` passing.

### Step 3: Run all resolve tests

- [ ] Run:
  ```bash
  uv run pytest tests/test_resolve.py tests/test_trace_resolve.py -v
  ```
  Expected: all pass. Confirm `test_run_resolve_stores_all_matching_values` is GREEN.

### Step 4: Rename old `_first_value` tests

- [ ] In `tests/test_resolve.py`, rename the four `_first_value` test functions:
  - `test_first_value_returns_first_data_cell` → `test_all_values_first_row_compat`
    - Change body: `assert _all_values("brand\nHeco\nMaker") == ["Heco", "Maker"]`
  - `test_first_value_returns_none_for_header_only` → `test_all_values_empty_for_header_only` (already added above — delete the old one)
  - `test_first_value_returns_none_for_empty` → `test_all_values_empty_for_empty_string` (already added — delete old)
  - `test_first_value_strips_quotes` → `test_all_values_strips_quotes_first_row`
    - Change body: `assert _all_values('brand\n"Heco GmbH"') == ["Heco GmbH"]`

- [ ] After renaming, verify `_first_value` no longer appears anywhere in `tests/test_resolve.py`:
  ```bash
  grep "_first_value" tests/test_resolve.py
  ```
  Expected: no output (shim kept in `resolve.py` for backward compat but unused in tests).

- [ ] Run:
  ```bash
  uv run pytest tests/test_resolve.py -v
  ```
  Expected: all pass, no `_first_value` test names in output.

### Step 5: Full test suite

- [ ] Run:
  ```bash
  uv run pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: 0 failures.

### Step 6: Commit

```bash
git add agent/resolve.py tests/test_resolve.py
git commit -m "fix(resolve): collect all discovery values, not just first row

_first_value returned only the first CSV row, causing SCHEMA gate to
block task literals present in later rows (e.g. 'L' after '3XL').
_all_values collects every row; _first_value kept as compat shim.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: `pipeline.py` — answer fallback when parse fails

**Files:**
- Modify: `agent/pipeline.py:564-579`
- Test: `tests/test_pipeline.py` (add one test)

### Step 1: Write failing test

- [ ] Open `tests/test_pipeline.py` and find the section with answer-phase tests. Add:

```python
def test_answer_fallback_called_when_parse_fails(tmp_path):
    """When AnswerOutput.model_validate fails (invalid outcome), vm.answer is still called.

    Uses side_effect so SQL_PLAN succeeds (call 1) but ANSWER returns invalid JSON (call 2).
    Without the fix: answer_out=None → if answer_out: skipped → vm.answer never called.
    With the fix: else branch → vm.answer(OUTCOME_NONE_CLARIFICATION) called.
    """
    vm = MagicMock()
    # Both EXPLAIN and EXECUTE return sku+path data so pipeline reaches ANSWER
    exec_result = _make_exec_result("sku,path\nSKU-001,/proc/catalog/SKU-001.json\n")
    vm.exec.return_value = exec_result

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    bad_answer_json = json.dumps({
        "reasoning": "x", "message": "hi",
        "outcome": "OUTCOME_NEED_MORE_DATA",   # invalid — not in AnswerOutput Literal
        "grounding_refs": [], "completed_steps": [],
    })
    # Call 1 → SQL_PLAN succeeds; Call 2 → ANSWER parse fails
    call_seq = [
        _sql_plan_json(queries=["SELECT p.sku, p.path FROM products p WHERE p.type='X'"]),
        bad_answer_json,
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "test-model", "test task", pre, {})

    # vm.answer must have been called despite parse failure
    vm.answer.assert_called_once()
    req = vm.answer.call_args.args[0]   # AnswerRequest positional arg
    assert "Could not synthesize" in req.message
```

- [ ] Run to confirm it fails:
  ```bash
  uv run pytest tests/test_pipeline.py::test_answer_fallback_called_when_parse_fails -v
  ```
  Expected: FAIL — `AssertionError: Expected 'answer' to have been called once. Called 0 times.`

### Step 2: Implement fallback in `agent/pipeline.py`

- [ ] In `agent/pipeline.py`, find the block starting at line 564:
  ```python
        if answer_out:
            outcome = answer_out.outcome
  ```
  After the entire `if answer_out:` block (after line 579), add the `else` branch:

```python
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
```

### Step 3: Run test

- [ ] Run:
  ```bash
  uv run pytest tests/test_pipeline.py::test_answer_fallback_called_when_parse_fails -v
  ```
  Expected: PASS.

### Step 4: Full test suite

- [ ] Run:
  ```bash
  uv run pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: 0 failures.

### Step 5: Commit

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "fix(pipeline): call vm.answer fallback when AnswerOutput parse fails

When model returns an outcome not in the AnswerOutput Literal enum
(e.g. OUTCOME_NEED_MORE_DATA), model_validate raises and answer_out
is None. Previously vm.answer was never called, causing silent 0-score.
Now falls back to OUTCOME_NONE_CLARIFICATION.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: `pipeline.py` — structural discovery-only detection

**Files:**
- Modify: `agent/pipeline.py:522-537`
- Test: `tests/test_pipeline.py` (add two tests)

### Step 1: Write failing test

- [ ] Add to `tests/test_pipeline.py`:

```python
def test_discovery_only_detection_fires_without_all_distinct(tmp_path):
    """Schema query (non-DISTINCT) mixed with DISTINCT batch → discovery-only fires if no sku/path.

    Old code: all_discovery = all(SELECT DISTINCT ...) → False → ANSWER after cycle 1
              call_seq[1] = _sql_plan_json (invalid AnswerOutput) → parse fails → vm.answer not called
    New code: not new_refs and not has_count_result → continue → cycle 2 → sku/path → vm.answer called
    """
    vm = MagicMock()

    def mock_exec(req):
        arg = req.args[0] if req.args else ""
        if arg.startswith("EXPLAIN"):
            return _make_exec_result("")
        if "sqlite_schema" in arg:
            return _make_exec_result("")
        if "DISTINCT" in arg.upper() and "kind_id" in arg:
            return _make_exec_result("kind_id\ntool_boxes\n")
        return _make_exec_result("sku,path\nSKU-001,/proc/catalog/SKU-001.json\n")

    vm.exec.side_effect = mock_exec
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    # call_seq designed for new code: SQL_PLAN cycle1 → (discovery-only) → SQL_PLAN cycle2 → ANSWER
    # With old code: cycle1 goes directly to ANSWER, consuming call_seq[1] = _sql_plan_json
    # → AnswerOutput.model_validate fails → answer_out=None → vm.answer never called
    call_seq = [
        json.dumps({
            "reasoning": "discover schema then kind_id",
            "queries": [
                "SELECT name, sql FROM sqlite_schema WHERE name = 'kinds'",
                "SELECT DISTINCT kind_id FROM products WHERE kind_id LIKE '%tool%'",
            ],
        }),
        _sql_plan_json(["SELECT p.sku, p.path FROM products p WHERE p.kind_id = 'tool_boxes'"]),
        _answer_json(),
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "test-model", "find tool boxes", pre, {})

    # New code: cycle 2 ran → sku refs found → vm.answer called
    vm.answer.assert_called_once()
```

- [ ] Run to confirm it fails:
  ```bash
  uv run pytest tests/test_pipeline.py::test_discovery_only_detection_fires_without_all_distinct -v
  ```
  Expected: FAIL — `AssertionError: Expected 'answer' to have been called once. Called 0 times.`

### Step 2: Implement structural detection in `agent/pipeline.py`

- [ ] In `agent/pipeline.py`, replace lines 522–537 (the `# ── DISCOVERY-ONLY DETECTION` block):

```python
        # ── DISCOVERY-ONLY DETECTION ──────────────────────────────────────────
        # Structural check: if no sku/path refs AND no COUNT aggregate result,
        # this cycle produced only discovery data regardless of SELECT DISTINCT.
        # Dependency: sql_plan.md rule requires p.sku + p.path in final queries;
        # a final query missing those columns will also trigger this — forcing
        # the model to comply with the projection rule.
        has_count_result = any(
            re.search(r'\bCOUNT\s*\(', q, re.IGNORECASE) and _csv_has_data(r)
            for q, r in zip(queries, sql_results)
        )
        if not new_refs and not has_count_result:
            static_sql = _build_static_system(
                "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
                pre.schema_digest, rules_loader, security_gates,
                confirmed_values=confirmed_values, task_text=task_text,
            )
            last_error = "Discovery cycle complete. All confirmed values updated. Now emit the final SKU filter query using confirmed values — do NOT run more discovery."
            print(f"{CLI_BLUE}[pipeline] DISCOVERY-ONLY cycle — continuing for final filter{CLI_CLR}")
            continue
```

### Step 3: Run new test + full suite

- [ ] Run:
  ```bash
  uv run pytest tests/test_pipeline.py::test_discovery_only_detection_fires_without_all_distinct -v
  ```
  Expected: PASS.

- [ ] Run:
  ```bash
  uv run pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: 0 failures.

### Step 4: Commit

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "fix(pipeline): structural discovery-only detection replaces DISTINCT check

Old check required all queries to be SELECT DISTINCT. A schema introspection
query mixed into the batch caused t09 cycle 2 to be wrongly treated as
success — ANSWER received kind_id discovery data instead of COUNT result.

New check: no sku/path refs AND no COUNT aggregate result → discovery-only.
COUNT queries with data pass through correctly.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `data/prompts/resolve.md` — attr_value coverage

**Files:**
- Modify: `data/prompts/resolve.md`

No code change — prompt edit. Verification: re-run affected tasks after all changes.

- [ ] **Step 4a:** Open `data/prompts/resolve.md`. After the `## Discovery query patterns` section (after line 27), add:

```markdown
## Attribute value coverage (REQUIRED)

For every attribute value mentioned in the task (sizes, color families, protection
classes, machine types, anchor types, mask types, etc.) generate one `attr_value`
candidate.

- Key known (present in TOP PROPERTY KEYS): `SELECT DISTINCT value_text FROM product_properties WHERE key = '<key>' AND value_text LIKE '%<val>%' LIMIT 10`
- Key unknown: `SELECT DISTINCT value_text FROM product_properties WHERE value_text LIKE '%<val>%' LIMIT 10`

Generate candidates for ALL attribute values — including single-letter sizes
('M', 'L', 'S', 'XL') and short enum values ('basic', 'blue', 'clamp').
Do not skip values just because they are short or seem obvious.
```

- [ ] **Step 4b:** Commit:

```bash
git add data/prompts/resolve.md
git commit -m "feat(prompts): require attr_value candidate for every task attribute value

LLM was skipping short values like size 'M' and enum values like 'basic',
leaving them unconfirmed and triggering SCHEMA gate in later cycles.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: `data/prompts/pipeline_evaluator.md` — new failure pattern detection

**Files:**
- Modify: `data/prompts/pipeline_evaluator.md`

- [ ] **Step 5a:** Open `data/prompts/pipeline_evaluator.md`. After item `7.` in the `## Assess` section, add:

```markdown
8. RESOLVE coverage: Do `confirmed_values` in the trace include all `attr_value` literals from the task text (sizes, protection classes, color families, etc.)? If any task literal is absent from confirmed_values AND caused a SCHEMA gate block, suggest adding an `attr_value` candidate for it in `resolve.md`.
9. ANSWER silent failure: If the answer phase `output` field in the trace is a raw string (not a parsed dict), the model returned an invalid `outcome` enum value causing parse failure. Identify the invalid outcome string and suggest either adding it to `AnswerOutput` Literal in `models.py` (if semantically valid) or adding a prompt rule in `answer.md` forbidding it.
```

- [ ] **Step 5b:** Commit:

```bash
git add data/prompts/pipeline_evaluator.md
git commit -m "feat(prompts): evaluator detects resolve coverage gaps and answer parse failures

Adds assess items 8-9 so propose_optimizations.py captures these failure
modes in eval_log.jsonl for future automated suggestion.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Verification run

Run 5 tasks including t04, t09, t16 to confirm improvements.

- [ ] **Step 6a:** Run benchmark tasks:
  ```bash
  make task TASKS='t01 t04 t08 t09 t16' 2>&1 | tee /tmp/pipeline-fixes-run.log
  ```

- [ ] **Step 6b:** Check final stats table from output. Expected improvements:
  - t04: score 1.00, ≤2 cycles (was 3)
  - t09: score > 0, vm.answer called (was 0 "no answer provided")
  - t16: score > 0 or ≤5 cycles (was 7, score 0)
  - t01, t08: score 1.00 (no regression)
  - Overall: ≥80% (was 60%)

- [ ] **Step 6c:** If t09 still scores 0, check log for `[pipeline] ANSWER parse failed` message — confirms fallback fired. If missing, the discovery-only fix may have enabled COUNT cycle that still failed.

- [ ] **Step 6d:** Full test suite one final time:
  ```bash
  uv run pytest tests/ -v --tb=short 2>&1 | tail -20
  ```
  Expected: 0 failures.

---

## Self-Review Checklist

- [x] **Spec § Problem 1** (resolve first-value) → Task 1 ✓
- [x] **Spec § Problem 2** (silent ANSWER failure) → Task 2 ✓
- [x] **Spec § Problem 3** (discovery detection) → Task 3 ✓
- [x] **Spec § resolve.md attr_value** → Task 4 ✓
- [x] **Spec § pipeline_evaluator.md** → Task 5 ✓
- [x] **Spec § test_resolve.py scope** → Task 1 Steps 1 + 4 ✓
- [x] **Spec § backward compat** — `_first_value` shim kept, trace logs `values[0]` ✓
- [x] **Spec dependency note (2B)** — documented in Task 3 Step 2 comment ✓
- [x] No placeholders — all steps have exact code ✓
- [x] Type consistency — `_all_values` returns `list[str]` used consistently ✓
- [x] Task 1 import — `_first_value` removed from test import; Step 4 adds grep check ✓
- [x] Task 2 assertion — checks `req.message` directly, not `str(call_args)` ✓
- [x] Task 3 TDD — integration test via `run_pipeline`; red before Step 2, green after ✓
