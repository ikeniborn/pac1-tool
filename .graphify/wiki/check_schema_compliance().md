# check_schema_compliance()

> God node · 14 connections · `agent/schema_gate.py`

**Community:** [[Community 17]]

## Connections by Relation

### calls
- [[run_pipeline()]] `EXTRACTED`
- [[test_valid_query_passes()]] `INFERRED`
- [[test_unknown_column_detected()]] `INFERRED`
- [[test_known_columns_pass()]] `INFERRED`
- [[test_unverified_literal_detected()]] `INFERRED`
- [[test_confirmed_literal_passes()]] `INFERRED`
- [[test_literal_not_in_task_passes()]] `INFERRED`
- [[test_double_key_join_detected()]] `INFERRED`
- [[test_separate_exists_passes()]] `INFERRED`
- [[test_empty_queries_passes()]] `INFERRED`
- [[test_empty_digest_skips_column_check()]] `INFERRED`
- [[test_multiple_queries_first_error_returned()]] `INFERRED`

### contains
- [[schema_gate.py]] `EXTRACTED`

### rationale_for
- [[Check queries against schema. Returns first error string or None if all pass.]] `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*