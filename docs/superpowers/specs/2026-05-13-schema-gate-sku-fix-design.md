# Design: schema_gate sqlglot + SKU auto-refs + sql_plan rules

**Date:** 2026-05-13  
**Context:** Run `logs/20260513_003838_minimax-m2.7-cloud` — 0/20 tasks scored. Two systemic bugs identified.

---

## Problem Summary

### Bug A — Missing grounding_refs (9 tasks: t01, t02, t13–t15, t17–t20)
SQL executes successfully but `grounding_refs` in ANSWER output is empty. Root cause: the model's SQL plan queries `brand`, `model`, `key` columns but never selects `sku`. The ANSWER phase has no SKU values to construct `/proc/catalog/{sku}.json` paths from.

### Bug B — SCHEMA gate cycles exhaust 3/3 (10 tasks: t03–t10, t12, t16)
Model uses exact literal `WHERE brand = 'Festool'` → SCHEMA gate blocks → LEARN fires → next cycle, same exact literal again → blocked again → 3 cycles exhausted → `OUTCOME_NONE_CLARIFICATION`. Root cause: LEARN error message says "run discovery first" but does not say *how* (use `LIKE '%term%'`). Additionally, current SCHEMA gate allows `'%Festool%'` (passes because `'%Festool%' not in task_text`) but blocks `'Festool%'` — model never tries LIKE form.

---

## Solution: 3 Components

### 1. `agent/schema_gate.py` — rewrite with sqlglot AST

Replace all regex-based checks with sqlglot AST traversal.

**Column validation (Check 1 + new table validation):**
- Parse `sqlglot.parse_one(q, dialect="sqlite")`
- Walk `exp.Column` nodes: validate `col.table` in `known_tables`, `col.name` in `known_cols`
- Error: `"unknown column: {name} (not in schema)"`

**Literal validation (Check 2) — context-aware:**
- Walk `exp.Literal` nodes
- Skip if value not in `task_text` or value in `all_confirmed`
- Skip if parent node is `exp.Like` or `exp.ILike` — these are discovery queries, allow
- Block otherwise with actionable message: `"unverified literal: '{val}' — use LIKE '%{val}%' for discovery"`

**Double-key JOIN (Check 3):**
- Walk `exp.Join` nodes where table alias matches `product_properties`
- Detect multiple `exp.EQ` conditions on `key` column in same WHERE scope
- Error: `"double-key JOIN on product_properties — use separate EXISTS subqueries"`

**Why sqlglot over regex:**
- Regex `r"'([^']+)'"` fires on literals in comments, string concatenations, EXPLAIN output
- `r'\b\w+\.(\w+)\b'` fires on aliases like `pp.sku` even when `sku` is a valid column
- AST is unambiguous; LIKE context detection is impossible with regex

### 2. `agent/pipeline.py` — auto-extract SKU refs

Add `_extract_sku_refs(queries: list[str], results: list[str]) -> list[str]`.

Logic:
- For each (query, result) pair: check if query SELECT list contains `sku` column
- Parse CSV result: find `sku` column by header name
- Collect unique values, build `/proc/catalog/{sku}.json` paths
- For queries against `stores` table: build `/proc/stores/{store_id}.json` from `store_id` column

Call site: after successful EXECUTE cycle, call `_extract_sku_refs(queries, sql_results)`.

Pass refs to `_build_answer_user_msg` as `auto_refs: list[str]`. Append to user message:
```
AUTO_REFS (extracted from sku column — MUST be included in grounding_refs):
/proc/catalog/FST-2JPIIG2S.json
```

This makes `grounding_refs` population independent of whether the model "figures out" the path format.

### 3. `data/prompts/sql_plan.md` — 3 targeted fixes

**Fix 1: Remove contradiction.**  
"Final query obligation" (include final query in same plan) contradicts "Discovery Query Isolation" (separate cycles). Remove "Final query obligation" section. Isolation rule is correct — keep it.

**Fix 2: Add LIKE-for-discovery rule.**  
Add to "String Literals in WHERE Clauses":
```
Discovery queries MUST use LIKE with % wildcards on both sides:
  SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'
Never: WHERE brand = 'Festool' (exact match on unconfirmed value — SCHEMA gate will block).
```

**Fix 3: Final SELECT must include sku.**  
Add rule: confirmation queries (last query in a plan) MUST project `p.sku`. Required for grounding_refs construction by ANSWER phase.

---

## Files Changed

| File | Change | Scope |
|---|---|---|
| `agent/schema_gate.py` | Full rewrite (~47 → ~80 lines) | medium |
| `agent/pipeline.py` | +`_extract_sku_refs()`, update `_build_answer_user_msg` | small |
| `data/prompts/sql_plan.md` | 3 targeted edits | small |
| `tests/test_schema_gate.py` | Update tests for new error messages + LIKE allowance | small |

---

## Success Criteria

- `test_schema_gate.py`: all existing tests pass with updated messages; new test confirms `LIKE '%val%'` is not blocked
- `make task TASKS='t01,t02,t05'`: t01/t02 score > 0 (grounding_refs populated); t05 exits cycle 1 with LIKE query instead of blocking
- No regression on currently passing behaviour (confirmed-value literals still allowed in `=` context)
