---
title: Pipeline Systemic Fixes — Resolve all-values + Answer fallback + Discovery detection
date: 2026-05-13
status: approved
---

## Problem

Three systemic failures identified from t01/t04/t08/t09/t16 benchmark run (60% score):

1. **t04/t16 — SCHEMA gate blocks task literals one at a time**
   `resolve.py:_first_value()` stores only the first row. Query `LIKE '%L%'` returns `3XL, L, XL, XXL` → saves `3XL` only → `'L'` fails SCHEMA gate → extra discovery cycle.

2. **t09 — silent ANSWER failure, vm.answer() never called**
   ANSWER model returned `"OUTCOME_NEED_MORE_DATA"` (not in `AnswerOutput` Literal enum) → `model_validate` fails → `answer_out=None` → `if answer_out:` block skipped → `vm.answer()` never called → score=0 "no answer provided".

3. **t09/t16 — discovery-only detection relies on syntax (SELECT DISTINCT), not semantics**
   Cycle 2 had `SELECT name, sql FROM sqlite_schema` (not DISTINCT) mixed with two DISTINCT queries → `all_discovery=False` → pipeline declared success on discovery data → ANSWER got kind_id instead of COUNT.

## Solution — 4 files

### 1. `agent/resolve.py` — store all values

Replace `_first_value(csv_text) -> str | None` with `_all_values(csv_text) -> list[str]` that collects every non-header row. Update `_run()` to extend `confirmed_values[field]` with the full list.

Effect: `confirmed_values['attr_value'] = ['3XL', 'L', 'XL', 'XXL']` — any task literal passes SCHEMA gate if it appears in any result row.

Trace logging: keep logging `values[0]` as `value_extracted` for backward compat, but store all.

### 2. `agent/pipeline.py` — two changes

**2A. Answer fallback:**

```python
if answer_out:
    ...  # existing path
else:
    print(f"{CLI_RED}[pipeline] ANSWER parse failed — sending fallback clarification{CLI_CLR}")
    try:
        vm.answer(AnswerRequest(
            message="Could not synthesize an answer from available data.",
            outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
            refs=[],
        ))
    except Exception as e:
        print(f"{CLI_RED}[pipeline] vm.answer fallback error: {e}{CLI_CLR}")
```

**2B. Discovery-only detection — structural, not syntactic:**

Replace:
```python
all_discovery = all(re.search(r'SELECT\s+DISTINCT\b', q, re.IGNORECASE) for q in queries)
if all_discovery and not new_refs:
```

With:
```python
has_count_result = any(
    re.search(r'\bCOUNT\s*\(', q, re.IGNORECASE) and _csv_has_data(r)
    for q, r in zip(queries, sql_results)
)
if not new_refs and not has_count_result:
```

Logic: no sku/path refs AND no COUNT aggregate result → this cycle produced only discovery data → treat as discovery-only regardless of whether queries use DISTINCT.

**Dependency:** relies on sql_plan.md rule "final product query MUST include p.sku and p.path". If the model violates that rule and emits a final query without sku/path columns, the new condition treats it as discovery and loops. This is acceptable — it forces the model to comply with the projection rule rather than silently producing ungrounded answers.

### 3. `data/prompts/resolve.md` — attr_value coverage

Add section requiring a candidate for every attribute value in the task, including short values (sizes 'M', 'L', 'XL') and enum-like values ('basic', 'cavity fixing'):

```
## Attribute value coverage (REQUIRED)

For every attribute value in the task (sizes, color families, protection classes,
machine types, anchor types, etc.) generate one attr_value candidate.

- Key known (in TOP PROPERTY KEYS): `WHERE key = '<key>' AND value_text LIKE '%<val>%' LIMIT 10`
- Key unknown: `WHERE value_text LIKE '%<val>%' LIMIT 10`

Generate candidates for ALL attribute values — even single-letter sizes ('M', 'L', 'S').
```

### 4. `data/prompts/pipeline_evaluator.md` — detect new failure patterns

Add two new assess items so the optimizer captures these failures in `eval_log.jsonl`:

```
8. RESOLVE coverage: Did confirmed_values include all attr_value literals from the task?
   If not, suggest adding attr_value candidate guidance to resolve.md.
9. ANSWER silent failure: Was answer_out None (parse failed)? Log outcome attempted.
   Suggest adding the invalid outcome value to AnswerOutput Literal if it was semantically valid.
```

## Scope

5 files changed (no new files):
- `agent/resolve.py` — `_first_value` → `_all_values`
- `agent/pipeline.py` — answer fallback + discovery-only detection
- `data/prompts/resolve.md` — attr_value coverage rule
- `data/prompts/pipeline_evaluator.md` — new assess items 8–9
- `tests/test_resolve.py` — rename `_first_value` tests → `_all_values`, add multi-value test

No changes to schema_gate.py, sql_security.py, models.py.

Backward compatible: `schema_gate.py` and `_format_confirmed_values` already handle `list` values via `isinstance(vals, list)` branch.

## Success criteria

| Task | Before | Expected after |
|------|--------|----------------|
| t04  | 1 wasted cycle (SCHEMA gate on 'L') | 0 wasted cycles |
| t09  | score=0 silent failure | score>0, vm.answer called |
| t16  | 7 cycles, inventory missed | ≤4 cycles, inventory queried |
