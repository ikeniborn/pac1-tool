---
wiki_sources:
  - docs/architecture/05-security-stall.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, security, stall, injection, write-scope]
---

# Безопасность и stall-detection

Два взаимодополняющих слоя защиты loop: injection-pipeline и детектор зацикливаний.

## Security pipeline (5 стадий)

1. **Нормализация** — strip zero-width chars, NFKC, leet (0→o, 1→l, @→a и т.д.)
2. **Injection check** — regex `_INJECTION_RE`: ignore previous / disregard / new task / system prompt
3. **Contamination** — при write в `/outbox/`: vault paths, tree chars (├ └), 'Result of Req_'
4. **Write-scope** — email только в `/outbox/`; `/docs/` и `/AGENTS.MD` блокируются кроме OTP-exception
5. **OTP elevation** — удаление `/docs/channels/otp.txt` как gate для admin-операций

### Inbox-specific patterns

При `task_type=inbox/queue`: дополнительная проверка на `read docs`, `override rules`, `admin elevation`, `credential harvest`.

### Write-payload injection

При write-операции: проверка на embedded commands, conditional execute, auth-bridge claims.

## Stall detection (3 ортогональных сигнала)

| Сигнал | Условие | Действие |
|---|---|---|
| Signal 1 | 3 последних fingerprint одинаковы | hint + retry LLM once |
| Signal 2 | error_counts[tool, path, code] ≥ 2 | hint "list parent" + retry |
| Signal 3a | ≥6 шагов без write/delete/move/mkdir | hint "take action or CLARIFICATION" |
| Signal 3b | ≥12 шагов без action | STALL ESCALATION + force retry (re-fire 12/18/24) |

### Fingerprint

```python
fingerprint = f"{tool}:{path}:{hash(args)}"  # deque max=10
error_key   = (tool, path, error_code)        # Counter
```

## Outcome-коды

| Код | Когда |
|---|---|
| `OUTCOME_DENIED_SECURITY` | injection / contamination / scope |
| `OUTCOME_NONE_CLARIFICATION` | exploration stall без прогресса |
| `OUTCOME_NONE_UNSUPPORTED` | preject (внешний сервис) |

## FIX-метки

| FIX | Что |
|---|---|
| FIX-203 | Нормализация injection-текста |
| FIX-206 | Contamination gate на email writes |
| FIX-215 | Inbox-specific injection-паттерны |
| FIX-250 | Write-scope enforcement (email → только /outbox/) |
| FIX-321 | Write-payload injection detection |
| FIX-323 | Re-fire stall escalation на 12/18/24 шагах |

## Ключевые файлы

| Файл | Функции |
|---|---|
| `agent/security.py` | `_normalize_for_injection`, `_INJECTION_RE`, `_check_write_scope` |
| `agent/stall.py` | `_check_stall`, `_handle_stall_retry` |
