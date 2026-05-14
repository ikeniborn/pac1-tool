# Design: Fix Reference Extraction Bugs (Benchmark t03, t17, t21)

**Date:** 2026-05-14  
**Status:** Approved  
**Scope:** `agent/pipeline.py`, `agent/json_extract.py`

## Background

Three bugs found in benchmark run (40% score, 5 tasks):

- **t03** (0.00): evaluator expected `/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json`, answer contained `/proc/catalog/PLB-2GJZ9R7K.json` — subdirectory stripped.
- **t17** (0.00): evaluator expected `/proc/stores/store_vienna_praterstern.json`, but store refs were never extracted from inventory query results.
- **t21** (0.00): unhandled `AttributeError: 'str' object has no attribute 'get'` — pipeline crashed, no answer submitted.

## Bug 1 — `_to_short_ref` strips subdirectories

### Root cause

`_to_short_ref` at `pipeline.py:38–39`:
```python
def _to_short_ref(path: str) -> str:
    return f"/proc/catalog/{Path(path).stem}.json"
```

This strips subdirectory structure. DB `path` column stores full paths like
`/proc/catalog/plumbing/pipe_fittings/PLB-2GJZ9R7K.json`. After transformation,
AUTO_REFS shows `/proc/catalog/PLB-2GJZ9R7K.json` — evaluator cannot match.

### Fix

**Delete `_to_short_ref` entirely.**

1. `_build_answer_user_msg`: replace `[_to_short_ref(r) for r in auto_refs]` with `auto_refs` directly.
2. TDD ANSWER block (`pipeline.py:666–668`) and non-TDD ANSWER block (`pipeline.py:709–711`):
   replace stem-based filter with exact path match:

   ```python
   # Before
   result_skus = {Path(r).stem for r in sku_refs}
   clean_refs = (
       [_to_short_ref(r) for r in answer_out.grounding_refs if Path(r).stem in result_skus]
       if result_skus else list(answer_out.grounding_refs)
   )

   # After
   result_paths = set(sku_refs)
   clean_refs = [r for r in answer_out.grounding_refs if r in result_paths]
   ```

LLM sees full paths in AUTO_REFS, copies them verbatim to `grounding_refs`,
`clean_refs` filters by exact membership.

## Bug 2 — `_extract_sku_refs` ignores `store_id` column

### Root cause

`_extract_sku_refs` (`pipeline.py:305–330`) only handles `path` and `sku` columns.
Inventory queries return `store_id` column (e.g. `store_vienna_praterstern`).
Store refs are never added to `sku_refs` → never appear in AUTO_REFS →
LLM cannot ground answer to `/proc/stores/{store_id}.json`.

### Fix

Add third branch after `elif "sku" in headers:` in `_extract_sku_refs`:

```python
elif "store_id" in headers:
    store_idx = headers.index("store_id")
    for row in lines[1:]:
        cols = row.split(",")
        if store_idx < len(cols):
            store_id = cols[store_idx].strip().strip('"')
            if store_id:
                refs.append(f"/proc/stores/{store_id}.json")
```

Priority order unchanged: `path` > `sku` > `store_id` (if/elif chain).

## Bug 3 — `AttributeError: 'str' object has no attribute 'get'`

### Root cause

`_obj_mutation_tool` in `json_extract.py:43`:
```python
tool = obj.get("tool") or (obj.get("function") or {}).get("tool", "")
```

When `obj["function"]` is a string (e.g. `"checkout"`), the expression
`(obj.get("function") or {})` evaluates to `"checkout"` (truthy string),
and `.get("tool", "")` raises `AttributeError`. For task t21 (checkout task),
the LLM produces JSON with a `"function"` string field, triggering this path.
Exception propagates unhandled from `run_pipeline` → harness shows crash, no answer.

### Fix — two levels

**Level 1: fix `_obj_mutation_tool` in `json_extract.py`:**

```python
def _obj_mutation_tool(obj: dict) -> str | None:
    tool = obj.get("tool")
    if not tool:
        fn = obj.get("function")
        if isinstance(fn, dict):
            tool = fn.get("tool", "")
    return tool if tool in _MUTATION_TOOLS else None
```

Only calls `.get()` on `fn` when `fn` is confirmed to be a dict.

**Level 2: defensive wrapper in `run_pipeline`:**

Wrap the main `for cycle in range(_MAX_CYCLES):` loop in try/except:

```python
try:
    for cycle in range(_MAX_CYCLES):
        ...
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

`traceback` is already imported at `pipeline.py:9`.

## Test Plan

- Unit test for `_obj_mutation_tool` with `obj["function"]` as string → no crash, returns `None`.
- Unit test for `_extract_sku_refs` with `store_id` column → returns `/proc/stores/{id}.json`.
- Unit test for `_build_answer_user_msg` → AUTO_REFS contains full paths (no stem stripping).
- Unit test for `clean_refs` filter → exact match, not stem match.
- Existing pipeline tests must continue to pass.

## Files Changed

| File | Change |
|------|--------|
| `agent/pipeline.py` | Delete `_to_short_ref`; fix `_build_answer_user_msg`; fix `clean_refs` (×2); add `store_id` branch in `_extract_sku_refs`; wrap for-loop in try/except |
| `agent/json_extract.py` | Fix `_obj_mutation_tool` to guard `isinstance(fn, dict)` |
| `tests/test_ref_bugs.py` | New test file covering all 4 unit tests above |
