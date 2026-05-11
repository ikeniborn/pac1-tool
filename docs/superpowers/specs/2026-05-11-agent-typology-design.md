# Agent Re-Architecture: Type/Subtype System

**Date:** 2026-05-11  
**Baseline:** run `20260511_134122_qwen3.5-cloud` — 50% score (6/12 tasks)  
**Scope:** Full re-architecture — task_types.json, prephase, FIX-345, prompt blocks, DSPy Signatures

---

## 1. Problem Statement

All 12 ecom1-dev tasks are classified as `lookup`, but they have fundamentally different execution requirements. The agent treats them identically → 4 distinct failure modes:

| Failure | Tasks | Root Cause |
|---------|-------|------------|
| Context overflow | t04, t08, t12 | Prephase reads 9000+ catalog files → 1.6M tok > 262K limit |
| No answer | t06 | SQL timeout → Pydantic stall validation error → task abandoned |
| Grounding gate loop | t07 | FIX-345 blocks report_completion for pure SQL tasks |
| Missing ref | t01 | Prompt doesn't require specific `/proc/catalog/SKU.json` in grounding_refs |

Additionally: t11 (success) consumed 1.56M tokens for a 1-step SQL count — near-overflow, unsustainable.

---

## 2. Task Typology (ecom1-dev analysis)

### Observed subtypes from logs

| Subtype | Tasks | Question Pattern | Correct Strategy |
|---------|-------|-----------------|-----------------|
| `sql_count` | t09, t10, t11, t12 | "How many catalogue products are X?" | `SELECT COUNT(*)` — 1 SQL step |
| `sql_attr` | t01, t02, t03 | "Do you have X with attribute Y?" (standard attr) | SQL exact match, cite SKU file |
| `sql_negative` | t05, t06, t07, t08 | "Do you have X with [Bluetooth/app-scheduling]?" | Schema check first → likely immediate NO |
| `sql_broad` | t04 | "Do you have X?" (broad category, many SKUs) | SQL only, never filesystem scan |

### Subtype discovery: open-set problem

New benchmarks will introduce unknown subtypes. The agent must not silently fall back — it must surface gaps.

---

## 3. Architecture: type:subtype Hierarchy

### 3.1 `task_types.json` extension

Add `subtypes` dict and `default_subtype` per type. Existing fields (`model_env`, `fallback_chain`, etc.) unchanged.

```json
{
  "lookup": {
    "description": "...",
    "model_env": "MODEL_LOOKUP",
    "fallback_chain": ["..."],
    "wiki_folder": "lookup",
    "fast_path": "(?i)\\b(find|lookup|search|do you have|how many)\\b",
    "needs_builder": true,
    "status": "stable",
    "prephase_strategy": "standard",
    "subtypes": {
      "sql_count": {
        "prephase_strategy": "none",
        "discovery_gate_exempt": true,
        "needs_builder": false,
        "description": "Count products by kind — single SQL COUNT(*) query"
      },
      "sql_attr": {
        "prephase_strategy": "minimal",
        "discovery_gate_exempt": true,
        "needs_builder": true,
        "description": "Attribute existence check on specific product — SQL match + cite SKU file"
      },
      "sql_negative": {
        "prephase_strategy": "minimal",
        "discovery_gate_exempt": true,
        "needs_builder": false,
        "description": "Attribute check where attribute likely absent from schema — schema check first"
      },
      "sql_broad": {
        "prephase_strategy": "minimal",
        "discovery_gate_exempt": true,
        "needs_builder": true,
        "description": "Attribute check across broad product category — SQL only, no filesystem"
      }
    },
    "default_subtype": "sql_attr"
  }
}
```

All other types (`email`, `crm`, `temporal`, etc.) gain `subtypes: {}` and `default_subtype: null` — no behaviour change until subtypes are added.

### 3.2 `agent/task_types.py` changes

```python
def get_subtype_config(task_type: str, task_subtype: str | None) -> dict:
    """Returns merged config: type defaults overridden by subtype fields."""
    type_cfg = REGISTRY[task_type]
    if not task_subtype:
        return type_cfg
    subtypes = type_cfg.get("subtypes", {})
    return {**type_cfg, **subtypes.get(task_subtype, {})}

def is_discovery_gate_exempt(task_type: str, task_subtype: str | None) -> bool:
    return get_subtype_config(task_type, task_subtype).get("discovery_gate_exempt", False)

def get_prephase_strategy(task_type: str, task_subtype: str | None) -> str:
    return get_subtype_config(task_type, task_subtype).get("prephase_strategy", "standard")
```

---

## 4. Subtype Discovery Pipeline

### Flow

```
task arrives
     ↓
classifier outputs {type, subtype, subtype_reason, subtype_strategy_hint}
     ↓
task_types.py: is subtype in valid_subtypes?
     ↓ YES                        ↓ NO
use subtype config         log_subtype_candidate()
                           use default_subtype config
                                   ↓
                          run-end summary in wiki-lint phase
                                   ↓
                          manual: add to task_types.json (status:soft)
                                   ↓
                          recompile classifier DSPy
```

### `data/subtype_candidates.jsonl` schema

```jsonl
{
  "task_type": "lookup",
  "proposed_subtype": "new:inventory_write_check",
  "reason": "task asks to verify stock level and update inventory",
  "suggested_strategy": "minimal",
  "task_text": "Check if product X is in stock and reserve 3 units",
  "timestamp": "2026-05-11T12:00:00Z",
  "run_id": "run-abc123",
  "count": 1
}
```

### `agent/maintenance/subtype_candidates.py`

```python
# Usage: uv run python -m agent.maintenance.subtype_candidates
# Shows candidates, offers interactive promotion to task_types.json
```

### Run-end warning (wiki-lint phase)

```
[SUBTYPE CANDIDATES] 2 new subtypes proposed this run:
  lookup → 'new:count_by_category_sql' (3 occurrences) — suggested strategy: none
  lookup → 'new:inventory_check_write'  (1 occurrence) — suggested strategy: minimal
  → Review: uv run python -m agent.maintenance.subtype_candidates
```

### Classifier subtype detection hints

The classifier (LLM) needs signal to distinguish subtypes. Key patterns:

| Pattern in task text | Likely subtype |
|---------------------|---------------|
| "How many catalogue products are X?" | `sql_count` |
| "Do you have X with [Bluetooth/app-scheduling/IoT/smart]?" | `sql_negative` |
| "Do you have X with [standard attr: wattage/color/size]?" across many SKUs | `sql_broad` |
| "Do you have X with [standard attr]?" with specific brand+model | `sql_attr` |

These patterns go into the `ClassifyTask` docstring and DSPy few-shot examples — not hardcoded regex.

### DSPy Classifier Signature additions

```python
class ClassifyTask(dspy.Signature):
    task_text         = dspy.InputField()
    task_type         = dspy.OutputField(desc="one of VALID_TYPES")
    task_subtype      = dspy.OutputField(
        desc="matching subtype key, or 'new:<proposed_name>' if no match"
    )
    task_subtype_reason = dspy.OutputField(desc="one-sentence justification")
    task_subtype_strategy_hint = dspy.OutputField(
        desc="only when new: — one of none|minimal|standard"
    )
```

---

## 5. Prephase Strategy Dispatch

### `prephase.py` refactor

```python
STRATEGY_DISPATCH = {
    "none":     _strategy_none,
    "minimal":  _strategy_minimal,
    "standard": _strategy_standard,
    "full":     _strategy_full,   # deprecated, legacy only
}

async def run_prephase(task_type, task_subtype, task_text, vm):
    strategy = get_prephase_strategy(task_type, task_subtype)
    log.info(f"[prephase] strategy={strategy} (type={task_type}, subtype={task_subtype})")
    return await STRATEGY_DISPATCH[strategy](task_text, vm)
```

### Strategy implementations

**`_strategy_none`** — sql_count, sql_broad:
- Calls: `tree(level=2, root="/")` + `read("/AGENTS.MD")` + `context()`
- ~3K tokens. No catalog reads.

**`_strategy_minimal`** — sql_attr, sql_negative:
- Calls: `tree(level=2, root="/")` + `read("/AGENTS.MD")` + `context()` + `read("/bin/sql")`
- ~5K tokens. Agent enters loop knowing SQL interface.

**`_strategy_standard`** — all other types (no subtype):
- Current behaviour + hard cap: `PREPHASE_MAX_READS` (env, default 200).
- Logs warning when cap hit.

**`_strategy_full`** — legacy, deprecated:
- Current uncapped behaviour. Only used if explicitly set. Prints deprecation warning.

### Prephase strategy by subtype (corrected)

| Subtype | Strategy | Reads | Rationale |
|---------|----------|-------|-----------|
| `sql_count` | `none` | 3 | No SQL interface needed — AGENTS.MD mentions `/bin/sql`, agent discovers on first step |
| `sql_attr` | `minimal` | 4 | Pre-load `/bin/sql` spec — agent needs exact syntax for property LIKE queries |
| `sql_negative` | `minimal` | 4 | Pre-load `/bin/sql` spec — `.schema` call is step 1 |
| `sql_broad` | `minimal` | 4 | Pre-load `/bin/sql` spec — broad SQL query needs interface knowledge upfront |

Note: `sql_count` uses `none` because the query pattern ("How many X?") is trivially translatable to `COUNT(*)` without needing the full `/bin/sql` spec page.

### Token impact (projected)

| Task | Before | After |
|------|--------|-------|
| t04, t08, t12 | 1.6M tok → overflow | ~5K tok (sql_broad: none) |
| t09, t10, t11, t12 | 87K–1.5M tok | ~3K tok (sql_count: none) |
| t01, t02, t03 | 19K–750K tok | ~5K tok (sql_attr: minimal) |

---

## 6. FIX-345 Revocation for SQL Subtypes

FIX-345 blocks `report_completion` when no vault discovery tool has been called. For SQL subtypes, `/bin/sql` IS vault discovery.

### `loop.py` / `security.py` change

```python
def check_discovery_gate(task_type, task_subtype, tool_history):
    # Exempt subtypes bypass entirely
    if is_discovery_gate_exempt(task_type, task_subtype):
        return True

    # SQL exec counts as vault discovery for all lookup types
    sql_calls = [
        t for t in tool_history
        if t.tool == "exec" and t.path == "/bin/sql"
    ]
    if sql_calls:
        return True

    # Original FIX-345 logic
    return has_vault_discovery(tool_history)
```

---

## 7. Per-Subtype Prompt Blocks

### `prompt.py` — two-level `_TASK_BLOCKS`

```python
def get_task_block(task_type: str, task_subtype: str | None) -> str:
    type_blocks = _TASK_BLOCKS.get(task_type, {})
    if task_subtype and task_subtype in type_blocks:
        return type_blocks[task_subtype]
    return type_blocks.get("_default", _TASK_BLOCKS["default"])
```

### Block content

**`lookup/sql_count`:**
```
TASK: catalogue count query

1. GET kind_id: SELECT id FROM product_kinds WHERE name LIKE '%X%'
2. COUNT: SELECT COUNT(*) FROM products WHERE kind_id = ?
3. Report '<COUNT:n>' exactly as required by task.
Grounding refs: ["/bin/sql"]
No file reads needed.
```

**`lookup/sql_attr`:**
```
TASK: catalogue attribute check (specific product)

1. SQL: SELECT sku, properties FROM products
        WHERE brand=? AND model=? AND properties LIKE '%attr%value%'
2. Answer with <YES> or <NO> token.
3. REQUIRED — grounding_refs must include exact product file:
   "/proc/catalog/<category>/<kind>/<family>/<SKU>.json"
   A directory path alone is insufficient and will fail grading.
```

**`lookup/sql_negative`:**
```
TASK: catalogue attribute check (attribute may not exist in schema)

1. FIRST: /bin/sql '.schema' — check if attribute column exists.
2. Non-standard attributes (Bluetooth, app-scheduling, IoT, smart-home)
   are NOT in the catalogue schema — answer <NO> immediately citing schema.
3. If attribute IS in schema: run targeted SQL query.
4. SQL timeout: retry once, then use search as fallback.
Grounding refs: schema result or specific product file.
```

**`lookup/sql_broad`:**
```
TASK: catalogue attribute check (broad product category)

NEVER read individual catalogue files — catalogue has thousands of files
and reading them causes context window overflow.

1. SQL only: SELECT sku, properties FROM products
             WHERE kind_id=? AND brand=? AND model=? AND properties LIKE ?
2. Filter results in-memory if needed.
3. Answer <YES>/<NO> with SQL result as grounding.
```

### Evaluator grounding_refs enforcement

```python
# evaluator.py
if task_subtype == "sql_attr" and "<YES>" in message:
    has_sku_ref = any(
        re.match(r"/proc/catalog/.+\.json$", ref)
        for ref in grounding_refs
    )
    if not has_sku_ref:
        add_objection("grounding_refs must include specific /proc/catalog/SKU.json path")
```

---

## 8. SQL Timeout Fix (t06)

```python
# dispatch.py — exec tool retry
MAX_SQL_RETRIES = int(os.getenv("SQL_MAX_RETRIES", "1"))
SQL_RETRY_DELAY = float(os.getenv("SQL_RETRY_DELAY_S", "2.0"))

async def _exec_with_retry(vm, cmd):
    for attempt in range(MAX_SQL_RETRIES + 1):
        try:
            return await vm.exec(cmd)
        except (TimeoutError, asyncio.TimeoutError):
            if attempt < MAX_SQL_RETRIES:
                log.warning(f"[dispatch] SQL timeout attempt {attempt+1}, retrying")
                await asyncio.sleep(SQL_RETRY_DELAY)
                continue
            raise
```

Also fix: Pydantic validation error in `StallRequest.error_counts` — key must be `str`, not `tuple`. Replace `(tool, path, "EXCEPTION")` key with `f"{tool}:{path}:EXCEPTION"`.

---

## 9. DSPy Signature Changes Summary

| Module | Field | Change |
|--------|-------|--------|
| `classifier.py` | `task_subtype` | New OutputField |
| `classifier.py` | `task_subtype_reason` | New OutputField |
| `classifier.py` | `task_subtype_strategy_hint` | New OutputField (only when new:) |
| `prompt_builder.py` | `task_subtype` | New InputField |
| `evaluator.py` | `task_subtype` | New InputField |

### Recompilation order

```bash
# After collecting examples from updated benchmark run:
uv run python scripts/optimize_prompts.py --target classifier   # subtype prediction
uv run python scripts/optimize_prompts.py --target builder      # subtype-aware addendum
uv run python scripts/optimize_prompts.py --target evaluator    # subtype-aware scoring
```

Existing compiled programs fail-open — agent runs on default prompts until recompiled.

---

## 10. Implementation Scope

### Files to change

| File | Change |
|------|--------|
| `data/task_types.json` | Add `subtypes`, `default_subtype`, `prephase_strategy` per type |
| `agent/task_types.py` | `get_subtype_config()`, `is_discovery_gate_exempt()`, `get_prephase_strategy()` |
| `agent/prephase.py` | Strategy dispatch, 4 strategy implementations, cap for standard |
| `agent/prompt.py` | Two-level `_TASK_BLOCKS`, `get_task_block(type, subtype)` |
| `agent/classifier.py` | New DSPy OutputFields, subtype validation, candidate logging |
| `agent/loop.py` | Pass subtype through pipeline, FIX-345 bypass |
| `agent/security.py` | `check_discovery_gate()` — SQL counts as discovery |
| `agent/evaluator.py` | New InputField `task_subtype`, grounding_refs enforcement |
| `agent/prompt_builder.py` | New InputField `task_subtype` |
| `agent/dispatch.py` | SQL retry logic, StallRequest key fix |
| `agent/maintenance/subtype_candidates.py` | New file — candidate review CLI |
| `agent/__init__.py` | Pass subtype through run_agent() call chain |

### Out of scope

- Changes to non-lookup task types (email, crm, etc.) — subtypes field added but empty
- Wiki/graph changes
- benchmark harness changes

---

## 11. Success Criteria

| Metric | Target |
|--------|--------|
| ecom1-dev score | ≥ 83% (10/12) — t04/t08 may still need SQL schema investigation |
| Max tokens per task | < 50K (currently up to 1.5M) |
| Prephase reads for sql_count | 3 (was up to 9896) |
| t06 failure mode | Retry SQL → get answer |
| t07 failure mode | FIX-345 exempt → report_completion accepted |
| t01 failure mode | Evaluator enforces SKU ref → model includes it |
| New subtype surfacing | Candidates logged, run-end summary shown |
