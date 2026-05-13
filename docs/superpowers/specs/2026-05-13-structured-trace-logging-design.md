# Structured JSONL Trace Logging

**Date:** 2026-05-13  
**Status:** Approved

## Goal

Replace per-task plain-text logs (`t01.log`) with structured JSONL traces (`t01.jsonl`). Each file captures the full pipeline execution for one task: every LLM call (request + response), SQL execution, gate checks, and final result. `main.log` stays as the human-readable run summary.

## Architecture

**Thread-local singleton** — new module `agent/trace.py` exposes `TraceLogger` + `get_trace()` / `set_trace()` via `threading.local()`. Matches the existing `_task_local` pattern in `main.py`. Zero changes to function signatures across the codebase; any callsite that wants to log calls `get_trace()` and gets `None` (no-op) if no logger is set.

## New Module: `agent/trace.py`

```
TraceLogger
  __init__(path: Path, task_id: str)
  log_header(task_text, model)          → type: "header"
  log_llm_call(phase, cycle, system,    → type: "llm_call"
               user_msg, raw_response,
               parsed_output, tokens_in,
               tokens_out, duration_ms)
  log_gate_check(cycle, gate_type,      → type: "gate_check"
                 queries, blocked, error)
  log_sql_validate(cycle, query,        → type: "sql_validate"
                   result, error)
  log_sql_execute(cycle, query, result, → type: "sql_execute"
                  has_data, duration_ms)
  log_resolve_exec(query, result,       → type: "resolve_exec"
                   value)
  log_task_result(outcome, score,       → type: "task_result"
                  cycles, total_in,
                  total_out, elapsed_ms,
                  score_detail)
  close()

get_trace() → TraceLogger | None
set_trace(logger: TraceLogger | None)
```

**System prompt deduplication:** `_sys_sha256(system)` computes `hashlib.sha256` over JSON-serialised blocks. On first occurrence of a new hash, a `header_system` record is written (full blocks + hash). Subsequent `llm_call` records reference the hash only (`system_sha256`).

## JSONL Record Schema

All records share common fields:

```json
{
  "ts": "<ISO-8601>",
  "task_id": "t01",
  "type": "<record_type>",
  ...type-specific fields...
}
```

### `header`
```json
{
  "type": "header",
  "task_text": "...",
  "model": "minimax-m2.7:cloud"
}
```

### `header_system`
Written once per unique system prompt, just before the first `llm_call` that uses it.
```json
{
  "type": "header_system",
  "sha256": "abc123...",
  "blocks": [{"type": "text", "text": "..."}]
}
```

### `llm_call`
```json
{
  "type": "llm_call",
  "cycle": 1,
  "phase": "sql_plan",
  "system_sha256": "abc123...",
  "user_msg": "TASK: ...\n\nPREVIOUS ERROR: ...",
  "raw_response": "...",
  "parsed_output": {"queries": [...], "reasoning": "..."},
  "tokens_in": 7499,
  "tokens_out": 1479,
  "duration_ms": 12300,
  "success": true
}
```
`phase` values: `resolve`, `sql_plan`, `learn`, `answer`.  
`cycle`: 0 for resolve, 1–3 for pipeline cycles.

### `gate_check`
```json
{
  "type": "gate_check",
  "cycle": 1,
  "gate_type": "schema",
  "queries": ["SELECT ..."],
  "blocked": true,
  "error": "SCHEMA gate blocked: unverified literal: 'Heco'"
}
```
`gate_type`: `"security"` | `"schema"`. `error` is `null` when `blocked: false`.

### `sql_validate`
```json
{
  "type": "sql_validate",
  "cycle": 1,
  "query": "SELECT ...",
  "explain_result": "...",
  "error": null
}
```

### `sql_execute`
```json
{
  "type": "sql_execute",
  "cycle": 1,
  "query": "SELECT DISTINCT brand FROM products WHERE ...",
  "result": "brand\nHeco\n",
  "has_data": true,
  "duration_ms": 230
}
```

### `resolve_exec`
```json
{
  "type": "resolve_exec",
  "query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE '%Heco%'",
  "result": "brand\nHeco\n",
  "value_extracted": "Heco"
}
```

### `task_result`
```json
{
  "type": "task_result",
  "outcome": "OUTCOME_NONE_CLARIFICATION",
  "score": 0.0,
  "cycles_used": 3,
  "total_tokens_in": 7499,
  "total_tokens_out": 1479,
  "elapsed_ms": 65000,
  "score_detail": ["answer missing required reference '/proc/catalog/FST-2JPIIG2S.json'"]
}
```

## Instrumentation Points

| File | Location | Action |
|------|-----------|--------|
| `main.py` | after task start | `set_trace(TraceLogger(run_dir / f"{task_id}.jsonl", task_id))` + `log_header` |
| `main.py` | after `end_trial()`, before `return` | `log_task_result(score, score_detail, ...)` |
| `main.py` | `finally` block | `trace.close()` + `set_trace(None)` |
| `main.py` | `_Tee.write` + `_run_single_task` | remove per-task `log_fh` open/write/close |
| `pipeline.py` | `_call_llm_phase` signature | add `cycle: int` parameter; wrap `call_llm_raw` with timer, call `log_llm_call` |
| `pipeline.py` | after `check_sql_queries` | `log_gate_check(gate_type="security")` always (blocked or not) |
| `pipeline.py` | after `check_schema_compliance` | `log_gate_check(gate_type="schema")` always |
| `pipeline.py` | VALIDATE loop | `log_sql_validate` per query |
| `pipeline.py` | EXECUTE loop | `log_sql_execute` per query with timer |
| `resolve.py:_run` | after `call_llm_raw` | `log_llm_call(phase="resolve", cycle=0)`; pass `token_out=tok` to `call_llm_raw` to capture token counts |
| `resolve.py:_run` | after each `_exec_sql` | `log_resolve_exec` |

## Files Changed

- `agent/trace.py` — new module
- `agent/pipeline.py` — add trace calls in `_call_llm_phase`, `run_pipeline`
- `agent/resolve.py` — add trace calls in `_run`
- `main.py` — create/close TraceLogger, remove per-task `.log` file writes

## What Is NOT Changed

- `main.log` — stays, stdout tee continues
- `agent/llm.py` — not touched (tracing at pipeline level is sufficient)
- `agent/evaluator.py` — not touched (reads `sgr_trace` from pipeline, independent)
- `sgr_trace` — stays (evaluator depends on it), just no longer the primary trace mechanism

## Constraints

- Thread-safe: each task runs in its own thread with its own `TraceLogger` in thread-local storage
- No-op when trace not set: all callsites guard with `if t := get_trace():`
- `main.log` loses per-task detail (SQL queries, LLM outputs) — that detail moves to `.jsonl`; `main.log` keeps the summary lines printed to stdout
