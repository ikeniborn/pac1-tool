---
wiki_sources:
  - "agent/agents/compaction_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - compaction
  - dispatch
aliases:
  - "CompactionAgent"
---

# CompactionAgent (agent/agents/compaction_agent.py)

Агент компакции лога сообщений в мультиагентной архитектуре. Оборачивает функции `_compact_log` и `_estimate_tokens` из `agent.log_compaction` в контрактный интерфейс.

## Основные характеристики

- **Метод `compact(request: CompactionRequest) → CompactedLog`:**
  - Конвертирует `request.step_facts_dicts` (список dict) в `_StepFact` объекты.
  - Вычисляет токены до компакции через `_estimate_tokens`.
  - Вызывает `_compact_log(messages, preserve_prefix, step_facts, token_limit)`.
  - Вычисляет `tokens_saved = max(0, before - after)`.
- **Возвращает** `CompactedLog`: `messages` (скомпакченный список), `tokens_saved`.
- Агенты без состояния — один экземпляр может переиспользоваться.

## Связанные концепции

- [[log-compaction]] — содержит `_compact_log` и `_estimate_tokens`
- [[executor-agent]] — инжектирует CompactionAgent в run_loop
