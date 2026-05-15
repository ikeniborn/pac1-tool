# Design: t10 Pipeline Failures Fix

**Date:** 2026-05-15
**Scope:** Five interlinked defects surfaced by `logs/20260515_134945_qwen3.5-cloud/t10.jsonl`.
**Status:** Draft — pending user approval.

## Problem Summary

Task `t10` ("How many catalogue products are Corded Angle Grinder?") ran 9 pipeline cycles and never produced an `ANSWER`. Cycle 2 already obtained the correct `COUNT(*) = 3` (trace line 24), but a broken TDD assert discarded it and the agent diverged into stale table-name lookups for the rest of the run.

Five root causes identified:

| # | Defect | Surface |
|---|--------|---------|
| 1 | TDD assert `len(rows) > 1` fails on `COUNT(*)` results | `data/prompts/test_gen.md` + `agent/test_runner.py` + `agent/pipeline.py:_run_test_gen` callsite |
| 2 | Stale table name `kinds` in prompts; real table is `product_kinds` | `data/prompts/{resolve,lookup,sql_plan}.md`, `agent/prompt.py`, `agent/prephase.py` |
| 3 | Schema gate false-positive: literal `'products'` in `sqlite_schema` discovery is blocked | `agent/schema_gate.py` Check 2 |
| 4 | LEARN context loses `sqlite_schema` discovery — agent rediscovers the same table 4 times | `agent/pipeline.py` after `sql_execute` |
| 5 | Schema gate does not reject queries referencing unknown tables | `agent/schema_gate.py` (new Check 0) |

## Goals

- Zero-shot: replay of `t10` with the same model converges in ≤ 3 cycles and produces `<COUNT:3>`.
- No regressions in the existing benchmark.
- Each subsystem (test_gen, schema_gate, schema_digest refresh) testable in isolation.

## Non-Goals

- No changes to LLM routing, evaluator, or RESOLVE phase contract.
- No new YAML security gates (`data/security/` stays empty).
- No restructuring of the cycle loop in `pipeline.py` beyond targeted hooks.

## Architecture

```
prephase ──► schema_digest (semantic roles: products/kinds/properties)
   │
   ▼
RESOLVE  ──── system prompt now includes SCHEMA DIGEST
   │
   ▼
SQL_PLAN ──► schema_gate (Check 0 unknown-table, Check 2 sqlite-schema exemption)
   │
   ▼
EXECUTE ──► if query targets sqlite_schema/sqlite_master AND has_data
   │           └─► merge_schema_from_sqlite_results() — refreshes schema_digest in-place
   ▼
TEST_RUN ──► runtime guard: aggregate-vs-row antipattern check
   │
   ▼
LEARN / ANSWER
```

## Components

### 1. TDD Test Generator (defect #1)

**Files:** `data/prompts/test_gen.md`, `agent/test_runner.py`, `agent/pipeline.py`.

**Prompt changes (`test_gen.md`):**
- Rewrite the output-format example for the aggregate path. New example demonstrates `assert results[-1].strip()` plus integer parsing of the last data row, never `len(rows) > 1`.
- Anti-patterns section: explicit ban on `len(rows) > 1` / `len(results) > 1` for queries containing `COUNT(`, `SUM(`, `AVG(`, `MIN(`, `MAX(`.
- Contract clarification: `results` parameter contains every executed query in cycle order. Tests MUST select the relevant element (typically `results[-1]`) or filter empties — never assume `results[0]` is the data query.

**Runtime guard (`test_runner.py`):**
- Extend `_check_tdd_antipatterns(test_code, task_text, sql_queries)` (new third argument).
- New regex `_AGG_RE = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)`.
- New regex `_BAD_LEN_RE = re.compile(r"len\s*\(\s*(rows|results)\s*\)\s*>\s*1")`.
- If any `sql_queries` matches `_AGG_RE` AND `test_code` matches `_BAD_LEN_RE`: append warning `"aggregate query + len > 1 antipattern — use rows == 1 + integer parse"` AND return `passed=False` with that error (force-fail without subprocess).
- `run_tests` signature gains `sql_queries: list[str]`; pipeline callsite passes the queries.

**Pipeline (`pipeline.py:_run_test_gen` + test_run call):**
- `_run_test_gen` callsite at line ~635: pass `sql_queries=queries` into `run_tests`.
- No filtering of `sql_results` in pipeline — contract change above places that on the test author/LLM.

### 2. Schema-Driven Prompts (defect #2)

**Files:** `data/prompts/{resolve,lookup,sql_plan}.md`, `agent/prompt.py`, `agent/prephase.py`.

**Prompt edits:**
- Remove every hardcoded `FROM kinds`, `WHERE k.name`, `SELECT ... FROM products` literal *table* name. Replace with directive:
  > "Consult SCHEMA DIGEST (above) for the actual table names. Tables are tagged with semantic role: `role=products`, `role=kinds`, `role=properties`."
- Discovery-query patterns in `resolve.md` keep their *shape* but reference roles, e.g. `SELECT DISTINCT name FROM <role:kinds> WHERE name LIKE ... LIMIT 10`. The LLM must substitute the actual name from the digest.

**`prompt.py:build_system_prompt`:**
- Currently injects `SCHEMA DIGEST` for `sql_plan` and `learn` only (pipeline.py:236). Extend to `resolve` phase.

**`prephase.py:_build_schema_digest`:**
- After columns are loaded, compute semantic role per table:
  - `role = "products"` if columns include `sku` AND `kind_id`.
  - `role = "kinds"` if columns include `category_id` AND `name` AND no `sku`.
  - `role = "properties"` if columns include `key` AND `value_text`.
  - Else `role = "other"`.
- Emit role in `_format_schema_digest` output: `product_kinds [role=kinds]: id, category_id, name`.

### 3. Schema Gate Refactor (defects #3, #5)

**File:** `agent/schema_gate.py`.

**Check 0 (new) — unknown table:**
- Walk parsed expression, collect every `exp.Table.name.lower()`.
- Known set: `set(schema_digest['tables'].keys())` lowercased ∪ `SYSTEM_TABLES`, where `SYSTEM_TABLES = {"sqlite_schema", "sqlite_master"}` plus prefix match `pragma_*`.
- First unknown table → `return f"unknown table: '{name}' (not in schema digest)"`.
- Runs before Check 1; if schema_digest is empty, skip Check 0 (no ground truth).

**Check 2 modification — system-table exemption:**
- Before iterating literals, scan tables: if any referenced table is in `SYSTEM_TABLES` or matches `pragma_*` → skip Check 2 entirely (DDL discovery).
- Rationale: literals in `WHERE name IN ('products', ...)` against `sqlite_schema` are table-name identifiers, not data values.

**Check 1 (unknown qualified column), Check 3 (double-key JOIN):** unchanged.

**Public API `check_schema_compliance` signature:** unchanged.

### 4. In-Cycle Schema Refresh (defect #4)

**Files:** `agent/prephase.py`, `agent/pipeline.py`, `agent/trace.py`.

**New function `prephase.merge_schema_from_sqlite_results(schema_digest, csv_results) -> list[str]`:**
- Input: list of CSV strings (from `sql_execute`) that returned rows from `sqlite_schema` / `sqlite_master`.
- Parse CSV; expect columns `name, sql`. For each row where `sql` starts with `CREATE TABLE`:
  - Parse via `sqlglot.parse_one(sql, dialect="sqlite")`.
  - Extract table name and column names.
  - If table not already in `schema_digest['tables']`: insert with `columns=[{name, type}]` plus computed `role` (same logic as `_build_schema_digest`).
- Return list of added table names (for audit).

**`pipeline.py` after `sql_execute`:**
- New helper `_SQLITE_SCHEMA_RE = re.compile(r"\bsqlite_(?:schema|master)\b", re.IGNORECASE)`.
- After the execute loop fills `sql_results` (~line 590), iterate `(q, r)` pairs: if `_SQLITE_SCHEMA_RE.search(q)` and `_csv_has_data(r)`:
  - `added = merge_schema_from_sqlite_results(pre.schema_digest, [r])`.
  - If `added`: `trace.log_schema_refresh(cycle, added_tables=added)`.
- Mutation is in-place on `pre.schema_digest`; the next cycle's `SCHEMA DIGEST` block in the system prompt automatically reflects the new tables.

**`trace.py`:**
- New event type `schema_refresh` with fields `cycle`, `added_tables`. Append to JSONL via existing `_emit`.

### 5. Tests

**New / extended unit tests:**

- `tests/test_schema_gate.py`:
  - `test_unknown_table_rejected` — query `FROM nonexistent_table` returns error.
  - `test_sqlite_schema_exempt_from_literal_check` — `SELECT name FROM sqlite_schema WHERE name IN ('products', 'kinds')` passes.
  - `test_sqlite_master_exempt` — same for `sqlite_master`.
  - `test_pragma_table_info_exempt` — `pragma_table_info('products')` passes.
  - Regressions: existing Check 1 / Check 2 / Check 3 cases.

- `tests/test_test_runner.py` (new file):
  - `test_aggregate_antipattern_force_fail` — test_code with `len(rows) > 1` AND sql_queries containing `COUNT(*)` returns `passed=False, error contains "antipattern"`, never spawns subprocess.
  - `test_non_aggregate_len_check_allowed` — same test_code with `SELECT sku FROM products` → no force-fail.

- `tests/test_prephase.py`:
  - `test_merge_schema_from_create_table` — feeds CSV with one CREATE TABLE row, asserts digest now contains the table with parsed columns and computed role.
  - `test_merge_idempotent` — re-merging same row does not duplicate.
  - `test_build_schema_digest_assigns_roles` — fixture digest contains `products`/`product_kinds`/`product_properties` with expected roles.

- `tests/test_pipeline.py`:
  - `test_pipeline_schema_refresh_after_sqlite_query` — mock execute that returns sqlite_schema CSV; assert `pre.schema_digest` gained the new table after the cycle.

**Integration replay:**

- Run `make task TASKS='t10'` against the same model used in the failing log (`qwen3.5:cloud` via OpenRouter or local Ollama, per `models.json`).
- Acceptance:
  - Final `answer.message` matches `<COUNT:3>`.
  - `answer.outcome == 'OUTCOME_OK'`.
  - Cycles ≤ 3.
- Full suite: `uv run pytest tests/ -v` green.

## Data Flow Per Cycle (post-fix)

1. RESOLVE — system prompt now has SCHEMA DIGEST with roles; LLM picks real `product_kinds` name.
2. SQL_PLAN — schema_digest in context; queries reference real tables.
3. Gate:
   - Check 0 catches `FROM kinds` if LLM still hallucinates → forces LEARN immediately, no wasted EXPLAIN/execute.
   - Check 2 skipped for `sqlite_schema` queries.
4. EXECUTE — if any query hits sqlite_schema, `merge_schema_from_sqlite_results` refreshes digest in place.
5. TEST_RUN — runtime guard rejects aggregate antipattern before subprocess; LLM forced to regenerate proper assert.
6. ANSWER reached within 3 cycles.

## Error Handling

- `merge_schema_from_sqlite_results`: on `sqlglot.parse` failure for a row, skip the row and continue; no exception propagates.
- Runtime antipattern guard: warning + force-fail, never a hard exception.
- Schema gate Check 0: skipped if `schema_digest` is empty (preserves dry-run / unit-test friendliness).

## Migration & Rollout

- All changes additive at the API surface; existing callers unaffected (`check_schema_compliance` and `run_tests` keep return types, gain one parameter on `run_tests`).
- No schema migrations, no env-var changes.
- Existing prompts under `data/prompts/optimized/` not touched.

## Open Risks

- **R1.** Role inference in `_build_schema_digest` may misclassify edge tables. Mitigation: `role="other"` fallback is benign; prompts use roles only as hints.
- **R2.** Some models may still copy the bad assert example before the prompt change propagates. Mitigation: runtime guard provides defence in depth.
- **R3.** `merge_schema_from_sqlite_results` relies on `sqlglot` parsing arbitrary `CREATE TABLE` text. Mitigation: parse failures are tolerated silently; the worst case is "no refresh" (current behaviour).

## File Touch List

| File | Change |
|------|--------|
| `data/prompts/test_gen.md` | Rewrite output example, ban aggregate `len > 1` in anti-patterns |
| `data/prompts/resolve.md` | Remove hardcoded table names, reference roles |
| `data/prompts/lookup.md` | Same |
| `data/prompts/sql_plan.md` | Same |
| `agent/test_runner.py` | New regexes, extended `_check_tdd_antipatterns`, new arg on `run_tests` |
| `agent/pipeline.py` | Pass `sql_queries` to `run_tests`; post-execute schema refresh hook |
| `agent/prephase.py` | Role tagging in `_build_schema_digest`; new `merge_schema_from_sqlite_results` |
| `agent/prompt.py` | SCHEMA DIGEST block for `resolve` phase |
| `agent/schema_gate.py` | Check 0 (unknown table), system-table exemption in Check 2 |
| `agent/trace.py` | New `schema_refresh` event |
| `tests/test_schema_gate.py` | New cases above |
| `tests/test_test_runner.py` | New file, antipattern cases |
| `tests/test_prephase.py` | Role and merge tests |
| `tests/test_pipeline.py` | Schema refresh integration |

## Success Criteria

- All new unit tests pass.
- `uv run pytest tests/` green end to end.
- `make task TASKS='t10'` returns `<COUNT:3>` in ≤ 3 cycles with `OUTCOME_OK`.
- No new errors in trace for `t10` replay beyond what existed before changes.
