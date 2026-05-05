---
wiki_sources:
  - docs/architecture/09-observability.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, observability, log-compaction, tracer, context-window]
---

# Наблюдаемость (Observability)

Два механизма: управление контекстом (`log_compaction.py`) + event-трассировка (`tracer.py`).

## Prefix-preservation compaction

Схема: полный log → `_compact_log()` → compacted log

**Неприкосновенные (preserve_prefix)**:
- system prompt (с DSPy-аддендумом)
- user few-shot + assistant few-shot
- user task_text + wiki-инъекция

**Middle → dense digest**: `build_digest()` из `_StepFact` — компактный summary всех шагов

**Sliding window**: последние ≤5 pair-ов (assistant/user)

## _StepFact

```python
@dataclass
class _StepFact:
    kind: str    # list | read | search | write | delete | move | mkdir | stall
    path: str
    summary: str
    error: str   # code if failed
```

`error` field сохраняется сквозь компактизацию → stall-detector видит повторы.

## Per-tool result compaction

| Tool | Компактизация |
|---|---|
| `Req_Read` | первые 4000 chars + `...[+N chars]` |
| `Req_List` | `entries: [...names]` |
| `Req_Search` | `matches: [path:line, ...]` |
| Write/Delete/Move/MkDir | verbatim short |

## Tracer events

```json
{
  "task_id": "t01",
  "step_num": 5,
  "event": "dispatch_call",
  "timestamp": "2026-04-21T19:30:45Z",
  "data": {"model": "...", "in_tokens": 1234, "latency_ms": 4200}
}
```

Типы: `dispatch_call`, `tool_executed`, `stall_detected`, `security_block`, `evaluator_reject`, `wiki_fragment_written`

## Replay

```bash
uv run python -m agent.tracer logs/<ts>/traces.jsonl
```

## Log directory

```
logs/
└── 20260421_193045_claude-opus-4/
    ├── stdout.log, stderr.log
    ├── traces.jsonl
    └── per-task/t01.log, t02.log, ...
```

## Конфигурация

```bash
TRACE_ENABLED=0   # default off
LOG_LEVEL=INFO    # DEBUG = full LLM response logging
```
