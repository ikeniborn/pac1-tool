# run_pipeline()

> God node · 29 connections · `agent/pipeline.py`

**Community:** [[Pipeline System Builder]]

## Connections by Relation

### calls
- [[check_sql_queries()]] `EXTRACTED`
- [[run_agent()]] `INFERRED`
- [[check_schema_compliance()]] `EXTRACTED`
- [[_call_llm_phase()]] `EXTRACTED`
- [[RulesLoader]] `INFERRED`
- [[test_happy_path()]] `INFERRED`
- [[test_security_gate_ddl_triggers_learn()]] `INFERRED`
- [[test_learn_does_not_persist_auto_rule()]] `INFERRED`
- [[_build_static_system()]] `EXTRACTED`
- [[run_resolve()]] `EXTRACTED`
- [[_run_learn()]] `EXTRACTED`
- [[load_security_gates()]] `INFERRED`
- [[test_validate_error_triggers_learn_and_retry()]] `INFERRED`
- [[test_max_cycles_exhausted_returns_clarification()]] `INFERRED`
- [[_extract_discovery_results()]] `EXTRACTED`
- [[test_run_pipeline_returns_tuple()]] `INFERRED`
- [[test_evaluator_thread_starts_on_failure()]] `INFERRED`
- [[_build_system()]] `EXTRACTED`
- [[test_pipeline_token_counts_nonzero()]] `INFERRED`
- [[_run_evaluator_safe()]] `EXTRACTED`

### contains
- [[pipeline.py]] `EXTRACTED`

### rationale_for
- [[Phase-based SQL pipeline. Returns stats dict compatible with run_loop().]] `EXTRACTED`
- [[Phase-based SQL pipeline. Returns (stats dict, eval Thread or None).]] `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*