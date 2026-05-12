# Pipeline System Builder

> 78 nodes · cohesion 0.05

## Key Concepts

- **run_pipeline()** (29 connections) — `agent/pipeline.py`
- **pipeline.py** (27 connections) — `agent/pipeline.py`
- **test_pipeline.py** (26 connections) — `tests/test_pipeline.py`
- **_make_pre()** (10 connections) — `tests/test_pipeline.py`
- **_build_static_system()** (9 connections) — `agent/pipeline.py`
- **_call_llm_phase()** (9 connections) — `agent/pipeline.py`
- **_make_exec_result()** (9 connections) — `tests/test_pipeline.py`
- **test_happy_path()** (9 connections) — `tests/test_pipeline.py`
- **test_learn_does_not_persist_auto_rule()** (9 connections) — `tests/test_pipeline.py`
- **test_security_gate_ddl_triggers_learn()** (9 connections) — `tests/test_pipeline.py`
- **_run_learn()** (8 connections) — `agent/pipeline.py`
- **_sql_plan_json()** (8 connections) — `tests/test_pipeline.py`
- **test_max_cycles_exhausted_returns_clarification()** (8 connections) — `tests/test_pipeline.py`
- **test_validate_error_triggers_learn_and_retry()** (8 connections) — `tests/test_pipeline.py`
- **_extract_discovery_results()** (7 connections) — `agent/pipeline.py`
- **test_run_pipeline_returns_tuple()** (7 connections) — `tests/test_pipeline.py`
- **_answer_json()** (6 connections) — `tests/test_pipeline.py`
- **test_evaluator_thread_starts_on_failure()** (6 connections) — `tests/test_pipeline.py`
- **_build_system()** (5 connections) — `agent/pipeline.py`
- **test_pipeline_token_counts_nonzero()** (5 connections) — `tests/test_pipeline.py`
- **_format_confirmed_values()** (4 connections) — `agent/pipeline.py`
- **_run_evaluator_safe()** (4 connections) — `agent/pipeline.py`
- **_csv_has_data()** (3 connections) — `agent/pipeline.py`
- **_exec_result_text()** (3 connections) — `agent/pipeline.py`
- **_format_schema_digest()** (3 connections) — `agent/pipeline.py`
- *... and 53 more nodes in this community*

## Relationships

- [[SQL Security Gates]] (4 shared connections)
- [[LLM Raw Call]] (2 shared connections)
- [[Dispatch (Legacy)]] (2 shared connections)
- [[Community 18]] (2 shared connections)
- [[Prephase & Schema]] (2 shared connections)
- [[Resolve Phase]] (2 shared connections)
- [[Community 17]] (2 shared connections)
- [[Community 15]] (2 shared connections)
- [[Prompt Builder]] (1 shared connections)
- [[Evaluator & Contract Models]] (1 shared connections)
- [[LLM Routing]] (1 shared connections)
- [[Orchestrator]] (1 shared connections)

## Source Files

- `agent/pipeline.py`
- `tests/test_pipeline.py`

## Audit Trail

- EXTRACTED: 262 (83%)
- INFERRED: 52 (17%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*