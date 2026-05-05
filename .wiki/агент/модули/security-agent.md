---
wiki_sources:
  - "agent/agents/security_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - security
  - dispatch
aliases:
  - "SecurityAgent"
---

# SecurityAgent (agent/agents/security_agent.py)

Агент валидации инструментальных вызовов по правилам безопасности в мультиагентной архитектуре. Оборачивает функции из `agent.security` в контрактный интерфейс.

## Основные характеристики

Предоставляет три метода проверки, все возвращают `SecurityCheck(passed, violation_type, detail)`:

- **`check_write_scope(request: SecurityRequest) → SecurityCheck`:**
  Проверяет, что write-операция направлена в допустимый путь.
  Email-задачи могут писать только в `/outbox/`. Все задачи заблокированы от записи в `/docs/` и `AGENTS.MD`.
  Строит `SimpleNamespace(**request.tool_args)` для совместимости с внутренним интерфейсом `_check_write_scope`.

- **`check_injection(text: str) → SecurityCheck`:**
  Нормализует текст (leet speak, zero-width chars, homoglyphs) через `_normalize_for_injection`, затем матчит `_INJECTION_RE`.

- **`check_write_payload(content, source_path=None) → SecurityCheck`:**
  Обнаруживает инжекции команд в payload записи (embedded tool notes, conditional imperatives, authority metadata).
  Освобождает content из доверенных путей политик (`docs/channels/` и т.д.).

- **Изоляция**: импортирует только из `agent.contracts` и `agent.security`.

## Связанные концепции

- [[security]] — базовые функции `_check_write_scope`, `_check_write_payload_injection`, `_normalize_for_injection`
- [[executor-agent]] — инжектирует SecurityAgent в run_loop
