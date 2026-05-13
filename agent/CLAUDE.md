# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Authoritative CLAUDE.md is `../CLAUDE.md` (repo root). This file covers agent-package internals.**

## Commands

```bash
uv sync                                          # install all deps
uv run python -m pytest tests/ -v               # all tests
uv run pytest tests/test_pipeline.py -v         # single test file

EVAL_ENABLED=1 uv run python main.py            # run with evaluator
LOG_LEVEL=DEBUG uv run python main.py           # full LLM response logging
```

Key env vars:
- `MODEL` — primary LLM (e.g. `anthropic/claude-sonnet-4-6`)
- `EVAL_ENABLED=1` + `MODEL_EVALUATOR` — post-task LLM evaluation
- `MAX_STEPS` — unused in current pipeline (pipeline uses `_MAX_CYCLES=3`)

## Agent Package Architecture

Entry: `orchestrator.py:run_agent()` → `prephase.py` → `pipeline.py`

**Phase execution order (per cycle, up to 3 cycles):**

1. **RESOLVE** (`resolve.py:run_resolve()`) — LLM generates discovery queries (must contain `LIKE` or `DISTINCT`; ILIKE accepted but unsupported by SQLite — use LIKE); executes them to confirm DB values before SQL planning. Returns `confirmed_values: dict`.
2. **SQL_PLAN** — LLM call → `json_extract.py` → `SqlPlanOutput` (queries + agents_md_refs).
3. **AGENTS.MD refs check** — if `agents_md_refs` is empty but index terms appear in task, triggers LEARN.
4. **SECURITY** (`sql_security.py:check_sql_queries()`) — regex/named gates from `data/security/*.yaml`.
5. **SCHEMA** (`schema_gate.py:check_schema_compliance()`) — unknown columns, unverified literals, double-key JOINs on `product_properties`.
6. **VALIDATE** — `EXPLAIN <query>` via VM exec.
7. **EXECUTE** — runs queries; empty result set triggers LEARN.
8. **ANSWER** — LLM synthesises `AnswerOutput` → `vm.answer()`.
9. **LEARN** (on any failure) — LLM produces `LearnOutput`; either elevates a vault rule section or appends a session rule (max 3 kept). Called `_run_learn()` in `pipeline.py`.

**Pydantic models** (`models.py`):
- `SqlPlanOutput` — `queries`, `agents_md_refs`, `reasoning`
- `LearnOutput` — `rule_content`, `agents_md_anchor`, `reasoning`
- `AnswerOutput` — `message`, `outcome`, `grounding_refs`
- `ResolveOutput` / `ResolveCandidate` — resolve phase output
- `PipelineEvalOutput` — evaluator scoring model

**LLM routing** (`llm.py:call_llm_raw()`): provider prefix → tier.
- `anthropic/` → Anthropic SDK (prompt caching via `cache_control` blocks)
- `openrouter/` → OpenRouter (OpenAI-compatible)
- bare name / `ollama/` → local Ollama
- `CC_ENABLED=1` → `cc_client.py` subprocess (Claude Code tier)

Transient errors (503, rate-limit, timeout) retry with exponential backoff.

**Prephase** (`prephase.py:run_prephase()`): reads `/AGENTS.MD` from VM → `parse_agents_md()` → section index; executes `.schema` + `PRAGMA` queries to build `schema_digest` (columns, FK, top `product_properties` keys with value type map).

**Trace logging** (`trace.py`): thread-local `TraceLogger` writes structured JSONL. Attach with `set_trace(logger)` before pipeline; read with `get_trace()` anywhere in call chain. Records: `header`, `header_system` (deduped by SHA-256), `llm_call`, `gate_check`, `sql_validate`, `sql_execute`, `resolve_exec`, `task_result`.

**Prompt loading** (`prompt.py:load_prompt(phase)`): reads `data/prompts/{phase}.md`. Phases: `resolve`, `sql_plan`, `learn`, `answer`. The guide block is always last in the system message and marked `cache_control: ephemeral`.

**Rules** (`rules_loader.py:RulesLoader`): loads `data/rules/*.yaml`; only `verified: true` rows injected. Cached module-level in `pipeline.py`.

## Notable Constraints

- JSON extraction priority in `json_extract.py` is load-bearing: mutation tools take priority over reads.
- `schema_gate.py` checks unverified string literals copied from task text — run RESOLVE first to populate `confirmed_values`.
- `_run_learn` keeps only the last 3 session rules (`session_rules[-3:]`).
- RESOLVE queries are security-checked: must contain `LIKE` or `DISTINCT` (ILIKE accepted but unsupported by SQLite); DDL/DML blocked.
- System prompt blocks are passed as `list[dict]` (Anthropic multi-block format) for `sql_plan`/`learn`/`answer` phases; `resolve` uses a plain string.
- `loop.py` and `dispatch.py` no longer exist — replaced by `pipeline.py` and `llm.py`.
