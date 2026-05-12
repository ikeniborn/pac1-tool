# Tracer Removal Design

**Date:** 2026-05-12  
**Status:** Approved

## Context

`agent/tracer.py` implements a JSONL event logger (`RunTracer` + `TaskTracer`) controlled by `TRACE_ENABLED=1` env var (default: 0). It was introduced as part of П3 (replay tracer) but was never used in practice. `LOG_LEVEL=DEBUG` provides sufficient observability via existing `print()`-based logging in `loop.py`.

## Decision

Full deletion. No replacement.

- `TRACE_ENABLED=0` default means the tracer is already a no-op in all environments.
- Dead code confuses readers and adds import overhead.
- `LOG_LEVEL=DEBUG` covers all debugging needs.

## Changes

### Delete file

```
agent/tracer.py  (130 lines)
```

### agent/loop.py — remove 6 lines

| Line | Content |
|------|---------|
| 26 | `from .tracer import get_task_tracer` |
| 264 | `_tracer = get_task_tracer()` |
| 265 | `_tracer.emit("task_start", 0, {"model": model, "task_text": task_text[:200]})` |
| 306 | `_tracer.emit(step_label, step, {"action": "report_completion", "outcome": outcome})` |
| 325 | `_tracer.emit(step_label, step, {"action": action_name})` |
| 347 | `_tracer.emit("task_end", max_steps, {"outcome": outcome, ...})` |

### main.py — remove 5 lines/blocks

| Line | Content |
|------|---------|
| 87 | `from agent.tracer import init_tracer as _init_tracer, set_task_id as _set_task_id` |
| 88–89 | `if _run_dir is not None: _init_tracer(str(_run_dir))` |
| 142 | `_set_task_id(task_id)` |
| 266–267 | `from agent.tracer import close_tracer as _close_tracer` + `_close_tracer()` |

## Verification

```bash
uv run python main.py
```

Confirm: no `ImportError`, no `NameError`. Existing `LOG_LEVEL=DEBUG` output unaffected.
