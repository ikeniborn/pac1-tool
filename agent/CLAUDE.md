# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install all deps (main + dev)
uv run python main.py            # run all benchmark tasks
make task TASKS='t01,t03'        # run specific tasks

uv run python -m pytest tests/ -v              # all tests
uv run pytest tests/test_json_extraction.py -v # single test file

make proto                       # rebuild protobuf stubs (buf generate)
uv run python scripts/optimize_prompts.py --target all  # DSPy optimization
```

Key env vars (copy from `.env.example` + `.secrets.example`):
- `MODEL` — primary LLM (e.g. `anthropic/claude-sonnet-4-6`)
- `MAX_STEPS` — agent loop iterations per task (default: 5)
- `DRY_RUN=1` — prephase only, no LLM calls, writes `data/dry_run_analysis.jsonl`
- `LOG_LEVEL=DEBUG` — full LLM response logging

## Architecture

Entry point: `main.py` → BitGN harness → `agent/orchestrator.py:run_agent()`

**Execution flow per task:**
1. `prephase.py:run_prephase()` — reads `/AGENTS.MD` and injects task text; if `DRY_RUN=1`, also reads `/bin/sql` and writes `data/dry_run_analysis.jsonl`
2. `prompt.py:build_system_prompt()` — assemble modular system prompt from blocks (`_CORE`, `_LOOKUP`, task-specific rules)
3. `loop.py:run_loop()` — main loop up to `MAX_STEPS`:
   - `dispatch.py:dispatch()` → LLM call (Anthropic → OpenRouter → Ollama fallback)
   - `json_extract.py` → extract `NextStep` JSON from response (7-level priority: fenced block → mutation tool → known tool → full NextStep → object with 'function' → YAML)
   - Validate against Pydantic `NextStep` + `Req_*` models in `models.py`
   - Execute tool against ECOM runtime via Connect-RPC (PCM + ECOM protobuf services)
   - Security gate check → stall detection → log compaction
4. `bitgn/harness_connect.py:EndTrialRequest` → return score

**LLM routing:** `dispatch.py` routes by provider prefix. Capability probing cached 7 days in `.cache/capability_cache.json`. Transient errors (503, rate-limit, timeout) retry with backoff.

**Protobuf layer:** `bitgn/` contains generated stubs for harness + ECOM + PCM services. Source protos in `proto/`. Regenerate with `make proto` (requires `buf`).

**DSPy:** Classifier, prompt builder, and evaluator can be compiled via `scripts/optimize_prompts.py`. Compiled programs saved as `data/*_program.json`. Training data in `data/dspy_examples.jsonl`.

**Key data files:**
- `data/task_types.json` — task type registry (soft/hard classification status)
- `data/models.json` — per-model provider hints and ollama options
- `logs/{ts}_{model}/` — per-run logs + optional `traces.jsonl` (`TRACE_ENABLED=1`)

## Notable Constraints

- `agent/loop.py` is excluded from pyright type checking (see `pyproject.toml`)
- `prephase.py` receives `system_prompt` as arg — must be passed explicitly from orchestrator (see fix commit 4e710c2)
- JSON extraction priority order in `json_extract.py` is load-bearing; mutation tools (write/delete) are preferred over read tools to avoid spurious reads
- Security gates run before tool execution; violations log to task trace but do not raise by default
