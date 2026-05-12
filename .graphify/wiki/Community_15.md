# Community 15

> 19 nodes · cohesion 0.19

## Key Concepts

- **evaluator.py** (10 connections) — `agent/evaluator.py`
- **run_evaluator()** (9 connections) — `agent/evaluator.py`
- **_run()** (8 connections) — `agent/evaluator.py`
- **_make_eval_input()** (7 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **test_evaluator.py** (5 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **test_evaluator.py** (5 connections) — `tests/test_evaluator.py`
- **test_run_evaluator_exception_returns_none()** (5 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **test_run_evaluator_llm_failure_returns_none()** (5 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **test_run_evaluator_parse_failure_returns_none()** (5 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **EvalInput** (4 connections) — `agent/evaluator.py`
- **test_run_evaluator_writes_to_log()** (4 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **_build_eval_system()** (3 connections) — `agent/evaluator.py`
- **_append_log()** (2 connections) — `agent/evaluator.py`
- **Post-execution pipeline evaluator. Fail-open: any exception returns None.** (1 connections) — `agent/evaluator.py`
- **Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure.** (1 connections) — `agent/evaluator.py`
- **Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure.** (1 connections) — `agent/evaluator.py`
- **LLM failure → returns None, no crash.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **Unparseable LLM response → returns None, no crash.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- **Any exception in evaluator → returns None (fail-open).** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`

## Relationships

- [[Evaluator & Contract Models]] (4 shared connections)
- [[Pipeline System Builder]] (2 shared connections)
- [[Dispatch (Legacy)]] (2 shared connections)
- [[LLM Raw Call]] (2 shared connections)
- [[Prompt Builder]] (1 shared connections)
- [[LLM Routing]] (1 shared connections)

## Source Files

- `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/.worktrees/eval-driven-rules/tests/test_evaluator.py`
- `agent/evaluator.py`
- `tests/test_evaluator.py`

## Audit Trail

- EXTRACTED: 63 (81%)
- INFERRED: 15 (19%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*