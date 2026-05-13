# Design: schema_gate sqlglot + SKU auto-refs + sql_plan rules

**Date:** 2026-05-13  
**Context:** Run `logs/20260513_003838_minimax-m2.7-cloud` — 0/20 tasks scored. Two systemic bugs identified.

---

## Problem Summary

### Bug A — Missing grounding_refs (t01, t02 confirmed; t13–t15, t17–t20 ambiguous)

SQL executes successfully but `grounding_refs` in ANSWER output is empty.

Confirmed cases (t01, t02): ANSWER phase ran with `OUTCOME_OK`, pipeline log shows answer submitted, but grader reports missing reference. Root cause: SQL plan queries `brand`, `model`, `key` columns but never selects `sku`. ANSWER phase has no SKU values → cannot construct `/proc/catalog/{sku}.json`.

Ambiguous cases (t13–t15, t17–t20): pipeline log shows "All 3 cycles exhausted — clarification" (Bug B), yet grader reports "answer missing required reference". This is a grader behaviour: refs checked even on `OUTCOME_NONE_CLARIFICATION`. These tasks fail from Bug B; fixing Bug B may expose them as Bug A too.

### Bug B — SCHEMA gate exhausts 3/3 cycles (t03–t10, t12, t16, t17–t20)

Model uses exact literal `WHERE brand = 'Festool'` → SCHEMA gate blocks → LEARN fires → next cycle, same exact literal again → blocked → 3 cycles exhausted → `OUTCOME_NONE_CLARIFICATION`.

Root cause: model (minimax-m2.7) does not adapt after LEARN. The LEARN rule says "run discovery first" but is not explicit enough: the model does not switch to `LIKE '%Festool%'`. Note: the current gate already allows `'Festool%'` and `'%Festool%'` (neither string appears verbatim in task_text), so the LIKE escape hatch exists — the model just never uses it. The fix is a clear rule in sql_plan.md, not a gate logic change.

The LIKE-context exception in schema_gate.py (see §1 below) is still valuable: it makes the gate's intent explicit in the AST layer and allows future literal forms that might appear in task_text.

### Bug C — Wrong count format (t11, known gap, not addressed in this spec)

Model found 1 category row, answered `Count: 1` instead of `<COUNT:20>`. Separate issue; lower priority.

---

## Solution: 3 Components

### 1. `agent/schema_gate.py` — rewrite with sqlglot AST

Replace regex-based checks with sqlglot AST traversal.

**Column validation (Check 1):**
- Parse `sqlglot.parse_one(q, dialect="sqlite")`
- Walk `exp.Column` nodes; skip columns without `col.table` (unqualified columns are fine)
- For qualified references (`table_alias.col`): collect alias→table map from `FROM`/`JOIN` clauses first; resolve alias → real table name; validate `col.name` in known columns for that table
- Error: `"unknown column: {alias}.{col} (not in schema)"`

**Alias resolution is required** to avoid false positives on `p.sku`, `pp.key`, `pp2.value_text` — these use aliases `p`, `pp`, `pp2` not table names. Naive check of `col.table in known_tables` would block all aliased queries.

**Literal validation (Check 2) — context-aware:**
- Walk `exp.Literal` nodes
- Skip if value not in `task_text` or value in `all_confirmed`
- Skip if parent node is `exp.Like` or `exp.ILike` — discovery query, allow
- Block otherwise with actionable message: `"unverified literal: '{val}' — use LIKE '%{val}%' for discovery first"`

**Double-key JOIN (Check 3):**
- Walk `exp.Join` nodes joining `product_properties` (resolved via alias map)
- Detect multiple `exp.EQ` on `key` column within same `WHERE` scope
- Error: `"double-key JOIN on product_properties — use separate EXISTS subqueries"`

### 2. `agent/pipeline.py` — auto-extract SKU refs

**Dependency:** this component only produces refs if the SQL plan includes `SELECT p.sku`. It is ineffective without the sql_plan.md fix (§3) that mandates sku in final query. Both §2 and §3 are required together.

Add `_extract_sku_refs(queries: list[str], results: list[str]) -> list[str]`.

Logic:
- For each (query, result) pair: parse header row of CSV result
- If header contains `sku` column: extract values, build `/proc/catalog/{sku}.json`
- **Open question — stores refs:** expected paths are `/proc/stores/store_graz_lend.json` etc. These do not follow `store_{id}.json` pattern. The `stores` table likely has a `path` column (similar to `products.path`). During implementation: inspect stores table schema via `.schema` and determine correct column. If `path` column exists in stores table, extract it directly from results. If not, skip stores auto-refs and rely on prompt rules.

Call site: after successful EXECUTE cycle (`success = True`), call `_extract_sku_refs(queries, sql_results)`. Accumulate refs across cycles (refs from cycle N carry into cycle N+1 context).

Append to `_build_answer_user_msg` output:
```
AUTO_REFS (from sku column in SQL results — MUST be included in grounding_refs):
/proc/catalog/FST-2JPIIG2S.json
```

### 3. `data/prompts/sql_plan.md` — 3 targeted fixes

**Fix 1: Remove contradiction.**
"Final query obligation" (include final query in same plan as discovery) contradicts "Discovery Query Isolation CRITICAL" (separate cycles). Remove "Final query obligation" section entirely. Isolation rule is correct — keep it.

**Fix 2: Add explicit LIKE rule for discovery.**
Add to "String Literals in WHERE Clauses" section:
```
Discovery queries MUST use LIKE with % wildcards on both sides:
  SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'
Never exact match on unconfirmed value:
  WHERE brand = 'Festool'  -- SCHEMA gate will block this
```

**Fix 3: Final confirmation query must project sku.**
Add rule: the last query in any plan that claims product existence MUST include `p.sku` in SELECT. This is required for ANSWER phase to construct grounding_refs.

---

## Files Changed

| File | Change | Scope |
|---|---|---|
| `agent/schema_gate.py` | Full rewrite with sqlglot (~47 → ~90 lines) | medium |
| `agent/pipeline.py` | +`_extract_sku_refs()`, update `_build_answer_user_msg` | small |
| `data/prompts/sql_plan.md` | 3 targeted edits | small |
| `tests/test_schema_gate.py` | Update for new error messages + LIKE allowance + alias test | small |

---

## Open Questions (resolve during implementation)

1. **Stores path format:** inspect `stores` table schema to confirm whether `path` column exists and what format it holds (`store_graz_lend` slug or opaque ID). Determines stores ref construction logic in `_extract_sku_refs`.

---

## Success Criteria

- `test_schema_gate.py`: existing tests pass with updated messages; new test confirms `LIKE '%val%'` not blocked; new test confirms aliased queries (`SELECT p.sku FROM products p`) not blocked
- `make task TASKS='t01,t02'`: score > 0 (grounding_refs populated from sku in SQL results)
- `make task TASKS='t05'`: cycle 2 uses `LIKE '%Festool%'`, passes gate, executes discovery
- No regression: confirmed-value literals still allowed in `=` context
