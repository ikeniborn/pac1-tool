# Grounding Refs Normalization — Design

**Date:** 2026-05-14  
**Status:** Approved

## Problem

`t16` fails with "invalid grounding refs". Root cause: `_extract_sku_refs` stores raw `p.path` values verbatim (e.g. `/proc/catalog/hand_tools/.../HND-6D7TN1CT.json`). These raw paths propagate through `AUTO_REFS` to the model and through `clean_refs` to `vm.answer`. The harness only accepts short-form refs (`/proc/catalog/{SKU}.json`).

Two failure modes:
- **Mode A**: model uses full path from `AUTO_REFS` → `clean_refs` exact-match passes → VM rejects full path
- **Mode B**: model constructs short path from SKU → NOT in `sku_refs` (full paths) → filtered out → empty refs → VM error

Secondary issue: `clean_refs` filter uses exact string match (`r in sku_refs`), which silently drops valid refs on any format mismatch.

`check_grounding_refs` is stem-based (correct) — no change needed.

## Design

### 1. Helper function `_to_short_ref`

```python
def _to_short_ref(path: str) -> str:
    return f"/proc/catalog/{Path(path).stem}.json"
```

Single normalization point. All output-facing code calls this.

### 2. `sku_refs` storage — no change

`sku_refs: list[str]` keeps raw paths from DB. Preserves full path for future use cases (e.g. hierarchical display, logging). `_extract_sku_refs` unchanged.

### 3. `_build_answer_user_msg` — normalize AUTO_REFS

```python
def _build_answer_user_msg(task_text, sql_results, auto_refs):
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    short_refs = [_to_short_ref(r) for r in auto_refs]
    refs_block = "\n".join(short_refs)
    return (
        base
        + f"\n\nAUTO_REFS (catalogue paths for grounding_refs — use exactly as shown):\n{refs_block}"
    )
```

Model sees short-form paths → learns correct output format. Label updated to be format-neutral.

### 4. `clean_refs` filter — stem-based matching

Replace:
```python
clean_refs = [r for r in answer_out.grounding_refs if r in sku_refs or not result_skus]
```

With:
```python
clean_refs = (
    [_to_short_ref(r) for r in answer_out.grounding_refs if Path(r).stem in result_skus]
    if result_skus else list(answer_out.grounding_refs)
)
```

`result_skus` is already computed on the line above (`result_skus = {Path(r).stem for r in sku_refs}`) and passed to `check_grounding_refs` — do not recompute it. Only the `clean_refs` line is replaced.

Stem-based match tolerates any path format from the model. Output is always short-form → VM accepts.

### 5. `answer.md` prompt update

Replace:
> `grounding_refs` MUST list the full catalogue path for every product in the results. Use the `path` column value from SQL results directly — do NOT construct paths from `sku`.

With:
> `grounding_refs` MUST list catalogue paths for every product in the results. Use values from AUTO_REFS exactly as shown — do NOT construct paths manually from `sku` or raw `path` column values.

Update `Forbidden sources` block — keep the prohibition on manual path construction, but update the wording: "Paths constructed manually from `sku` (e.g. `/proc/catalog/{sku}.json`) or raw `path` column — use AUTO_REFS values instead." The prohibition itself stays; only the positive instruction changes from "use path column" to "use AUTO_REFS".

### 6. Tests

Add to `tests/test_pipeline_sku_refs.py`:

```python
def test_extract_sku_refs_hierarchical_path_preserved():
    """Raw hierarchical paths stored verbatim in sku_refs."""
    results = ["path,sku\n/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json,HND-6D7TN1CT\n"]
    refs = _extract_sku_refs(["SELECT p.path, p.sku FROM products p"], results)
    assert refs == ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"]

def test_build_answer_user_msg_normalizes_hierarchical_ref():
    """AUTO_REFS block shows short-form refs regardless of raw path depth."""
    msg = _build_answer_user_msg(
        "find hand tool",
        ["path,sku\n/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json,HND-6D7TN1CT\n"],
        ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"],
    )
    assert "/proc/catalog/HND-6D7TN1CT.json" in msg
    assert "hand_tools/subcat" not in msg

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

## Files Changed

| File | Change |
|------|--------|
| `agent/pipeline.py` | Add `_to_short_ref`, update `_build_answer_user_msg`, update `clean_refs` filter |
| `data/prompts/answer.md` | Update grounding_refs instruction and Forbidden sources |
| `tests/test_pipeline_sku_refs.py` | Add 3 new test cases |

## Not Changed

- `_extract_sku_refs` — raw paths preserved
- `check_grounding_refs` — already stem-based, correct
- `sku_refs` storage type — `list[str]` unchanged
