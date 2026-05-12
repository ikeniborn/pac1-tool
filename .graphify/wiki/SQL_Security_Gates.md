# SQL Security Gates

> 39 nodes · cohesion 0.11

## Key Concepts

- **check_sql_queries()** (20 connections) — `agent/sql_security.py`
- **test_sql_security.py** (20 connections) — `tests/test_sql_security.py`
- **test_sql_security.py** (15 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_sql_security.py`
- **load_security_gates()** (8 connections) — `agent/sql_security.py`
- **sql_security.py** (7 connections) — `agent/sql_security.py`
- **sql_security.py** (6 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/agent/sql_security.py`
- **check_path_access()** (5 connections) — `agent/sql_security.py`
- **_has_where_clause()** (4 connections) — `agent/sql_security.py`
- **test_unverified_gate_is_skipped()** (4 connections) — `tests/test_sql_security.py`
- **_is_select()** (3 connections) — `agent/sql_security.py`
- **test_cte_with_where_passes()** (3 connections) — `tests/test_sql_security.py`
- **test_ddl_drop_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_ddl_insert_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_empty_queries_passes()** (3 connections) — `tests/test_sql_security.py`
- **test_explain_select_without_where_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_has_where_clause_subquery()** (3 connections) — `tests/test_sql_security.py`
- **test_load_security_gates_empty_dir()** (3 connections) — `tests/test_sql_security.py`
- **test_load_security_gates_from_dir()** (3 connections) — `tests/test_sql_security.py`
- **test_multiple_queries_first_error_returned()** (3 connections) — `tests/test_sql_security.py`
- **test_no_outer_where_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_path_catalog_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_path_other_passes()** (3 connections) — `tests/test_sql_security.py`
- **test_select_count_without_where_blocked()** (3 connections) — `tests/test_sql_security.py`
- **test_select_with_where_passes()** (3 connections) — `tests/test_sql_security.py`
- **test_select_without_where_blocked()** (3 connections) — `tests/test_sql_security.py`
- *... and 14 more nodes in this community*

## Relationships

- [[Pipeline System Builder]] (4 shared connections)

## Source Files

- `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/agent/sql_security.py`
- `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_sql_security.py`
- `agent/sql_security.py`
- `tests/test_sql_security.py`

## Audit Trail

- EXTRACTED: 119 (74%)
- INFERRED: 41 (26%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*