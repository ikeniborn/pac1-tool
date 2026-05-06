---
wiki_title: "t42 — capture/lookup (статья за N дней назад)"
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
tags: [lookup, temporal, capture, t42, win-rate-zero, date-calculation]
---

# t42 — capture/lookup (статья за N дней назад)

**Тип задачи:** lookup/temporal (distill в некоторых прогонах)  
**Win rate:** 0/25 (0%) в v1–v4

## Формулировка задачи

"Find the article I captured N days ago." — N рандомизируется. Нужно вычислить дату (VAULT_DATE - N дней) и найти файл в `/01_capture/` по этой дате.

## Паттерн ошибок

| Версия | Паттерн ошибки |
|--------|---------------|
| v1 | Стабильно OUTCOME_NONE_CLARIFICATION (все 5 прогонов) |
| v2 run1–2 | no answer (timeout/молчание) |
| v2 run3–4 | OUTCOME_NONE_CLARIFICATION |
| v2 run5 | Нашёл, но неверный файл (2026-02-15 вместо правильного) |
| v3 | 2× CLARIFICATION, 1× CLARIFICATION (ожидался OK), 1× missing ref, 1× no answer |
| v4 | Стабильно CLARIFICATION (все 5 прогонов) |

## Корневая причина

Та же проблема что и t41: агент не умеет корректно вычислить дату `N дней назад` от VAULT_DATE. Когда не может найти статью по вычисленной дате — сдаётся (CLARIFICATION) или молчит.

В v2 run5 частично помогла wiki: агент сделал правильный поиск в `01_capture/influential/`, но ошибся в дате. Прогресс минимальный.

## Что накопилось в Knowledge Graph

К v3/v4 в графе присутствуют 5 узлов типа rule/insight о поиске в `01_capture/influential/`. Граф читается агентом, правило активирует поиск в правильной папке — но дата вычисляется неверно, и агент уходит в CLARIFICATION.

## Рекомендации

1. Явная инструкция в системном промпте: при отсутствии статьи за N дней назад — возвращать OUTCOME_NONE_CLARIFICATION, не молчать.
2. Исправить temporal reasoning (та же проблема что t41).
3. Усилить инструкцию builder prompt: "искать в `01_capture/`, вычислить дату как VAULT_DATE - N".

## Связи

- [[результаты/задачи/t41-temporal]] — та же корневая проблема
- [[результаты/проблемы/temporal-gap-formula]] — баг в расчёте даты
- [[результаты/сессии/run-v1-v2-v3]] — история прогонов
