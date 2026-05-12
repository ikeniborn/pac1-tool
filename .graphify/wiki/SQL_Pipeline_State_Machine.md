# SQL Pipeline State Machine

> 26 nodes · cohesion 0.16

## Key Concepts

- **pipeline.py** (16 connections) — `agent/pipeline.py`
- **run_pipeline()** (16 connections) — `agent/pipeline.py`
- **test_pipeline.py** (8 connections) — `tests/test_pipeline.py`
- **test_happy_path()** (7 connections) — `tests/test_pipeline.py`
- **test_security_gate_ddl_triggers_learn()** (7 connections) — `tests/test_pipeline.py`
- **test_validate_error_triggers_learn_and_retry()** (7 connections) — `tests/test_pipeline.py`
- **_call_llm_phase()** (6 connections) — `agent/pipeline.py`
- **_make_pre()** (6 connections) — `tests/test_pipeline.py`
- **test_max_cycles_exhausted_returns_clarification()** (6 connections) — `tests/test_pipeline.py`
- **_build_system()** (5 connections) — `agent/pipeline.py`
- **_make_exec_result()** (5 connections) — `tests/test_pipeline.py`
- **_sql_plan_json()** (5 connections) — `tests/test_pipeline.py`
- **_run_learn()** (4 connections) — `agent/pipeline.py`
- **_answer_json()** (4 connections) — `tests/test_pipeline.py`
- **_csv_has_data()** (3 connections) — `agent/pipeline.py`
- **_exec_result_text()** (3 connections) — `agent/pipeline.py`
- **_gates_summary()** (2 connections) — `agent/pipeline.py`
- **Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='l** (1 connections) — `agent/pipeline.py`
- **Phase-based SQL pipeline. Returns stats dict compatible with run_loop().** (1 connections) — `agent/pipeline.py`
- **Extract stdout/output text from an ExecResponse or test mock.** (1 connections) — `agent/pipeline.py`
- **/bin/sql returns CSV (header + data rows) or JSON array/object.     CSV empty =** (1 connections) — `agent/pipeline.py`
- **SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry).** (1 connections) — `agent/pipeline.py`
- **3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call.** (1 connections) — `tests/test_pipeline.py`
- **DDL query → security gate blocks → LEARN → retry → success.** (1 connections) — `tests/test_pipeline.py`
- **SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok.** (1 connections) — `tests/test_pipeline.py`
- *... and 1 more nodes in this community*

## Relationships

- [[LLM Dispatch & Routing]] (5 shared connections)
- [[SQL Security Gates]] (3 shared connections)
- [[Prompt Loader & Assembly]] (2 shared connections)
- [[Rules Loader (YAML)]] (2 shared connections)
- [[Pipeline Evaluator]] (2 shared connections)
- [[Pydantic Models & Contracts]] (1 shared connections)
- [[Orchestrator Entry Point]] (1 shared connections)
- [[Prephase & VM Bootstrap]] (1 shared connections)

## Source Files

- `agent/pipeline.py`
- `tests/test_pipeline.py`

## Audit Trail

- EXTRACTED: 109 (92%)
- INFERRED: 10 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*