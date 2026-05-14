# Grounding Refs Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `t16` "invalid grounding refs" by normalizing all catalogue paths to short-form `/proc/catalog/{SKU}.json` before sending to the VM.

**Architecture:** Add `_to_short_ref(path)` as the single normalization point; call it in `_build_answer_user_msg` (so the model sees short-form AUTO_REFS) and in `clean_refs` (so the VM always receives short-form refs regardless of what the model produces). Raw paths stay verbatim in `sku_refs`.

**Tech Stack:** Python 3.11+, pathlib.Path (already imported), pytest

---

## File Map

| File | Action |
|------|--------|
| `agent/pipeline.py` | Add `_to_short_ref`, update `_build_answer_user_msg` (line 264), update `clean_refs` (line 574) |
| `data/prompts/answer.md` | Update grounding_refs instruction (line 16) and Forbidden sources block (lines 35–42) |
| `tests/test_pipeline_sku_refs.py` | Add 3 new test cases |

---

### Task 1: Write 3 failing tests

**Files:**
- Modify: `tests/test_pipeline_sku_refs.py`

- [ ] **Step 1: Add tests at end of file**

Append to `tests/test_pipeline_sku_refs.py` (after line 46, after the last existing test):

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
        ["sku\nHND-6D7TN1CT\n"],
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

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent
uv run pytest tests/test_pipeline_sku_refs.py -v 2>&1 | tail -30
```

Expected:
- `test_extract_sku_refs_hierarchical_path_preserved` — PASS (existing behavior already stores path verbatim)
- `test_build_answer_user_msg_normalizes_hierarchical_ref` — FAIL (`"hand_tools/subcat" not in msg` assertion fails)
- `test_clean_refs_stem_match_normalizes` — ERROR (`ImportError: cannot import name '_to_short_ref'`)

---

### Task 2: Add `_to_short_ref` and update `_build_answer_user_msg`

**Files:**
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Add `_to_short_ref` after imports block**

In `agent/pipeline.py`, insert after line 34 (the `from .trace import get_trace` import), before line 36 (`_MAX_CYCLES = ...`):

```python
def _to_short_ref(path: str) -> str:
    return f"/proc/catalog/{Path(path).stem}.json"

```

`Path` is already imported on line 9.

- [ ] **Step 2: Update `_build_answer_user_msg` to normalize AUTO_REFS**

Replace in `agent/pipeline.py` (current lines 264–272):

```python
def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    refs_block = "\n".join(auto_refs)
    return (
        base
        + f"\n\nAUTO_REFS (from sku column in SQL results — MUST be included in grounding_refs):\n{refs_block}"
    )
```

With:

```python
def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
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

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_pipeline_sku_refs.py -v 2>&1 | tail -30
```

Expected:
- `test_extract_sku_refs_hierarchical_path_preserved` — PASS
- `test_build_answer_user_msg_normalizes_hierarchical_ref` — PASS
- `test_clean_refs_stem_match_normalizes` — PASS (`_to_short_ref` now importable)

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests pass, no regressions.

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline_sku_refs.py
git commit -m "feat: add _to_short_ref, normalize AUTO_REFS to short-form paths"
```

---

### Task 3: Update `clean_refs` filter to stem-based matching

**Files:**
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Replace `clean_refs` line**

In `agent/pipeline.py`, find line 574 (after the `result_skus` line):

```python
clean_refs = [r for r in answer_out.grounding_refs if r in sku_refs or not result_skus]
```

Replace with:

```python
clean_refs = (
    [_to_short_ref(r) for r in answer_out.grounding_refs if Path(r).stem in result_skus]
    if result_skus else list(answer_out.grounding_refs)
)
```

`result_skus` is computed on the line immediately above (line 570):
```python
result_skus = {Path(r).stem for r in sku_refs}
```
Do not add or change that line — it already exists.

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add agent/pipeline.py
git commit -m "fix: clean_refs uses stem-based match, always outputs short-form refs"
```

---

### Task 4: Update `answer.md` prompt

**Files:**
- Modify: `data/prompts/answer.md`

- [ ] **Step 1: Update the grounding_refs instruction (line 16)**

In `data/prompts/answer.md`, replace:

```
- `grounding_refs` MUST list the full catalogue path for every product in the results. Use the `path` column value from SQL results directly — do NOT construct paths from `sku`.
```

With:

```
- `grounding_refs` MUST list catalogue paths for every product in the results. Use values from AUTO_REFS exactly as shown — do NOT construct paths manually from `sku` or raw `path` column values.
```

- [ ] **Step 2: Update first line of Forbidden sources block (line 37)**

In `data/prompts/answer.md`, replace:

```
- Paths constructed from `sku` formula (e.g. `/proc/catalog/{sku}.json`) — the `path` column is authoritative.
```

With:

```
- Paths constructed manually from `sku` (e.g. `/proc/catalog/{sku}.json`) or raw `path` column — use AUTO_REFS values instead.
```

Leave the other two Forbidden sources lines unchanged.

- [ ] **Step 3: Verify prompt file looks correct**

```bash
grep -n "grounding_refs\|AUTO_REFS\|Forbidden\|path column" data/prompts/answer.md
```

Expected: line 16 shows updated grounding_refs instruction; line 37 shows "use AUTO_REFS values instead"; no remaining "path column is authoritative" or "use path column value directly".

- [ ] **Step 4: Commit**

```bash
git add data/prompts/answer.md
git commit -m "docs: update answer.md grounding_refs to reference AUTO_REFS, not path column"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v 2>&1 | tail -50
```

Expected: all tests pass.

- [ ] **Step 2: Verify `_to_short_ref` is exported-accessible**

```bash
python -c "from agent.pipeline import _to_short_ref; print(_to_short_ref('/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json'))"
```

Expected output:
```
/proc/catalog/HND-6D7TN1CT.json
```

- [ ] **Step 3: Confirm no remaining raw-path usage in answer path**

```bash
grep -n "refs_block\|auto_refs\|sku_refs\|clean_refs" agent/pipeline.py
```

Check:
- `refs_block` built from `short_refs` (normalized), not `auto_refs` directly
- `clean_refs` uses `_to_short_ref` + stem match, not `r in sku_refs`
