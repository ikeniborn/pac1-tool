# Prompt Loader & Assembly

> 25 nodes · cohesion 0.13

## Key Concepts

- **load_prompt()** (19 connections) — `agent/prompt.py`
- **test_prompt_loader.py** (17 connections) — `tests/test_prompt_loader.py`
- **build_system_prompt()** (6 connections) — `agent/prompt.py`
- **prompt.py** (6 connections) — `agent/prompt.py`
- **test_build_system_prompt_fallback_to_default_for_unknown()** (2 connections) — `tests/test_prompt_loader.py`
- **test_build_system_prompt_lookup_contains_core_and_catalogue()** (2 connections) — `tests/test_prompt_loader.py`
- **test_core_has_ecom_role()** (2 connections) — `tests/test_prompt_loader.py`
- **test_core_has_exec_tool()** (2 connections) — `tests/test_prompt_loader.py`
- **test_core_has_no_vault_tools()** (2 connections) — `tests/test_prompt_loader.py`
- **test_email_prompt_not_loaded()** (2 connections) — `tests/test_prompt_loader.py`
- **test_inbox_prompt_not_loaded()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_answer_exists()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_core()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_learn_exists()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_lookup()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_pipeline_evaluator_exists()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_sql_plan_exists()** (2 connections) — `tests/test_prompt_loader.py`
- **test_load_prompt_unknown_returns_empty()** (2 connections) — `tests/test_prompt_loader.py`
- **test_lookup_has_no_vault_file_tools()** (2 connections) — `tests/test_prompt_loader.py`
- **test_lookup_has_sql_gate()** (2 connections) — `tests/test_prompt_loader.py`
- **_load_all()** (1 connections) — `agent/prompt.py`
- **System prompt builder — loads blocks from data/prompts/*.md.** (1 connections) — `agent/prompt.py`
- **Return prompt block by file stem name. Returns '' if not found.** (1 connections) — `agent/prompt.py`
- **Assemble system prompt from file-based blocks for the given task type.** (1 connections) — `agent/prompt.py`
- **test_task_blocks_has_no_email_inbox()** (1 connections) — `tests/test_prompt_loader.py`

## Relationships

- [[Pipeline Evaluator]] (2 shared connections)
- [[SQL Pipeline State Machine]] (2 shared connections)
- [[Orchestrator Entry Point]] (1 shared connections)

## Source Files

- `agent/prompt.py`
- `tests/test_prompt_loader.py`

## Audit Trail

- EXTRACTED: 52 (61%)
- INFERRED: 33 (39%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*