# Design: Scripts Lifecycle Automation

**Date:** 2026-05-03  
**Status:** Approved

## Problem

7 utility scripts in `scripts/` require manual invocation for critical knowledge-pipeline operations:
- Graph health check (contamination detection)
- Contamination purge
- Contract distillation (from accumulated examples)
- Task-type candidate promotion
- DSPy prompt optimization

These operations need to happen at specific lifecycle moments (before/after benchmark run), not on a manual schedule.

## Solution

Introduce two lifecycle modules — `agent/preflight.py` and `agent/postrun.py` — called from `main.py`. Extract the scripts that implement agent-internal operations into a new `agent/maintenance/` package. Keep standalone dev-only scripts in `scripts/`.

## Architecture

### Script Migration

Scripts that implement agent-internal logic move into `agent/maintenance/`:

| `scripts/` (deleted) | `agent/maintenance/` (new) |
|---|---|
| `check_graph_health.py` | `agent/maintenance/health.py` |
| `purge_research_contamination.py` | `agent/maintenance/purge.py` |
| `distill_contracts.py` | `agent/maintenance/distill.py` |
| `analyze_task_types.py` | `agent/maintenance/candidates.py` |

Scripts that remain in `scripts/` (dev-only, not runtime):
- `optimize_prompts.py` — heavy DSPy optimizer, called via subprocess from postrun if enabled
- `visualize_graph.py` — debug web UI
- `print_graph.py` — CLI graph inspector

### New Lifecycle Modules

**`agent/preflight.py`** — runs before benchmark tasks:

```
PREFLIGHT_ENABLED=1?
  → graph health check (health.py)
      OK/WARN  → log, continue
      FAIL     → auto purge (purge.py --apply) → re-check
                 re-check OK   → continue
                 re-check FAIL → SystemExit(1) with reason
  → wiki pages integrity (pages/*.md non-empty check)
  → wiki graph load test (load_graph → SystemExit(1) if broken)
```

**`agent/postrun.py`** — runs after all benchmark tasks complete:

```
POSTRUN_ENABLED=1?
  → purge (purge.py --apply, idempotent)
      FAIL → SystemExit(1) with reason
  → wiki lint (run_wiki_lint called for each task_type from task_types registry)
      FAIL → SystemExit(1) with reason
  → distill_contracts (distill.py)
      only if accumulated examples ≥ POSTRUN_DISTILL_MIN_EXAMPLES
      FAIL → SystemExit(1) with reason
  → log_candidates (candidates.py)
      passive: log counts per type, no auto-promote
      FAIL → log WARNING, continue (non-critical)
  → POSTRUN_OPTIMIZE=1?
       → subprocess: python scripts/optimize_prompts.py --target all
         (inherits OPTIMIZER_BUILDER, OPTIMIZER_EVALUATOR, etc.)
         FAIL → SystemExit(1) with reason
```

**`main.py`** wiring:

```python
await preflight()          # blocks on failure if PREFLIGHT_ENABLED
await run_benchmark_tasks()
await postrun()            # blocks on failure if POSTRUN_ENABLED
```

### `agent/maintenance/__init__.py`

Empty, marks as package. Each submodule exposes one primary function:
- `health.run_health_check(graph_path, conf_threshold, fail_ratio) → (exit_code, report_lines)`
- `purge.run_purge(graph_path, archive_path, pages_dir, fragments_dir, apply) → PurgeResult`
- `distill.run_distill(min_examples, task_type) → DistillResult`
- `candidates.log_candidates(candidates_path, min_count) → CandidatesReport`

## Error Handling

**Fail-closed when enabled.** If `PREFLIGHT_ENABLED=1` or `POSTRUN_ENABLED=1`, failures in those phases raise `SystemExit(1)` with a human-readable message. The intent: these switches signal that health checks are *mandatory* for knowledge quality. Skipping them silently defeats the purpose.

**WARN vs FAIL distinction (health check only):**
- `exit_code=1` (WARN): orphan edges, low-confidence nodes below conf_threshold — log warning, do not block
- `exit_code=2` (FAIL): contamination ratio > fail_ratio — trigger auto-purge, then re-check; if still FAIL → SystemExit(1)

**Non-critical exception:** `candidates.log_candidates()` is purely observational — its failure logs a WARNING but does not stop postrun.

## Env Variables

| Variable | Default | Description |
|---|---|---|
| `PREFLIGHT_ENABLED` | `0` | Enable preflight phase |
| `POSTRUN_ENABLED` | `0` | Enable postrun phase |
| `POSTRUN_DISTILL_MIN_EXAMPLES` | `10` | Minimum score=1.0 examples to trigger distillation |
| `POSTRUN_PROMOTE_MIN_COUNT` | `5` | Minimum candidate count to include in log |
| `POSTRUN_OPTIMIZE` | `0` | Run DSPy optimize_prompts.py --target all after postrun |

All variables documented in `.env.example`.

## Testing

- **Unit tests** for each `agent/maintenance/*.py` module in `tests/test_maintenance_*.py` — synthetic graph fixtures, known contamination keywords
- **Integration tests** in `tests/test_lifecycle.py`:
  - `test_preflight_auto_purge` — FAIL health → purge → re-check OK
  - `test_preflight_fatal` — FAIL health → purge → re-check FAIL → SystemExit(1)
  - `test_postrun_distill_threshold` — below threshold → no distill, at threshold → distill called
  - `test_postrun_optimize_subprocess` — POSTRUN_OPTIMIZE=1 → subprocess called with correct args
- Existing `tests/test_security_gates.py` and `tests/test_*.py` unaffected

## FIX Label

Tag this work as `FIX-427` (next sequential after `FIX-426`, current max in codebase).
