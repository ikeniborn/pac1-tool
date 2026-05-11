# SQL Adaptation Design — ecom1-agent

**Date:** 2026-05-11  
**Scope:** Fix 4/10 lookup failures + prepare for future SQL task types  
**Benchmark:** PAC1 (fixed, гRPC/Connect harness), MAX_STEPS=5

---

## Problem

All 10 `dspy_examples.jsonl` tasks are `lookup` type. 4/10 score 0.0. Root cause:
- Few-shot example shows `list /notes` → model copies file-traversal pattern
- With MAX_STEPS=5, file traversal (tree→list→read×N) exhausts steps before answer
- Model ignores available `/bin/sql` tool even though it's in system prompt
- Model assumes attribute values without verifying (false positive / false negative)

## Architecture

### Execution Flow (unchanged structure)

```
Prephase (no LLM):
  tree -L 2 /
  read AGENTS.MD
  exec /bin/sql ".schema"     → SQL schema in context
  context()                   → timestamp

Agent loop (MAX_STEPS=5):
  Step 1: Analyse task + AGENTS.MD → decide if DISTINCT needed
           If AGENTS.MD covers needed attributes → skip to Step 2
           If AGENTS.MD silent → exec /bin/sql "SELECT DISTINCT <col> FROM <table>..."
  Step 2: exec /bin/sql "EXPLAIN SELECT ..."   → validate syntax + plan
  Step 3: exec /bin/sql "SELECT ..."           → get answer
  Step 4: report_completion
  (Step 5: spare — retry if EXPLAIN revealed error)
```

### Decision rule for ontology step

```
task_text + AGENTS.MD → identify needed attributes (brand, type, color_family, ...)
↓
AGENTS.MD defines exact values for those attributes?
  YES → use those values directly in SQL (saves 1 step)
  NO  → SELECT DISTINCT <attribute> FROM products
        WHERE <narrowing conditions from task> LIMIT 50
```

---

## Changed Files

### `agent/prephase.py` — few-shot replacement

Replace `_FEW_SHOT_USER / _FEW_SHOT_ASSISTANT` (currently defined in `prephase.py`) with SQL-first catalogue example:
- User: `"How many catalogue products are Lawn Mower?"`
- Assistant: `exec /bin/sql "EXPLAIN SELECT COUNT(*) FROM products WHERE type='Lawn Mower'"`

### `agent/prompt.py` — system prompt

Add `## CATALOGUE STRATEGY` section to `SYSTEM_PROMPT`:
   - HARD RULE: never use `list/find/read` on `/proc/catalog/` — use SQL only
   - Step order: check AGENTS.MD → DISTINCT if needed → EXPLAIN → SELECT → report
   - Pattern by question type:
     - `How many X?` → `SELECT COUNT(*) FROM products WHERE type='X'`
     - `Do you have X?` → `SELECT 1 FROM products WHERE brand=? AND type=? AND ...=? LIMIT 1`
   - Never assume attribute values — verify from AGENTS.MD or DISTINCT first

### `agent/prephase.py` — other changes

- Few-shot replacement (see above)
- `proc` already in skip set — prevents file-preloading catalog
- SQL schema fetch already present (`.schema`)
- No static DISTINCT queries — agent handles ontology dynamically per task

### `agent/orchestrator.py`

Add `DRY_RUN=1` mode:
- Run prephase only (tree, AGENTS.MD, schema)
- Skip LLM loop entirely
- Append to `data/dry_run_analysis.jsonl`:
  ```json
  {
    "task_id": "t01",
    "task_text": "...",
    "agents_md": "...",
    "sql_schema": "...",
    "timestamp": "2026-05-11T..."
  }
  ```
- Return stats with `outcome="DRY_RUN"` (trial still ends via `main.py`, score=0)

### `.env.example`

- Rename `MODEL_DEFAULT` → `MODEL` (single model, no routing)
- Remove all variables for non-existent subsystems:
  - DSPy: `EVALUATOR_*`, `CLASSIFIER_*`, `OPTIMIZER_*`, `GEPA_*`
  - Wiki: `WIKI_*`
  - Contracts: `MODEL_CONTRACT`, `ROUTER_*`
  - Multi-model routing: `MODEL_EMAIL`, `MODEL_LOOKUP`, etc.
  - CC tier variables: `CC_ENABLED`, `CC_MAX_RETRIES`, `ICLAUDE_CMD` (keep as optional comments)
- Keep: `MODEL`, `BENCHMARK_HOST`, `BENCHMARK_ID`, `BITGN_RUN_NAME`, `BITGN_API_KEY`,
  `LOG_LEVEL`, `PARALLEL_TASKS`, `TASK_TIMEOUT_S`, `MAX_STEPS`, `DRY_RUN`,
  `OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY` (in .secrets), `OPENROUTER_API_KEY` (in .secrets)

### `MODEL_DEFAULT` → `MODEL` rename

Touch: `agent/orchestrator.py`, `agent/dispatch.py`, `main.py`, `.env.example`

---

## Cleanup

### Delete from `agent/`

| File | Reason |
|---|---|
| `agent/contract_models.py` | Not imported by any active module |

### Delete from `tests/`

Delete all test files referencing non-existent modules. Keep:

| Keep | Reason |
|---|---|
| `test_json_extraction.py` | Tests `agent/json_extract.py` — active |
| `test_dispatch_transient.py` | Tests dispatch retry logic — active |
| `test_loop_json_parse.py` | Tests JSON parsing in loop — active |
| `test_prephase_vault_date.py` | Tests prephase — active |
| `test_loop_mutation_gate.py` | Tests write/delete guards in loop — active |
| `test_loop_agent_wiring.py` | Tests loop integration — active |
| `conftest.py` | Test fixtures |

Delete: `test_wiki_*` (14), `test_evaluator*` (3), `test_contract*` (4), `test_classifier*` (1),
`test_optimization*` (5), `test_maintenance*` (3), `test_log_compaction.py`, `test_task_types*` (2),
`test_capability_cache.py`, `test_security_gates.py`, `test_dspy_*` (1), `test_lifecycle.py`,
`test_distill_contracts.py`, `test_postrun_outcome_gate.py`

### Delete from `data/`

| Path | Reason |
|---|---|
| `data/default_contracts/` | Contract system removed |
| `data/prompts/` | DSPy prompt templates, no DSPy |
| `data/wiki/` | Wiki system not in agent |

Keep: `data/dspy_examples.jsonl` (active training data)

---

## Success Criteria

- `make run` → lookup tasks use SQL path (visible in step logs: `exec /bin/sql`)
- Score improvement: 4 failed tasks should pass (colour_family, brand+attribute combos)
- `DRY_RUN=1 make run` → produces `data/dry_run_analysis.jsonl`, no LLM cost
- `uv run python -m pytest tests/` → only kept tests run, all pass
- `.env.example` matches actual env vars used in code
