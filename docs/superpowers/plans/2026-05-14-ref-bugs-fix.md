# Reference Extraction Bugs Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three benchmark failures (t03, t17, t21) caused by subdirectory stripping in refs, missing store_id extraction, and AttributeError crash.

**Architecture:** Three independent bugs in `agent/pipeline.py` and `agent/json_extract.py`. Each fix is surgical — no new abstractions. Tests go in new `tests/test_ref_bugs.py`; two conflicting existing tests in `tests/test_pipeline_sku_refs.py` are updated in Task 4.

**Tech Stack:** Python 3.11+, pytest, unittest.mock, pathlib.Path, Pydantic

---

## File Map

| Action | File | What changes |
|--------|------|--------------|
| Modify | `agent/json_extract.py:41-44` | Fix `_obj_mutation_tool` — guard `isinstance(fn, dict)` |
| Modify | `agent/pipeline.py:272-281` | `_build_answer_user_msg` — use `auto_refs` directly, no stem transform |
| Modify | `agent/pipeline.py:314-329` | `_extract_sku_refs` — add independent `if "store_id"` block |
| Modify | `agent/pipeline.py:38-39` | Delete `_to_short_ref` function entirely |
| Modify | `agent/pipeline.py:662-669` | TDD `clean_refs` — exact-path match instead of stem |
| Modify | `agent/pipeline.py:705-712` | Non-TDD `clean_refs` — exact-path match instead of stem |
| Modify | `agent/pipeline.py:424-731` | Wrap for-loop + post-loop answer block in try/except |
| Create | `tests/test_ref_bugs.py` | All new tests for the three bugs |
| Modify | `tests/test_pipeline_sku_refs.py:56-75` | Update two tests that assert old (broken) behavior |

---

## Task 1: Fix `_obj_mutation_tool` (Bug 3, Level 1)

**Files:**
- Modify: `agent/json_extract.py:41-44`
- Create: `tests/test_ref_bugs.py`

- [ ] **Step 1: Create the test file with all imports at the top and Task 1 tests**

Create `tests/test_ref_bugs.py` with this exact content (all imports for all future tasks go here now):

```python
# tests/test_ref_bugs.py
from unittest.mock import MagicMock, patch

from agent.json_extract import _obj_mutation_tool
from agent.pipeline import _build_answer_user_msg, _extract_sku_refs, run_pipeline
from agent.prephase import PrephaseResult


def _make_pre():
    return PrephaseResult(
        agents_md_content="AGENTS",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(id INT)",
    )


# ── Bug 3 / Level 1: _obj_mutation_tool ──────────────────────────────────────

def test_obj_mutation_tool_function_as_string():
    """Bug t21: 'function' field is a string — must not crash, must return None."""
    obj = {"function": "checkout", "args": {}}
    assert _obj_mutation_tool(obj) is None


def test_obj_mutation_tool_function_as_dict_with_mutation_tool():
    """Normal case: 'function' is a dict with a valid mutation tool name."""
    obj = {"function": {"tool": "write", "path": "/x"}}
    assert _obj_mutation_tool(obj) == "write"


def test_obj_mutation_tool_top_level_tool():
    """Top-level 'tool' key wins regardless of 'function'."""
    obj = {"tool": "delete"}
    assert _obj_mutation_tool(obj) == "delete"


def test_obj_mutation_tool_no_mutation():
    """Read-type tool returns None."""
    obj = {"tool": "read"}
    assert _obj_mutation_tool(obj) is None
```

- [ ] **Step 2: Run tests to confirm Task 1 tests fail**

```bash
uv run pytest tests/test_ref_bugs.py -v
```

Expected: `test_obj_mutation_tool_function_as_string` FAILS with `AttributeError: 'str' object has no attribute 'get'`. Other 3 tests PASS.

- [ ] **Step 3: Fix `_obj_mutation_tool` in `agent/json_extract.py`**

Replace lines 41-44:

```python
def _obj_mutation_tool(obj: dict) -> str | None:
    """Return the mutation tool name if obj is a write/delete/exec action, else None."""
    tool = obj.get("tool")
    if not tool:
        fn = obj.get("function")
        if isinstance(fn, dict):
            tool = fn.get("tool", "")
    return tool if tool in _MUTATION_TOOLS else None
```

- [ ] **Step 4: Run tests to confirm all 4 pass**

```bash
uv run pytest tests/test_ref_bugs.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ref_bugs.py agent/json_extract.py
git commit -m "fix: guard isinstance(fn, dict) in _obj_mutation_tool — fixes t21 AttributeError"
```

---

## Task 2: Fix `_extract_sku_refs` — add `store_id` branch (Bug 2)

**Files:**
- Modify: `agent/pipeline.py:314-329`
- Modify: `tests/test_ref_bugs.py`

- [ ] **Step 1: Add failing tests to `tests/test_ref_bugs.py`**

Append after the last test function (no new imports needed — already at top):

```python
# ── Bug 2: _extract_sku_refs store_id ────────────────────────────────────────

def test_extract_sku_refs_store_id_only():
    """Bug t17: store_id column must produce /proc/stores/{id}.json."""
    results = ["store_id\nstore_vienna_praterstern\n"]
    refs = _extract_sku_refs([], results)
    assert refs == ["/proc/stores/store_vienna_praterstern.json"]


def test_extract_sku_refs_sku_and_store_id():
    """Inventory query has both sku and store_id — both refs must appear."""
    results = ["store_id,sku,available_today\nstore_vienna_praterstern,PLB-2GJZ9R7K,1\n"]
    refs = _extract_sku_refs([], results)
    assert "/proc/catalog/PLB-2GJZ9R7K.json" in refs
    assert "/proc/stores/store_vienna_praterstern.json" in refs
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
uv run pytest tests/test_ref_bugs.py::test_extract_sku_refs_store_id_only tests/test_ref_bugs.py::test_extract_sku_refs_sku_and_store_id -v
```

Expected: Both FAIL — `refs == []` instead of expected paths.

- [ ] **Step 3: Add `store_id` block in `_extract_sku_refs` in `agent/pipeline.py`**

Current code at lines 305-330:

```python
def _extract_sku_refs(queries: list[str], results: list[str]) -> list[str]:
    """Extract catalogue paths from SQL results. Uses 'path' column when present,
    falls back to constructing /proc/catalog/{sku}.json from 'sku' column."""
    refs: list[str] = []
    for result_txt in results:
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        headers = [h.strip().lower() for h in lines[0].split(",")]
        if "path" in headers:
            path_idx = headers.index("path")
            for row in lines[1:]:
                cols = row.split(",")
                if path_idx < len(cols):
                    path = cols[path_idx].strip().strip('"')
                    if path:
                        refs.append(path)
        elif "sku" in headers:
            sku_idx = headers.index("sku")
            for row in lines[1:]:
                cols = row.split(",")
                if sku_idx < len(cols):
                    sku = cols[sku_idx].strip().strip('"')
                    if sku:
                        refs.append(f"/proc/catalog/{sku}.json")
    return refs
```

Replace with:

```python
def _extract_sku_refs(queries: list[str], results: list[str]) -> list[str]:
    """Extract catalogue paths from SQL results. Uses 'path' column when present,
    falls back to constructing /proc/catalog/{sku}.json from 'sku' column.
    Independently adds /proc/stores/{store_id}.json when 'store_id' column present."""
    refs: list[str] = []
    for result_txt in results:
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        headers = [h.strip().lower() for h in lines[0].split(",")]
        if "path" in headers:
            path_idx = headers.index("path")
            for row in lines[1:]:
                cols = row.split(",")
                if path_idx < len(cols):
                    path = cols[path_idx].strip().strip('"')
                    if path:
                        refs.append(path)
        elif "sku" in headers:
            sku_idx = headers.index("sku")
            for row in lines[1:]:
                cols = row.split(",")
                if sku_idx < len(cols):
                    sku = cols[sku_idx].strip().strip('"')
                    if sku:
                        refs.append(f"/proc/catalog/{sku}.json")
        if "store_id" in headers:
            store_idx = headers.index("store_id")
            for row in lines[1:]:
                cols = row.split(",")
                if store_idx < len(cols):
                    store_id = cols[store_idx].strip().strip('"')
                    if store_id:
                        refs.append(f"/proc/stores/{store_id}.json")
    return refs
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_ref_bugs.py tests/test_pipeline_sku_refs.py -v
```

Expected: All pass (including existing sku_refs tests).

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_ref_bugs.py
git commit -m "fix: add store_id branch in _extract_sku_refs — fixes t17 missing store refs"
```

---

## Task 3: Fix `_build_answer_user_msg` — full paths in AUTO_REFS (Bug 1, part 1)

**NOTE:** `_to_short_ref` is NOT deleted in this task — that happens in Task 4 together with the `clean_refs` fix. This keeps every commit in a working state.

**Files:**
- Modify: `agent/pipeline.py:272-281` (`_build_answer_user_msg`)
- Modify: `tests/test_ref_bugs.py` (add test)
- Modify: `tests/test_pipeline_sku_refs.py:56-64` (update one broken test)

- [ ] **Step 1: Add failing test to `tests/test_ref_bugs.py`**

Append after the last test function:

```python
# ── Bug 1 / Part 1: _build_answer_user_msg ───────────────────────────────────

def test_build_answer_user_msg_preserves_full_path():
    """Bug t03: AUTO_REFS must show full hierarchical paths, not stem-only."""
    msg = _build_answer_user_msg(
        "find pipe fittings",
        ["path\n/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json\n"],
        ["/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json"],
    )
    assert "/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json" in msg
    assert msg.count("/proc/catalog/PLB-2GJZ9R7K.json") == 0
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_ref_bugs.py::test_build_answer_user_msg_preserves_full_path -v
```

Expected: FAIL — msg contains `/proc/catalog/PLB-2GJZ9R7K.json` (short form) instead of full path.

- [ ] **Step 3: Fix `_build_answer_user_msg` in `agent/pipeline.py`**

Replace lines 272-281 (keep `_to_short_ref` at lines 38-39 untouched for now):

```python
def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    refs_block = "\n".join(auto_refs)
    return (
        base
        + f"\n\nAUTO_REFS (catalogue paths for grounding_refs — use exactly as shown):\n{refs_block}"
    )
```

- [ ] **Step 4: Update the broken test in `tests/test_pipeline_sku_refs.py`**

`test_build_answer_user_msg_normalizes_hierarchical_ref` (lines 56-64) asserts old short-form behavior. Replace it:

```python
def test_build_answer_user_msg_preserves_hierarchical_ref():
    """AUTO_REFS block must show full paths — LLM copies them verbatim to grounding_refs."""
    msg = _build_answer_user_msg(
        "find hand tool",
        ["sku\nHND-6D7TN1CT\n"],
        ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"],
    )
    assert "/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json" in msg
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_pipeline_sku_refs.py tests/test_ref_bugs.py -v
```

Expected: All pass. `_to_short_ref` still defined in `pipeline.py` — no NameError anywhere.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_ref_bugs.py tests/test_pipeline_sku_refs.py
git commit -m "fix: pass full paths in AUTO_REFS — fixes t03 subdirectory stripping in LLM prompt"
```

---

## Task 4: Fix `clean_refs` exact-path filter + delete `_to_short_ref` (Bug 1, part 2)

**Files:**
- Modify: `agent/pipeline.py:38-39` (NOW delete `_to_short_ref`)
- Modify: `agent/pipeline.py:662-669` (TDD ANSWER block)
- Modify: `agent/pipeline.py:705-712` (non-TDD ANSWER block)
- Modify: `tests/test_ref_bugs.py` (add tests)
- Modify: `tests/test_pipeline_sku_refs.py:67-75` (remove test that imports deleted function)

- [ ] **Step 1: Add failing tests to `tests/test_ref_bugs.py`**

Append after the last test function:

```python
# ── Bug 1 / Part 2: clean_refs exact-path filter ─────────────────────────────

def test_clean_refs_exact_match_preserves_full_path():
    """clean_refs must use exact path match, not stem match."""
    sku_refs = ["/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json"]
    result_paths = set(sku_refs)
    grounding_refs = ["/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json"]
    clean = [r for r in grounding_refs if r in result_paths]
    assert clean == ["/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json"]


def test_clean_refs_passthrough_when_result_paths_empty():
    """clean_refs passes all grounding_refs through when sku_refs is empty."""
    result_paths: set[str] = set()
    grounding_refs = ["/proc/catalog/PLB-2GJZ9R7K.json"]
    clean = [r for r in grounding_refs if r in result_paths] if result_paths else list(grounding_refs)
    assert clean == ["/proc/catalog/PLB-2GJZ9R7K.json"]


def test_clean_refs_excludes_unmatched_ref():
    """Refs not in sku_refs are excluded from clean_refs."""
    sku_refs = ["/proc/catalog/plumbing/PLB-ABC.json"]
    result_paths = set(sku_refs)
    grounding_refs = ["/proc/catalog/plumbing/PLB-ABC.json", "/proc/catalog/other/OTH-XYZ.json"]
    clean = [r for r in grounding_refs if r in result_paths] if result_paths else list(grounding_refs)
    assert clean == ["/proc/catalog/plumbing/PLB-ABC.json"]
```

- [ ] **Step 2: Run new tests to confirm they pass (logic tests)**

```bash
uv run pytest tests/test_ref_bugs.py::test_clean_refs_exact_match_preserves_full_path tests/test_ref_bugs.py::test_clean_refs_passthrough_when_result_paths_empty tests/test_ref_bugs.py::test_clean_refs_excludes_unmatched_ref -v
```

Expected: All 3 PASS — these test the replacement logic in isolation.

- [ ] **Step 3: Apply TDD ANSWER block fix in `agent/pipeline.py`**

At the TDD ANSWER block (near line 660), find:

```python
            result_skus = {Path(r).stem for r in sku_refs}
            ref_err = check_grounding_refs(answer_out.grounding_refs, result_skus, security_gates)
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            clean_refs = (
                [_to_short_ref(r) for r in answer_out.grounding_refs if Path(r).stem in result_skus]
                if result_skus else list(answer_out.grounding_refs)
            )
```

Replace with:

```python
            ref_err = check_grounding_refs(
                answer_out.grounding_refs,
                {Path(r).stem for r in sku_refs},
                security_gates,
            )
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            result_paths = set(sku_refs)
            clean_refs = (
                [r for r in answer_out.grounding_refs if r in result_paths]
                if result_paths else list(answer_out.grounding_refs)
            )
```

- [ ] **Step 4: Apply non-TDD ANSWER block fix in `agent/pipeline.py`**

At the non-TDD ANSWER block (near line 703), find the same pattern:

```python
            result_skus = {Path(r).stem for r in sku_refs}
            ref_err = check_grounding_refs(answer_out.grounding_refs, result_skus, security_gates)
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            clean_refs = (
                [_to_short_ref(r) for r in answer_out.grounding_refs if Path(r).stem in result_skus]
                if result_skus else list(answer_out.grounding_refs)
            )
```

Replace with:

```python
            ref_err = check_grounding_refs(
                answer_out.grounding_refs,
                {Path(r).stem for r in sku_refs},
                security_gates,
            )
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            result_paths = set(sku_refs)
            clean_refs = (
                [r for r in answer_out.grounding_refs if r in result_paths]
                if result_paths else list(answer_out.grounding_refs)
            )
```

- [ ] **Step 5: Delete `_to_short_ref` from `agent/pipeline.py`**

Now that no call sites remain, delete lines 38-39:

```python
def _to_short_ref(path: str) -> str:
    return f"/proc/catalog/{Path(path).stem}.json"
```

- [ ] **Step 6: Remove `test_clean_refs_stem_match_normalizes` from `tests/test_pipeline_sku_refs.py`**

Delete the entire function at lines 67-75 (it imports `_to_short_ref` which no longer exists):

```python
def test_clean_refs_stem_match_normalizes():
    """clean_refs accepts model output in any format, outputs short-form."""
    from pathlib import Path
    from agent.pipeline import _to_short_ref
    sku_refs = ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"]
    result_skus = {Path(r).stem for r in sku_refs}
    grounding_refs = ["/proc/catalog/HND-6D7TN1CT.json"]  # model used short form
    clean = [_to_short_ref(r) for r in grounding_refs if Path(r).stem in result_skus]
    assert clean == ["/proc/catalog/HND-6D7TN1CT.json"]
```

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass. Verify no leftover references:

```bash
grep -n "_to_short_ref\|result_skus" agent/pipeline.py
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add agent/pipeline.py tests/test_ref_bugs.py tests/test_pipeline_sku_refs.py
git commit -m "fix: clean_refs uses exact path match, delete _to_short_ref — fixes t03 ref mismatch"
```

---

## Task 5: Wrap for-loop in try/except (Bug 3, Level 2)

**Files:**
- Modify: `agent/pipeline.py:424-731`
- Modify: `tests/test_ref_bugs.py` (add integration test)

- [ ] **Step 1: Add failing integration test to `tests/test_ref_bugs.py`**

Append after the last test function (no new imports needed — already at top):

```python
# ── Bug 3 / Level 2: run_pipeline try/except wrapper ─────────────────────────

def test_run_pipeline_unhandled_exception_calls_vm_answer_once(tmp_path):
    """Bug t21: unhandled exception in for-loop must call vm.answer exactly once."""
    vm = MagicMock()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    with patch("agent.pipeline._call_llm_phase", side_effect=AttributeError("str has no .get")), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}):
        run_pipeline(vm, "anthropic/claude-sonnet-4-6", "checkout task", _make_pre(), {})

    assert vm.answer.call_count == 1
    call_arg = vm.answer.call_args[0][0]
    assert call_arg.message == "Internal pipeline error."
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_ref_bugs.py::test_run_pipeline_unhandled_exception_calls_vm_answer_once -v
```

Expected: FAIL — `AttributeError` propagates uncaught, `vm.answer` is never called.

- [ ] **Step 3: Wrap for-loop and post-loop answer block in try/except in `agent/pipeline.py`**

Make three surgical edits to `run_pipeline`:

**Edit A — add `try:` before the for-loop.** Find line 427 (`    for cycle in range(_MAX_CYCLES):`). Insert `    try:` on the line immediately before it.

**Edit B — indent the for-loop and the two post-loop blocks by 4 spaces.** The block to indent runs from `    for cycle in range(_MAX_CYCLES):` through the end of the `# TDD success: outcome already set in loop body` comment (before the `# ── EVALUATE` comment). This includes:
- The entire `for` loop body
- The `if not success:` block with its inner `try/except`
- The `elif not _TDD_ENABLED:` block with its inner logic
- The `# TDD success:` comment line

**Edit C — add the `except Exception:` handler** immediately after the last line of the indented block (the `# TDD success:` comment), before the `# ── EVALUATE` comment:

```python
    except Exception:
        print(f"{CLI_RED}[pipeline] UNHANDLED: {traceback.format_exc()}{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Internal pipeline error.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
```

`traceback` is already imported at `pipeline.py:9`. The `# ── EVALUATE` block and the `stats` dict construction remain OUTSIDE the try/except at their original indentation level.

The resulting structure (abbreviated):

```python
    _skip_sql = False
    queries: list[str] = []
    outcome = "OUTCOME_NONE_CLARIFICATION"
    try:
        for cycle in range(_MAX_CYCLES):
            cycles_used = cycle + 1
            # ... entire loop body indented 4 more spaces ...

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
            # ── ANSWER (non-TDD — outside loop, existing behavior) ───────────
            # ... existing non-TDD answer block indented 4 more spaces ...
        # TDD success: outcome already set in loop body
    except Exception:
        print(f"{CLI_RED}[pipeline] UNHANDLED: {traceback.format_exc()}{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Internal pipeline error.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    # ── EVALUATE (always, success or fail) ────────────────────────────────────
    eval_thread: threading.Thread | None = None
    # ... stats dict below, unchanged ...
```

- [ ] **Step 4: Run failing test to confirm it now passes**

```bash
uv run pytest tests/test_ref_bugs.py::test_run_pipeline_unhandled_exception_calls_vm_answer_once -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass, including existing `test_pipeline.py` and `test_pipeline_tdd.py` tests.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_ref_bugs.py
git commit -m "fix: wrap pipeline for-loop in try/except — prevents crash without vm.answer (t21)"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec requirement | Task |
|-----------------|------|
| Delete `_to_short_ref` | Task 4 (atomically with clean_refs fix) |
| `_build_answer_user_msg` uses `auto_refs` directly | Task 3 |
| TDD `clean_refs` — exact path match | Task 4 |
| Non-TDD `clean_refs` — exact path match | Task 4 |
| `check_grounding_refs` still receives stems | Task 4 (kept unchanged) |
| `result_paths` is separate variable from `check_grounding_refs` stems | Task 4 |
| `_extract_sku_refs` — independent `if "store_id"` block (not elif) | Task 2 |
| `_obj_mutation_tool` — guard `isinstance(fn, dict)` | Task 1 |
| try/except wraps for-loop + post-loop answer block together | Task 5 |
| EVALUATE and stats outside try/except | Task 5 |
| No double `vm.answer` call on exception | Task 5 (except block is sole fallback) |
| Unit test: `_obj_mutation_tool` string function → None | Task 1 |
| Unit test: `_extract_sku_refs` store_id-only | Task 2 |
| Unit test: `_extract_sku_refs` sku+store_id both | Task 2 |
| Unit test: `_build_answer_user_msg` full paths | Task 3 |
| Unit test: `clean_refs` exact match | Task 4 |
| Unit test: `clean_refs` passthrough when empty | Task 4 |
| Integration test: try/except calls vm.answer once | Task 5 |
| Existing pipeline tests continue to pass | Full suite run in Task 4 Step 7 and Task 5 Step 5 |
