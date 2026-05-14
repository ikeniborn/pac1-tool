# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                          # install all deps
uv run python main.py                            # run all benchmark tasks
make task TASKS='t01,t03'                        # run specific tasks
EVAL_ENABLED=1 uv run python main.py             # run with evaluator

uv run python -m pytest tests/ -v               # all tests
uv run pytest tests/test_propose_optimizations.py -v  # single file

uv run python scripts/propose_optimizations.py --dry-run  # preview suggestions
uv run python scripts/propose_optimizations.py            # write to data/

make proto                                       # rebuild protobuf stubs (requires buf)
```

## Environment Variables

Copy from `.env.example` + `.secrets.example`. Core vars:

| Var | Purpose |
|-----|---------|
| `MODEL` | Primary LLM (`anthropic/claude-sonnet-4-6`, `openrouter/…`, `ollama/…`, or bare Ollama name) |
| `MODEL_FALLBACK` | Fallback model tried after primary exhausts all tiers (FIX-417) |
| `MODEL_EVALUATOR` | LLM for evaluation scoring (defaults to `MODEL` if unset) |
| `MODEL_TEST_GEN` | LLM for TDD test generation (defaults to `MODEL` if unset) |
| `EVAL_ENABLED=1` | Run evaluator after each task, populate `data/eval_log.jsonl` |
| `TDD_ENABLED=1` | Enable TDD mode: generate and run tests before ANSWER phase |
| `MAX_STEPS` | Pipeline cycle limit per task (default 3) |
| `LOG_LEVEL=DEBUG` | Full LLM response logging |
| `OLLAMA_BASE_URL` | Ollama endpoint (default `http://localhost:11434/v1`) |
| `OLLAMA_API_KEY` | API key for OpenAI-compatible proxy; falls back to `"ollama"` when absent/empty |
| `CC_ENABLED=1` | Enable Claude Code CLI tier (iclaude subprocess, OAuth) |
| `LLM_HTTP_READ_TIMEOUT_S` | HTTP read timeout in seconds (default 180) |

Credentials (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`) belong in `.secrets`, not `.env`.

## Architecture

Entry point: `main.py` → BitGN harness → `agent/orchestrator.py:run_agent()`

**Execution flow per task:**
1. `prephase.py:run_prephase()` — fetches `/AGENTS.MD` (vault rules), reads `.schema`, loads prompt blocks
2. `resolve.py:run_resolve()` — **RESOLVE phase**: confirms task identifiers (SKUs, categories) against DB via LIKE/DISTINCT queries before any SQL planning; populates `confirmed_values`
3. `prompt.py:build_system_prompt()` — assembles modular system prompt from `data/prompts/*.md` blocks, security gates, in-session learned rules
4. `pipeline.py:run_pipeline()` — main loop (max `MAX_STEPS` cycles):
   - **SQL_PLAN** → LLM call → `json_extract.py` (7-priority extraction) → `SqlPlanOutput` (Pydantic)
   - **SECURITY CHECK** → `sql_security.py` validates against `data/security/*.yaml` gates
   - **SCHEMA CHECK** → `schema_gate.py` validates column/table names against `.schema`
   - **VALIDATE** → EXPLAIN check for SQL syntax
   - **EXECUTE** → runs SQL on ECOM VM via Connect-RPC
   - On failure: **LEARN** phase extracts a rule, retry with updated context
   - On success: **ANSWER** phase synthesizes response
5. Optional **TDD** (`test_runner.py`) — generates and runs SQL tests before ANSWER when `TDD_ENABLED=1`
6. Optional **EVALUATE** (`evaluator.py`) — LLM scores pipeline trace, appends suggestions to `data/eval_log.jsonl`

**LLM routing** (`llm.py`): provider prefix determines tier — `anthropic/` → Anthropic SDK; `openrouter/` → OpenRouter; `ollama/` or bare name → local Ollama; `claude-code` provider → CC CLI subprocess. All tiers tried in order per `models.json` config before falling through to `MODEL_FALLBACK`. Transient errors retry with backoff.

**Optimization loop** (`scripts/propose_optimizations.py`):
- Reads `data/eval_log.jsonl`, synthesizes suggestions via LLM
- Checks existing rules/gates to avoid duplicates (hashes stored in `.eval_optimizations_processed`)
- Three output channels, all require human review before activation:
  - `rule_optimization` → `data/rules/sql-NNN.yaml` (set `verified: true` to activate)
  - `security_optimization` → `data/security/sec-NNN.yaml` (set `verified: true`)
  - `prompt_optimization` → `data/prompts/optimized/YYYY-MM-DD-NN-<block>.md` (manually copy to main block)

**Protobuf layer:** `bitgn/` = generated stubs for harness + ECOM + PCM services. Source protos in `proto/`. Regenerate with `make proto`.

## Key Data Files

| Path | Purpose |
|------|---------|
| `data/rules/*.yaml` | SQL planning rules; only `verified: true` rows are loaded |
| `data/security/*.yaml` | Security gates (regex pattern or named check); `verified: true` to activate |
| `data/prompts/*.md` | Modular system prompt blocks (`core`, `lookup`, `catalogue`, `sql_plan`, `answer`) |
| `data/prompts/optimized/` | Generated prompt patches awaiting manual review |
| `data/eval_log.jsonl` | Per-task evaluation results and optimization suggestions |
| `models.json` | Per-model provider hints and Ollama options (e.g. `ollama_model` override, `num_ctx`) |

## Notable Constraints

- `agent/loop.py` excluded from pyright type checking (see `pyproject.toml`)
- JSON extraction priority in `json_extract.py` is load-bearing: mutation tools (write/delete) take priority over reads to avoid spurious tool calls
- Security gates run **before** SQL execution; a blocked query is never executed
- `propose_optimizations.py` synthesizers receive existing rules/prompts to prevent duplicate generation — preserve the `_existing_*` helpers if refactoring
- `agent/CLAUDE.md` is outdated (references `loop.py`/`dispatch.py` from old architecture); this file is authoritative
- `_rules_loader_cache` and `_security_gates_cache` in `pipeline.py` are module-level — call `tests/conftest.py:reset_pipeline_caches()` fixture to clear between tests
