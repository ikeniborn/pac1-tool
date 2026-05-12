# run_pipeline()

> God node · 16 connections · `agent/pipeline.py`

**Community:** [[SQL Pipeline State Machine]]

## Connections by Relation

### calls
- [[check_sql_queries()]] `EXTRACTED`
- [[RulesLoader]] `EXTRACTED`
- [[run_agent()]] `INFERRED`
- [[test_happy_path()]] `INFERRED`
- [[test_validate_error_triggers_learn_and_retry()]] `INFERRED`
- [[test_security_gate_ddl_triggers_learn()]] `INFERRED`
- [[_call_llm_phase()]] `EXTRACTED`
- [[test_max_cycles_exhausted_returns_clarification()]] `INFERRED`
- [[load_security_gates()]] `EXTRACTED`
- [[_build_system()]] `EXTRACTED`
- [[_run_learn()]] `EXTRACTED`
- [[_run_evaluator_safe()]] `EXTRACTED`
- [[_exec_result_text()]] `EXTRACTED`
- [[_csv_has_data()]] `EXTRACTED`

### contains
- [[pipeline.py]] `EXTRACTED`

### rationale_for
- [[Phase-based SQL pipeline. Returns stats dict compatible with run_loop().]] `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*