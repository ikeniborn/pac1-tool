---
wiki_sources:
  - "agent/log_compaction.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - compaction
aliases:
  - "_compact_log"
  - "Prefix-Compaction"
  - "log compaction"
---

# Log Compaction (agent/log_compaction.py)

Управление контекстным окном: скользящее сжатие лога, накопление фактов о шагах, компактное представление tool results. Избегает потери task understanding без полного сброса контекста.

## Основные характеристики

### `_StepFact`

Dataclass: одна ключевая единица информации о завершённом шаге (kind + path). Накапливается loop.py и передаётся в stall-детекцию.

### `_compact_log(log, preserve_prefix, max_tokens)`

Скользящее окно: сохраняет первый system prompt + few-shot пару (preserve_prefix) + последние 5 сообщений. Middle компактируется через `build_digest()`.

### `build_digest(step_facts)`

Строит compact state digest из накопленных фактов. Инжектируется в середину лога вместо вытесненных сообщений.

### `_compact_tool_result(action_name, txt)`

- `Req_Read` → full content (ответ может содержаться в файле)
- `Req_List` → `entries: name1, name2, ...`
- `Req_Search` → `matches: path:line, ...`
- Write/Delete/Error/Tree → без изменений (уже компактны или важны verbatim)

### `_estimate_tokens(log)`

Оценка: 3 chars/token (консервативно для mixed RU/EN).

## Связанные концепции

- [[loop]] — вызывает `_compact_log` при превышении token budget
- [[stall]] — использует `_StepFact` для контекста в hints
