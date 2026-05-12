# Pipeline Evaluator

> 18 nodes · cohesion 0.19

## Key Concepts

- **evaluator.py** (10 connections) — `agent/evaluator.py`
- **run_evaluator()** (8 connections) — `agent/evaluator.py`
- **_run()** (6 connections) — `agent/evaluator.py`
- **_make_eval_input()** (6 connections) — `tests/test_evaluator.py`
- **test_evaluator.py** (5 connections) — `tests/test_evaluator.py`
- **EvalInput** (4 connections) — `agent/evaluator.py`
- **_run_evaluator_safe()** (4 connections) — `agent/pipeline.py`
- **test_run_evaluator_exception_returns_none()** (4 connections) — `tests/test_evaluator.py`
- **test_run_evaluator_llm_failure_returns_none()** (4 connections) — `tests/test_evaluator.py`
- **test_run_evaluator_parse_failure_returns_none()** (4 connections) — `tests/test_evaluator.py`
- **_build_eval_system()** (3 connections) — `agent/evaluator.py`
- **test_run_evaluator_writes_to_log()** (3 connections) — `tests/test_evaluator.py`
- **_append_log()** (2 connections) — `agent/evaluator.py`
- **Post-execution pipeline evaluator. Fail-open: any exception returns None.** (1 connections) — `agent/evaluator.py`
- **Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure.** (1 connections) — `agent/evaluator.py`
- **LLM failure → returns None, no crash.** (1 connections) — `tests/test_evaluator.py`
- **Unparseable LLM response → returns None, no crash.** (1 connections) — `tests/test_evaluator.py`
- **Any exception in evaluator → returns None (fail-open).** (1 connections) — `tests/test_evaluator.py`

## Relationships

- [[LLM Dispatch & Routing]] (4 shared connections)
- [[Prompt Loader & Assembly]] (2 shared connections)
- [[Pydantic Models & Contracts]] (2 shared connections)
- [[SQL Pipeline State Machine]] (2 shared connections)

## Source Files

- `agent/evaluator.py`
- `agent/pipeline.py`
- `tests/test_evaluator.py`

## Audit Trail

- EXTRACTED: 53 (78%)
- INFERRED: 15 (22%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*