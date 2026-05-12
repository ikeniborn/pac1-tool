# LLM Dispatch & Routing

> 51 nodes · cohesion 0.06

## Key Concepts

- **dispatch.py** (22 connections) — `agent/dispatch.py`
- **_call_llm()** (11 connections) — `agent/loop.py`
- **loop.py** (11 connections) — `agent/loop.py`
- **json_extract.py** (10 connections) — `agent/json_extract.py`
- **_extract_json_from_text()** (9 connections) — `agent/json_extract.py`
- **get_provider()** (7 connections) — `agent/dispatch.py`
- **run_loop()** (7 connections) — `agent/loop.py`
- **_call_raw_single_model()** (6 connections) — `agent/dispatch.py`
- **probe_structured_output()** (6 connections) — `agent/dispatch.py`
- **call_llm_raw()** (5 connections) — `agent/dispatch.py`
- **_call_openai_tier()** (5 connections) — `agent/loop.py`
- **prephase.py** (5 connections) — `agent/prephase.py`
- **get_anthropic_model_id()** (4 connections) — `agent/dispatch.py`
- **get_response_format()** (4 connections) — `agent/dispatch.py`
- **_normalize_parsed()** (4 connections) — `agent/json_extract.py`
- **is_claude_code_model()** (3 connections) — `agent/dispatch.py`
- **is_ollama_model()** (3 connections) — `agent/dispatch.py`
- **_save_capability_cache()** (3 connections) — `agent/dispatch.py`
- **_obj_mutation_tool()** (3 connections) — `agent/json_extract.py`
- **_try_json5()** (3 connections) — `agent/json_extract.py`
- **_format_result()** (3 connections) — `agent/loop.py`
- **_to_anthropic_messages()** (3 connections) — `agent/loop.py`
- **dispatch()** (2 connections) — `agent/dispatch.py`
- **_get_static_hint()** (2 connections) — `agent/dispatch.py`
- **is_claude_model()** (2 connections) — `agent/dispatch.py`
- *... and 26 more nodes in this community*

## Relationships

- [[SQL Pipeline State Machine]] (5 shared connections)
- [[Pipeline Evaluator]] (4 shared connections)
- [[Pydantic Models & Contracts]] (2 shared connections)
- [[Tracer & Logging]] (2 shared connections)
- [[Prephase & VM Bootstrap]] (2 shared connections)
- [[CC Client (Claude Code)]] (1 shared connections)
- [[Rules Loader (YAML)]] (1 shared connections)
- [[Orchestrator Entry Point]] (1 shared connections)

## Source Files

- `agent/dispatch.py`
- `agent/json_extract.py`
- `agent/loop.py`
- `agent/prephase.py`

## Audit Trail

- EXTRACTED: 170 (99%)
- INFERRED: 2 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*