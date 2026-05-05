---
wiki_sources:
  - "agent/stall.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - stall
aliases:
  - "_check_stall"
  - "stall detection"
---

# Stall Detection (agent/stall.py)

Модуль обнаружения зависания агента в цикле (FIX-74). Три независимых сигнала, обнаруживаемых без LLM-вызовов.

## Основные характеристики

### Три сигнала (в порядке приоритета)

1. **Action loop** — последние 3 fingerprint идентичны → агент вызывает один инструмент с теми же аргументами. Hint включает recent actions и agreed contract plan
2. **Repeated path error** — одна и та же комбинация `(tool, path, error_code)` ≥ 2 раз → путь не существует. Hint называет parent dir для `list`
3. **Exploration stall** — ≥ 6 шагов без write/delete/move/mkdir → агент исследует без действий. При ≥ 12 шагах — эскалация

### `_handle_stall_retry(hint, ...)`

Внедряет hint в следующее user-сообщение и вызывает LLM один раз с dependency-injected функцией `call_llm_fn`. Не реализует retry-loop сам по себе — loop.py вызывает эту функцию при обнаружении stall.

## Связанные концепции

- [[loop]] — вызывает `_check_stall` и `_handle_stall_retry` в каждой итерации
- [[log-compaction]] — `_StepFact` используется для контекста в stall-хинтах
