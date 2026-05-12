# Community 17

> 16 nodes · cohesion 0.21

## Key Concepts

- **check_schema_compliance()** (14 connections) — `agent/schema_gate.py`
- **test_schema_gate.py** (11 connections) — `tests/test_schema_gate.py`
- **schema_gate.py** (3 connections) — `agent/schema_gate.py`
- **test_confirmed_literal_passes()** (2 connections) — `tests/test_schema_gate.py`
- **test_double_key_join_detected()** (2 connections) — `tests/test_schema_gate.py`
- **test_empty_digest_skips_column_check()** (2 connections) — `tests/test_schema_gate.py`
- **test_empty_queries_passes()** (2 connections) — `tests/test_schema_gate.py`
- **test_known_columns_pass()** (2 connections) — `tests/test_schema_gate.py`
- **test_literal_not_in_task_passes()** (2 connections) — `tests/test_schema_gate.py`
- **test_multiple_queries_first_error_returned()** (2 connections) — `tests/test_schema_gate.py`
- **test_separate_exists_passes()** (2 connections) — `tests/test_schema_gate.py`
- **test_unknown_column_detected()** (2 connections) — `tests/test_schema_gate.py`
- **test_unverified_literal_detected()** (2 connections) — `tests/test_schema_gate.py`
- **test_valid_query_passes()** (2 connections) — `tests/test_schema_gate.py`
- **Schema-aware SQL validator: unknown columns, unverified literals, double-key JOI** (1 connections) — `agent/schema_gate.py`
- **Check queries against schema. Returns first error string or None if all pass.** (1 connections) — `agent/schema_gate.py`

## Relationships

- [[Pipeline System Builder]] (2 shared connections)

## Source Files

- `agent/schema_gate.py`
- `tests/test_schema_gate.py`

## Audit Trail

- EXTRACTED: 30 (58%)
- INFERRED: 22 (42%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*