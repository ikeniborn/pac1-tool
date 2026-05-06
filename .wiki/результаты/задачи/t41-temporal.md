---
wiki_title: "t41 — temporal (дата через N дней)"
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
tags: [temporal, t41, win-rate-zero, date-calculation, vault-date]
---

# t41 — temporal (дата через N дней)

**Тип задачи:** temporal  
**Win rate:** 0/25 (0%) в v1–v4 (20 прогонов)

## Формулировка задачи

"Какая дата будет через N дней?" — N рандомизируется каждый прогон. VAULT_DATE тоже меняется.

## Паттерн ошибок

Все прогоны: **неверная дата**. В одном прогоне (v2 run5, v4 run2/5): `no answer provided`.

| Версия | Ожидаемые даты | Результат |
|--------|---------------|-----------|
| v1 | 19-03, 08-03, 04-01, 25-03, 26-03 | 0/5 |
| v2 | 24-03-2026, 2026-04-11, 2026-03-28, 2026-04-10, — | 0/5 |
| v3 | 2026-03-12, 2026-03-21, 2026-03-29, 2026-03-08, 24-03-2026 | 0/5 |
| v4 run1–5 | 2026-04-03, no answer, 03-04-2026, no answer, 27-03-2026 | 0/5 |

## Корневая причина

FIX-357 gap formula: агент берёт VAULT_DATE и добавляет фиксированный offset (+5 дней) → получает неверный ESTIMATED_TODAY. N (число дней в задаче) не совпадает с offset. Vault перегенерируется каждый прогон — нет единой стабильной VAULT_DATE.

**Это баг в коде, не в промпте.** Накопленные правила в Knowledge Graph не помогают — ошибка в логике вычисления базовой даты.

## Что пробовали

- Граф накопил temporal-правила (`expand search ±1-2 days`) — не помогло, ошибка в базовой дате.
- Wiki temporal.md развивалась до mature — evaluator читает, но outcome не меняется.

## Рекомендации

1. Исправить gap formula: не добавлять фиксированный offset к VAULT_DATE.
2. Проверять несколько источников в vault для определения базовой даты.
3. Если VAULT_DATE не найден в vault — явно запрашивать у пользователя.

## Связи

- [[результаты/задачи/t42-capture-lookup]] — та же проблема temporal reasoning
- [[результаты/проблемы/temporal-gap-formula]] — системная проблема расчёта даты
- [[результаты/сессии/run-v1-v2-v3]] — история прогонов
