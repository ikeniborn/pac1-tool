# Design: Remove RESEARCHER Mode

**Date:** 2026-04-28  
**Approach:** A — Full surgical deletion  
**Success criteria:** `uv run python -m pytest tests/` passes; `python -c "from agent import run_agent"` works without errors.

---

## Overview

Remove the RESEARCHER multi-cycle mode entirely from the codebase. The RESEARCHER mode is cleanly isolated behind a single `RESEARCHER_MODE=1` env flag and an entry-point branch in `agent/__init__.py`. Normal mode code is shared but parametrized with a `researcher_mode` boolean — those parameters and branches will be removed, leaving a simpler direct path.

**What stays:** wiki.py, wiki_graph.py, promote_successful_pattern(), promote_verified_refusal(), all normal-mode promotion flows, evaluator, stall detector, loop timeout — everything that normal mode uses.

**What goes:** researcher.py, reflector.py, all `researcher_mode` parameter branches, researcher-specific data artifacts.

---

## Files to Delete Entirely

| File | Reason |
|---|---|
| `agent/researcher.py` | Entire outer-cycle orchestrator, exclusive to researcher |
| `agent/reflector.py` | Used only by researcher.py for per-cycle reflection |

---

## Code Changes

### `agent/__init__.py`

Remove:
- Line 27: `_RESEARCHER_MODE = os.getenv("RESEARCHER_MODE", "0") == "1"`
- Lines 99–114: entire `if _RESEARCHER_MODE: ... return run_researcher(...)` block including the lazy `from .researcher import run_researcher` import

Result: `run_agent()` goes straight to normal-mode pipeline (prephase → router → builder → loop).

### `agent/loop.py`

Remove `researcher_mode` parameter and its branches:

1. **`run_loop()` signature** — remove parameters:
   - `researcher_mode: bool = False`
   - `researcher_breakout_check: Callable | None = None`
   - `_LoopState.researcher_mode` field assignment

2. **Timeout gate (~line 1981)** — unwrap condition:
   ```python
   # Before: if not st.researcher_mode and elapsed_task > TASK_TIMEOUT_S:
   # After:  if elapsed_task > TASK_TIMEOUT_S:
   ```

3. **Stall gate (~line 2062)** — unwrap condition:
   ```python
   # Before: if not st.researcher_mode: _handle_stall_retry(...)
   # After:  _handle_stall_retry(...)
   ```

4. **Soft stall advisory (~lines 2069–2076)** — delete entire block (researcher-only path under `if st.researcher_mode`).

5. **Evaluator gate (~line 2179)** — remove `and not st.researcher_mode` clause.

6. **Mid-cycle breakout check (~lines 2471–2482)** — delete entire block (calls `researcher_breakout_check` callback).

### `main.py`

Remove two score-gated researcher promotion blocks after `end_trial()`:

- Lines 344–363: `if stats.get("researcher_pending_promotion") and score == 1.0: promote_successful_pattern(...)`
- Lines 364–376: `if stats.get("researcher_pending_refusal") and score == 1.0: promote_verified_refusal(...)`

Keep: lines 378–426 (normal-mode promotion), lines 333–343 (normal-mode fragment write).

Also remove any `if stats.get("researcher_mode")` guards in logging/stats sections if present.

### `.env.example`

Remove entire `RESEARCHER_*` variable block (~40 lines, FIX-362 through FIX-376):

```
RESEARCHER_MODE, RESEARCHER_MAX_CYCLES, RESEARCHER_STEPS_PER_CYCLE,
MODEL_RESEARCHER, RESEARCHER_LOG_ENABLED, RESEARCHER_NEGATIVES_ENABLED,
RESEARCHER_NEGATIVES_TOP_K, RESEARCHER_SHORT_CIRCUIT,
RESEARCHER_SHORT_CIRCUIT_THRESHOLD, RESEARCHER_DRIFT_HINTS,
RESEARCHER_DRIFT_PREFIX_LEN, RESEARCHER_EVAL_GATED,
RESEARCHER_EVAL_SKEPTICISM, RESEARCHER_EVAL_EFFICIENCY,
RESEARCHER_FLIP_HINT_ENABLED, RESEARCHER_FLIP_REASON_SIMILARITY_THRESHOLD,
RESEARCHER_FLIP_HYP_MONOTONIC_K, RESEARCHER_FLIP_HYP_SIMILARITY_THRESHOLD,
RESEARCHER_REFUSAL_LAST_CHANCE, RESEARCHER_OK_LOOP_LIMIT,
RESEARCHER_EVAL_FAIL_CLOSED, RESEARCHER_HINT_FORCING,
RESEARCHER_HINT_MAX_INJECTIONS, RESEARCHER_MIDCYCLE_BREAKOUT,
RESEARCHER_MIDCYCLE_CHECK_EVERY, RESEARCHER_MIDCYCLE_REPEAT_THRESHOLD,
RESEARCHER_REFLECTOR_DIVERSIFY, RESEARCHER_REFLECTOR_PRIOR_WINDOW,
RESEARCHER_STEPS_ADAPTIVE, RESEARCHER_STEPS_MAX,
RESEARCHER_TOTAL_STEP_BUDGET, RESEARCHER_SOFT_STALL,
RESEARCHER_REFUSAL_DYNAMIC, RESEARCHER_REFUSAL_MIN_CYCLES_LEFT,
RESEARCHER_GRAPH_QUARANTINE, RESEARCHER_GRAPH_MIN_CONF,
RESEARCHER_DRIFT_FULL_TRACE, RESEARCHER_DRIFT_LCS_MIN
```

Keep: `WIKI_GRAPH_*`, `EVALUATOR_*`, `MODEL_*`, `CC_*`, and all other non-researcher variables.

---

## Data Cleanup

```bash
# Delete researcher-exclusive artifact directories
rm -rf data/wiki/fragments/research/
rm -rf data/wiki/archive/research_negatives/
rm -rf logs/researcher/

# graph.json: nodes have no source field, so researcher nodes can't be
# distinguished. Archive and reset to empty — normal mode rebuilds via
# WIKI_GRAPH_AUTOBUILD and WIKI_GRAPH_FEEDBACK.
mv data/wiki/graph.json data/wiki/graph.json.bak 2>/dev/null || true
echo '{"nodes": {}, "edges": []}' > data/wiki/graph.json
# data/dspy_eval_examples.jsonl — keep (normal mode also writes to it)
# data/wiki/pages/ — keep (promoted patterns from researcher stay as wiki knowledge)
```

`data/wiki/pages/` retains promoted patterns — they were score-gated (score==1.0) and represent validated task knowledge. Normal mode reads them via `load_wiki_patterns()`.

---

## What Stays Unchanged

| Component | Status |
|---|---|
| `agent/wiki.py` | Unchanged — used by normal mode |
| `agent/wiki_graph.py` | Unchanged — used by normal mode and evaluator |
| `agent/evaluator.py` | Unchanged — now always enabled in loop |
| `agent/stall.py` | Unchanged — now always active in loop |
| `agent/classifier.py` | Unchanged — fast regex path exists independently |
| `agent/prompt_builder.py` | Unchanged — DSPy builder for normal mode |
| `data/wiki/pages/` | Unchanged — validated patterns stay |
| `data/dspy_examples.jsonl` | Unchanged — normal mode training data |

---

## Verification

```bash
# 1. Import check
uv run python -c "from agent import run_agent; print('OK')"

# 2. Full test suite
uv run python -m pytest tests/

# 3. Confirm no researcher references remain
grep -r "RESEARCHER_MODE\|researcher_mode\|run_researcher\|from .researcher\|from agent.researcher\|reflector" agent/ main.py --include="*.py"
```

All three commands must pass cleanly.

---

## Implementation Order

1. Delete `agent/researcher.py`, `agent/reflector.py`
2. Edit `agent/__init__.py` — remove `_RESEARCHER_MODE` and `if _RESEARCHER_MODE` block
3. Edit `agent/loop.py` — remove parameter, unwrap branches, delete exclusive blocks
4. Edit `main.py` — remove researcher promotion blocks
5. Edit `.env.example` — remove RESEARCHER_* section
6. Run import check + tests
7. Data cleanup: `rm -rf` on researcher artifact dirs + graph.json filtering script
8. Final verification run
