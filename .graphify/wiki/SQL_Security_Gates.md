# SQL Security Gates

> 25 nodes · cohesion 0.13

## Key Concepts

- **check_sql_queries()** (15 connections) — `agent/sql_security.py`
- **test_sql_security.py** (14 connections) — `tests/test_sql_security.py`
- **sql_security.py** (7 connections) — `agent/sql_security.py`
- **load_security_gates()** (5 connections) — `agent/sql_security.py`
- **check_path_access()** (4 connections) — `agent/sql_security.py`
- **_has_where_clause()** (2 connections) — `agent/sql_security.py`
- **_is_select()** (2 connections) — `agent/sql_security.py`
- **test_ddl_drop_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_ddl_insert_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_empty_queries_passes()** (2 connections) — `tests/test_sql_security.py`
- **test_explain_select_without_where_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_load_security_gates_empty_dir()** (2 connections) — `tests/test_sql_security.py`
- **test_load_security_gates_from_dir()** (2 connections) — `tests/test_sql_security.py`
- **test_multiple_queries_first_error_returned()** (2 connections) — `tests/test_sql_security.py`
- **test_path_catalog_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_path_other_passes()** (2 connections) — `tests/test_sql_security.py`
- **test_select_count_without_where_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_select_with_where_passes()** (2 connections) — `tests/test_sql_security.py`
- **test_select_without_where_blocked()** (2 connections) — `tests/test_sql_security.py`
- **test_subquery_with_where_passes()** (2 connections) — `tests/test_sql_security.py`
- **test_where_in_string_literal_not_confused()** (2 connections) — `tests/test_sql_security.py`
- **Security gate evaluation — gates loaded from data/security/*.yaml.** (1 connections) — `agent/sql_security.py`
- **Load all gate definitions from *.yaml files in directory, sorted by filename.** (1 connections) — `agent/sql_security.py`
- **Apply security gates to SQL queries. Returns error message or None if all pass.** (1 connections) — `agent/sql_security.py`
- **Check if a file path access is blocked by path_prefix gates.** (1 connections) — `agent/sql_security.py`

## Relationships

- [[SQL Pipeline State Machine]] (3 shared connections)

## Source Files

- `agent/sql_security.py`
- `tests/test_sql_security.py`

## Audit Trail

- EXTRACTED: 53 (65%)
- INFERRED: 28 (35%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*