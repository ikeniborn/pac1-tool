# check_sql_queries()

> God node · 20 connections · `agent/sql_security.py`

**Community:** [[SQL Security Gates]]

## Connections by Relation

### calls
- [[run_pipeline()]] `EXTRACTED`
- [[_has_where_clause()]] `EXTRACTED`
- [[_is_select()]] `EXTRACTED`
- [[test_ddl_drop_blocked()]] `INFERRED`
- [[test_ddl_insert_blocked()]] `INFERRED`
- [[test_select_with_where_passes()]] `INFERRED`
- [[test_select_without_where_blocked()]] `INFERRED`
- [[test_select_count_without_where_blocked()]] `INFERRED`
- [[test_explain_select_without_where_blocked()]] `INFERRED`
- [[test_subquery_with_where_passes()]] `INFERRED`
- [[test_where_in_string_literal_not_confused()]] `INFERRED`
- [[test_multiple_queries_first_error_returned()]] `INFERRED`
- [[test_empty_queries_passes()]] `INFERRED`
- [[test_cte_with_where_passes()]] `INFERRED`
- [[test_where_in_double_quoted_identifier_not_confused()]] `INFERRED`
- [[test_subquery_outer_has_where_passes()]] `INFERRED`
- [[test_no_outer_where_blocked()]] `INFERRED`

### contains
- [[sql_security.py]] `EXTRACTED`
- [[sql_security.py]] `EXTRACTED`

### rationale_for
- [[Apply security gates to SQL queries. Returns error message or None if all pass.]] `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*