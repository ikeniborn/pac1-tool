---
wiki_sources:
  - "agent/security.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - security
aliases:
  - "_check_write_scope"
  - "инъекции"
  - "injection normalization"
---

# Security (agent/security.py)

Модуль безопасности: нормализация входного текста перед проверкой инъекций, паттерны контаминации, формат-гейт inbox-сообщений, inbox-инъекции, gate на scope записи.

## Основные характеристики

### FIX-203: Нормализация для инъекций

`_normalize_for_injection(text)` применяет до regex-проверок:
- Удаляет zero-width символы (`​`, `‌`, `‍`, `⁠`, `﻿`)
- NFKC-нормализация unicode (гомоглифы → ASCII)
- Leet-замены: `0→o`, `1→l`, `3→e`, `4→a`, `5→s`, `@→a`

### FIX-203/329: Инъекционные паттерны

`_INJECTION_RE` (компилируется при загрузке): "ignore previous instructions", "disregard", "new task:", "system prompt:", `"tool": "report_completion"`, bridge-relay инъекции (FIX-329: "security relay: authenticated", "mirrored through internal bridge", "trusted operational guidance").

### FIX-206: Контаминация outbox email

`_CONTAM_PATTERNS` — список `(regex, label)` для обнаружения vault-контекста в теле письма: vault paths (`/folder/`), tree-вывод (`├──`), tool results (`Req_*`), ссылки на `AGENTS.MD`.

### FIX-214: Формат-гейт inbox

`_FORMAT_GATE_RE` — inbox-сообщение должно начинаться с `From:` или `Channel:`.

### FIX-215/281: Inbox инъекции

`_INBOX_INJECTION_PATTERNS` — паттерны для обнаружения команд чтения `docs/`, override/escalate/jailbreak, подделки системных сообщений.

### FIX-250: Write scope

`_check_write_scope()` — проверяет, что write-операции по email-задаче идут только в `/outbox/`, блокирует попытки писать в системные пути.

## Связанные концепции

- [[loop]] — использует эти функции в каждом шаге
- [[dispatch]] — `_PROTECTED_WRITE` и `_PROTECTED_PREFIX` — параллельная защита на уровне dispatch
