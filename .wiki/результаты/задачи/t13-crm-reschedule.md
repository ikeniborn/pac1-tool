---
wiki_title: "t13 — CRM reschedule (перенос follow-up)"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04.md
  - docs/results/run_analysis_2026-05-04_v2.md
  - docs/results/run_analysis_2026-05-04_v3.md
  - docs/results/run_analysis_2026-05-04_v4.md
wiki_domain: результаты
wiki_type: task-analysis
tags: [crm, t13, reschedule, json-mismatch, date-calculation, security-false-positive]
---

# t13 — CRM reschedule (перенос follow-up)

**Тип задачи:** crm  
**Win rate:** 0/25 (0%) в v1–v4

## Формулировка задачи

"Nordlicht Health asked to reconnect in two weeks. Reschedule the follow-up accordingly." Задача не рандомизируется — одна и та же во всех прогонах v1–v3. В v4 VAULT_DATE меняется.

## Паттерн ошибок по версиям

| Версия | Прогон 1 | Прогон 2 | Прогон 3 | Прогон 4 | Прогон 5 |
|--------|---------|---------|---------|---------|---------|
| v1 | UNSUPPORTED | UNSUPPORTED | no answer | CLARIFICATION | CLARIFICATION |
| v2 | UNSUPPORTED | CLARIFICATION | off by 23 дня | off by 1 день | DENIED_SECURITY |
| v3 | off (8–20 дней) | off (8–20 дней) | off (8–20 дней) | off (8–20 дней) | off (8–20 дней) |
| v4 | JSON mismatch | JSON mismatch | no answer | JSON mismatch | no answer |

## Эволюция проблемы

1. **v1 начало**: Агент классифицирует как "calendar/external system" → UNSUPPORTED.
2. **v2 mid**: Агент начинает пытаться выполнить задачу, но вычисляет дату неверно (off by 23, 1 день).
3. **v2 run5**: DENIED_SECURITY — накопленные antipatterns спровоцировали ложную блокировку.
4. **v3**: Устойчивые попытки, но JSON mismatch `next_follow_up_on` — off by 8–20 дней стабильно.
5. **v4**: JSON mismatch на `acct_001.json` — дата записывается, но неверная.

## Корневые причины

1. **Ранние прогоны**: Security gates и classifier ошибочно блокируют — задача кажется запросом на внешний календарь.
2. **v3/v4**: Вычисление "две недели от сегодня" некорректно. Нет явного VAULT_DATE в vault или агент использует неверную базу.
3. **v2 run5 / отдельные прогоны**: Накопленные antipatterns из ошибок в `errors/crm.md` смещают агента в сторону DENY.

## Рекомендации

1. Явная инструкция в `_TASK_BLOCKS['crm']`: reschedule — это запись в vault, не внешний вызов.
2. Проверить security.py write-scope gates: `accounts/acct_001.json` должен разрешён.
3. Минимальный порог confidence для antipatterns в `errors/crm.md` перед попаданием в retrieval.
4. AGENTS.MD должен содержать VAULT_DATE явно для корректного расчёта дат.

## Связи

- [[результаты/задачи/t40-crm-lookup]] — смежная CRM задача
- [[результаты/проблемы/temporal-gap-formula]] — та же проблема расчёта дат
- [[результаты/проблемы/antipattern-poisoning]] — ложные DENIED_SECURITY из antipatterns
- [[результаты/сессии/run-v4-all-tasks]] — v4 baseline
