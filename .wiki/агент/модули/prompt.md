---
wiki_sources:
  - "agent/prompt.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - prompt
aliases:
  - "build_system_prompt"
  - "system prompt"
---

# Prompt System (agent/prompt.py)

Билдер системного промпта для агента. Архитектура: модель — pure text generator, эмитирующий структурированный JSON (Pydantic `NextStep`). Claude-native function calling не используется.

## Основные характеристики

- **`build_system_prompt(task_type)`** — собирает промпт из `_CORE` + task-type-специфичного блока (`_TASK_BLOCKS[task_type]`)
- **`_CORE`** — обязательная часть: формат ответа (5 полей JSON), список 9 инструментов, outcome-константы, quick rules (preject/clarification/security), discovery-first принцип
- **`_TASK_BLOCKS`** — dict task_type → доп. блок; типы не в словаре наследуют `default` блок (warn-once на старте)
- **Discovery-first**: системный промпт не хардкодит пути vault. Агент узнаёт роли папок из AGENTS.MD в prephase

### 9 инструментов в промпте

`list`, `read`, `write`, `delete`, `find`, `search`, `tree`, `move`, `mkdir`, `report_completion`

### Формат ответа (обязательные 5 полей)

```json
{"current_state":"...", "plan_remaining_steps_brief":["..."], "done_operations":["WRITTEN: /path"], "task_completed":false, "function":{"tool":"...", ...}}
```

## Связанные концепции

- [[orchestrator]] — передаёт prompt в prephase.log[0]
- [[prephase]] — загружает vault-контекст до запуска цикла
- [[prompt-builder]] — добавляет task-specific addendum к системному промпту
