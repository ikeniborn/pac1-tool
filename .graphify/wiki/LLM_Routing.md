# LLM Routing

> 37 nodes · cohesion 0.07

## Key Concepts

- **llm.py** (19 connections) — `agent/llm.py`
- **_call_raw_single_model()** (9 connections) — `agent/llm.py`
- **get_provider()** (7 connections) — `agent/llm.py`
- **test_llm_module.py** (6 connections) — `tests/test_llm_module.py`
- **probe_structured_output()** (5 connections) — `agent/llm.py`
- **_system_as_str()** (5 connections) — `agent/llm.py`
- **get_anthropic_model_id()** (4 connections) — `agent/llm.py`
- **is_claude_code_model()** (4 connections) — `agent/llm.py`
- **is_ollama_model()** (4 connections) — `agent/llm.py`
- **is_claude_model()** (3 connections) — `agent/llm.py`
- **_save_capability_cache()** (3 connections) — `agent/llm.py`
- **test_system_as_str_from_blocks()** (3 connections) — `tests/test_llm_module.py`
- **test_system_as_str_passthrough_str()** (3 connections) — `tests/test_llm_module.py`
- **get_response_format()** (2 connections) — `agent/llm.py`
- **_get_static_hint()** (2 connections) — `agent/llm.py`
- **_load_capability_cache()** (2 connections) — `agent/llm.py`
- **Flatten system prompt blocks to plain string for non-caching tiers.** (2 connections) — `agent/llm.py`
- **_load_secrets()** (1 connections) — `agent/llm.py`
- **Load persisted cache, filtering stale entries (>7 days).** (1 connections) — `agent/llm.py`
- **Persist current cache to disk. Non-critical — failure is silently ignored.** (1 connections) — `agent/llm.py`
- **Detect if model supports response_format. Returns 'json_object' or 'none'.     C** (1 connections) — `agent/llm.py`
- **Build response_format dict for the given mode, or None if mode='none'.** (1 connections) — `agent/llm.py`
- **True for Ollama-format models (name:tag, no slash).     Examples: qwen3.5:9b, de** (1 connections) — `agent/llm.py`
- **True for claude-code/* aliases routed to iclaude subprocess.** (1 connections) — `agent/llm.py`
- **Determine LLM provider for a model call.     Explicit cfg['provider'] wins; fall** (1 connections) — `agent/llm.py`
- *... and 12 more nodes in this community*

## Relationships

- [[LLM Raw Call]] (2 shared connections)
- [[Community 15]] (1 shared connections)
- [[Pipeline System Builder]] (1 shared connections)
- [[Dispatch (Legacy)]] (1 shared connections)
- [[Prephase & Schema]] (1 shared connections)
- [[Resolve Phase]] (1 shared connections)

## Source Files

- `agent/llm.py`
- `tests/test_llm_module.py`

## Audit Trail

- EXTRACTED: 99 (96%)
- INFERRED: 4 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*