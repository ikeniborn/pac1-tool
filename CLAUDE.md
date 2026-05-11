# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make sync              # Install dependencies (uv sync)
make run               # Run all benchmark tasks
uv run python main.py t01,t03   # Run specific tasks
uv run python -m pytest tests/  # Run all tests
uv run pytest tests/test_sql_adaptation.py -v  # Run single test file
```

Environment: copy `.env.example` → `.env`, fill `MODEL` and `BENCHMARK_HOST`.

## Architecture

Single-purpose agent: receives e-commerce task text from BitGN benchmark harness via gRPC, executes it against an SQL runtime, returns outcome.

**Execution pipeline:**
```
main.py → _run_single_task() → run_agent()
  ├─ prephase.py   — reads vault tree, AGENTS.md, SQL schema from VM
  └─ loop.py       — LLM tool-call loop (max MAX_STEPS iterations)
       ├─ dispatch.py   — LLM routing: Anthropic → OpenRouter → Ollama
       ├─ prompt.py     — builds system prompt + tool definitions
       └─ models.py     — Pydantic schemas for LLM output (NextStep, Req_Write…)
```

**Key contracts:**
- `agent/models.py` — all structured LLM output types; touch here when adding/changing tools
- `agent/prompt.py` — system prompt + tool JSON schema; must stay in sync with `models.py`
- `agent/loop.py` — parses `NextStep.action` and dispatches to VM tools; tool routing lives here
- `bitgn/harness_connect.py` — gRPC client for benchmark harness (generated stubs in `bitgn/`)
- `bitgn/vm/ecom/ecom_connect.py` — gRPC client for SQL runtime

**LLM routing** (`dispatch.py`): MODEL env var selects profile from `models.json`. Falls back OpenRouter → Ollama on timeout/error. Raw request/response logged to `logs/` via `tracer.py`.

**Outcomes:** loop terminates when LLM returns `action=DONE` with one of: `OK`, `DENIED_SECURITY`, `CLARIFICATION`, `UNSUPPORTED`.

## Key env vars

| Var | Default | Effect |
|-----|---------|--------|
| `MODEL` | `claude-sonnet-4-6` | LLM profile (see `models.json`) |
| `DRY_RUN` | `0` | `1` = prephase only, no LLM loop, writes `data/dry_run_analysis.jsonl` |
| `MAX_STEPS` | `5` | Max loop iterations per task |
| `PARALLEL_TASKS` | `1` | Concurrent task workers |
| `LOG_LEVEL` | `INFO` | `DEBUG` logs raw LLM payloads |

## Conventions

- `bitgn/` — generated protobuf stubs, do not edit manually
- `docs/architecture/` — detailed design docs for each subsystem (01–09)
- `data/` — runtime artifacts (JSONL traces, not committed)
- `logs/` — per-run directories with per-task logs
- Dead subsystems (DSPy, contracts, wiki) already removed; `docs/architecture/04` and `07` are archived for reference only
