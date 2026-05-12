# Orchestrator Entry Point

> 12 nodes · cohesion 0.20

## Key Concepts

- **run_agent()** (10 connections) — `agent/orchestrator.py`
- **orchestrator.py** (5 connections) — `agent/orchestrator.py`
- **test_lookup_routes_to_pipeline()** (4 connections) — `tests/test_orchestrator_pipeline.py`
- **write_wiki_fragment()** (2 connections) — `agent/orchestrator.py`
- **_make_vm_mock()** (2 connections) — `tests/test_orchestrator_pipeline.py`
- **test_orchestrator_pipeline.py** (2 connections) — `tests/test_orchestrator_pipeline.py`
- **__init__.py** (1 connections) — `agent/__init__.py`
- **Minimal orchestrator for ecom benchmark.** (1 connections) — `agent/orchestrator.py`
- **Execute a single benchmark task.** (1 connections) — `agent/orchestrator.py`
- **No-op: wiki subsystem removed.** (1 connections) — `agent/orchestrator.py`
- **run_agent with task_type=lookup calls run_pipeline, not run_loop.** (1 connections) — `tests/test_orchestrator_pipeline.py`

## Relationships

- [[Prephase & VM Bootstrap]] (2 shared connections)
- [[BitGN Harness Integration]] (1 shared connections)
- [[LLM Dispatch & Routing]] (1 shared connections)
- [[SQL Pipeline State Machine]] (1 shared connections)
- [[Prompt Loader & Assembly]] (1 shared connections)
- [[Connect-RPC Client Layer]] (1 shared connections)

## Source Files

- `agent/__init__.py`
- `agent/orchestrator.py`
- `tests/test_orchestrator_pipeline.py`

## Audit Trail

- EXTRACTED: 24 (73%)
- INFERRED: 9 (27%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*