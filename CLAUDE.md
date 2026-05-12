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

Key env vars (copy from `.env.example` + `.secrets.example`):
- `MODEL` — primary LLM (e.g. `anthropic/claude-sonnet-4-6`)
- `EVAL_ENABLED=1` — run evaluator after each task, populate `data/eval_log.jsonl`
- `MODEL_EVALUATOR` — separate LLM for evaluation
- `LOG_LEVEL=DEBUG` — full LLM response logging
- `MAX_STEPS=5` — pipeline cycle limit per task

## Architecture

Entry point: `main.py` → BitGN harness → `agent/orchestrator.py:run_agent()`

**Execution flow per task:**
1. `prephase.py:run_prephase()` — fetches `/AGENTS.MD` (vault rules), reads `.schema`, loads prompt blocks
2. `prompt.py:build_system_prompt()` — assembles modular system prompt from `data/prompts/*.md` blocks, security gates, in-session learned rules
3. `pipeline.py:run_pipeline()` — main loop (max 3 cycles):
   - **SQL_PLAN** → LLM call → `json_extract.py` (7-priority extraction) → `SqlPlanOutput` (Pydantic)
   - **SECURITY CHECK** → `sql_security.py` validates against `data/security/*.yaml` gates
   - **VALIDATE** → EXPLAIN check for SQL syntax
   - **EXECUTE** → runs SQL on ECOM VM via Connect-RPC
   - On failure: **LEARN** phase extracts a rule, retry with updated context
   - On success: **ANSWER** phase synthesizes response
4. Optional **EVALUATE** (`evaluator.py`) — LLM scores pipeline trace, appends suggestions to `data/eval_log.jsonl`

**LLM routing** (`llm.py`): provider prefix determines tier — `anthropic/` → Anthropic SDK; `openrouter/` → OpenRouter; `ollama/` or bare name → local Ollama. Transient errors retry with backoff.

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
| `models.json` | Per-model provider hints and Ollama options |

## Notable Constraints

- `agent/loop.py` excluded from pyright type checking (see `pyproject.toml`)
- JSON extraction priority in `json_extract.py` is load-bearing: mutation tools (write/delete) take priority over reads to avoid spurious tool calls
- Security gates run **before** SQL execution; a blocked query is never executed
- `propose_optimizations.py` synthesizers receive existing rules/prompts to prevent duplicate generation — preserve the `_existing_*` helpers if refactoring
- `agent/CLAUDE.md` is outdated (references `loop.py`/`dispatch.py` from old architecture); this file is authoritative
