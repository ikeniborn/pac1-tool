# Resolve Phase

> 25 nodes · cohesion 0.16

## Key Concepts

- **test_resolve.py** (15 connections) — `tests/test_resolve.py`
- **resolve.py** (11 connections) — `agent/resolve.py`
- **run_resolve()** (9 connections) — `agent/resolve.py`
- **_run()** (7 connections) — `agent/resolve.py`
- **_security_check()** (7 connections) — `agent/resolve.py`
- **_make_pre()** (7 connections) — `tests/test_resolve.py`
- **_first_value()** (6 connections) — `agent/resolve.py`
- **test_run_resolve_accumulates_multiple_fields()** (3 connections) — `tests/test_resolve.py`
- **test_run_resolve_blocks_unsafe_query()** (3 connections) — `tests/test_resolve.py`
- **test_run_resolve_returns_confirmed_values()** (3 connections) — `tests/test_resolve.py`
- **test_run_resolve_returns_empty_on_exception()** (3 connections) — `tests/test_resolve.py`
- **test_run_resolve_returns_empty_on_llm_failure()** (3 connections) — `tests/test_resolve.py`
- **_build_resolve_system()** (2 connections) — `agent/resolve.py`
- **_exec_sql()** (2 connections) — `agent/resolve.py`
- **test_first_value_returns_first_data_cell()** (2 connections) — `tests/test_resolve.py`
- **test_first_value_returns_none_for_empty()** (2 connections) — `tests/test_resolve.py`
- **test_first_value_returns_none_for_header_only()** (2 connections) — `tests/test_resolve.py`
- **test_first_value_strips_quotes()** (2 connections) — `tests/test_resolve.py`
- **test_security_check_allows_distinct()** (2 connections) — `tests/test_resolve.py`
- **test_security_check_allows_ilike()** (2 connections) — `tests/test_resolve.py`
- **test_security_check_blocks_drop()** (2 connections) — `tests/test_resolve.py`
- **test_security_check_blocks_insert()** (2 connections) — `tests/test_resolve.py`
- **test_security_check_blocks_query_without_ilike_or_distinct()** (2 connections) — `tests/test_resolve.py`
- **Resolve phase: confirm task identifiers against DB before pipeline cycles.** (1 connections) — `agent/resolve.py`
- **Resolve identifiers in task_text against DB. Returns confirmed_values or {} on f** (1 connections) — `agent/resolve.py`

## Relationships

- [[Pipeline System Builder]] (2 shared connections)
- [[Prephase & Schema]] (2 shared connections)
- [[Evaluator & Contract Models]] (1 shared connections)
- [[LLM Routing]] (1 shared connections)
- [[LLM Raw Call]] (1 shared connections)

## Source Files

- `agent/resolve.py`
- `tests/test_resolve.py`

## Audit Trail

- EXTRACTED: 72 (71%)
- INFERRED: 29 (29%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*