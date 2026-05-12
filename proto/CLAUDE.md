# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

RPC contract definitions (Protobuf) between the ecom1-agent and the BitGN benchmark harness. Not executable — only source-of-truth for the generated Python stubs in `../bitgn/`.

**Never edit files in `../bitgn/` directly** — they are auto-generated from these protos.

## Regenerating stubs

```bash
# From project root (ecom1-agent/)
make proto   # runs: buf generate
```

Requires `buf` CLI. Generated output goes to `../bitgn/`.

## Proto files

### `bitgn/harness.proto` — Benchmark lifecycle

`HarnessService` — 7 RPCs used by `main.py` via `HarnessServiceClientSync`:

| RPC | Purpose |
|---|---|
| `GetBenchmark` | Fetch task list + eval policy |
| `StartRun` | Initiate a benchmark run, returns `trial_ids` |
| `StartTrial` | Start one trial → returns `harness_url` + `instruction` |
| `EndTrial` | Finish trial → returns `score` (float) + `score_detail` |
| `SubmitRun` | Finalize and submit all results |
| `StartPlayground` | Interactive/debug mode (not used in batch) |
| `Status` | Health check |

### `bitgn/vm/ecom/ecom.proto` — ECOM vault runtime (current)

`EcomRuntime` — used by `agent/orchestrator.py` via `EcomRuntimeClientSync`. 11 RPCs exposing a virtual ecommerce-OS filesystem:

**Read ops:** `Context`, `Read`, `List`, `Tree`, `Find`, `Search`, `Stat`  
**Write ops:** `Write`, `Delete`  
**Exec:** `Exec` — restricted to deterministic in-runtime tools like `/bin/sql`; must not become host process execution  
**Completion:** `Answer(message, outcome, refs)` — submits task result

Key ECOM-specific features vs PCM:
- `ReadResponse.sha256` — SHA-256 of full file content (use with `WriteRequest.if_match_sha256` for optimistic locking)
- `WriteResponse.audit_path` / `.action_id` / `.action_status` — audit receipt for `/run/actions/*` writes
- `StatResponse.write_schema` + `write_schema_content_type` — JSON Schema for action files
- `Outcome` enum has `OUTCOME_UNSPECIFIED = 0` (unlike PCM where `OUTCOME_OK = 0`)

### `bitgn/vm/pcm.proto` — PCM vault runtime (legacy)

`PcmRuntime` — older flat interface, similar capabilities to ECOM but simpler. 10 RPCs: `Tree`, `Find`, `Search`, `List`, `Read`, `Write`, `Delete`, `MkDir`, `Move`, `Answer`, `Context`.

Differences from ECOM:
- No SHA-256 preconditions on writes
- No audit trail / action status
- No `Stat` RPC
- `Write` supports line-range patching (`start_line`/`end_line`)
- `MkDir` and `Move` exist (ECOM does not have them)
- `ContextResponse.content` is a string (ECOM returns structured `unix_time` + RFC3339 `time`)

## Parent project architecture (brief)

The agent (`../`) uses these protos as follows:

```
main.py
  └── HarnessService.StartTrial() → harness_url
        └── agent/orchestrator.py
              ├── prephase: EcomRuntime.{Tree, Read, Find, Search}
              └── loop: EcomRuntime.{Read,Write,Delete,Exec,Find,Search,Answer}
```

`Answer.outcome` values the agent sends: `OUTCOME_OK` (success), `OUTCOME_DENIED_SECURITY` (injection/scope violation), `OUTCOME_NONE_CLARIFICATION` (ambiguous task), `OUTCOME_NONE_UNSUPPORTED` (tool not available), `OUTCOME_ERR_INTERNAL` (agent crash).
