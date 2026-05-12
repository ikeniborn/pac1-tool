# Prephase & VM Bootstrap

> 30 nodes · cohesion 0.10

## Key Concepts

- **test_prephase.py** (14 connections) — `tests/test_prephase.py`
- **run_prephase()** (13 connections) — `agent/prephase.py`
- **_make_vm()** (7 connections) — `tests/test_prephase.py`
- **PrephaseResult** (5 connections) — `agent/prephase.py`
- **test_normal_mode_log_structure()** (4 connections) — `tests/test_prephase.py`
- **test_normal_mode_no_tree_no_context()** (4 connections) — `tests/test_prephase.py`
- **test_normal_mode_reads_only_agents_md()** (4 connections) — `tests/test_prephase.py`
- **test_preserve_prefix_equals_log()** (4 connections) — `tests/test_prephase.py`
- **test_agents_md_not_found()** (3 connections) — `tests/test_prephase.py`
- **test_normal_mode_reads_schema()** (3 connections) — `tests/test_prephase.py`
- **test_schema_exec_fail_sets_empty_db_schema()** (3 connections) — `tests/test_prephase.py`
- **test_schema_not_in_log()** (3 connections) — `tests/test_prephase.py`
- **test_prephase_result_fields()** (2 connections) — `tests/test_prephase.py`
- **test_prephase_result_has_db_schema_field()** (2 connections) — `tests/test_prephase.py`
- **PrephaseResult now has db_schema field.** (1 connections) — `tests/test_prephase.py`
- **Normal mode still calls vm.exec for schema.** (1 connections) — `tests/test_prephase.py`
- **vm.exec exception → db_schema is empty string, no crash.** (1 connections) — `tests/test_prephase.py`
- **db_schema content must NOT appear in LLM log messages.** (1 connections) — `tests/test_prephase.py`
- **PrephaseResult has exactly the expected fields.** (1 connections) — `tests/test_prephase.py`
- **Normal mode: exactly 1 vm.read call (AGENTS.MD).** (1 connections) — `tests/test_prephase.py`
- **Log has system + few-shot user + few-shot assistant + prephase user.** (1 connections) — `tests/test_prephase.py`
- **vm.tree and vm.context are never called.** (1 connections) — `tests/test_prephase.py`
- *... and 5 more nodes in this community*

## Relationships

- [[LLM Dispatch & Routing]] (2 shared connections)
- [[Orchestrator Entry Point]] (2 shared connections)
- [[Connect-RPC Client Layer]] (1 shared connections)
- [[SQL Pipeline State Machine]] (1 shared connections)

## Source Files

- `agent/prephase.py`
- `tests/test_prephase.py`

## Audit Trail

- EXTRACTED: 70 (73%)
- INFERRED: 26 (27%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*