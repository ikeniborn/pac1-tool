---
wiki_title: "Antipattern poisoning — накопление ложных DENY-сигналов"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04.md
  - docs/results/run_analysis_2026-05-04_v2.md
wiki_domain: результаты
wiki_type: system-problem
tags: [wiki-graph, antipattern, denied-security, false-positive, poisoning, system-problem]
---

# Antipattern poisoning — накопление ложных DENY-сигналов

**Статус:** частично решена (Block A в v5 — anti-poisoning ingest filter)  
**Приоритет:** ВЫСОКИЙ (v2 рекомендации)

## Симптом

В v1: узел `a_b30500141e` — `"text": "OUTCOME_FAIL"`, conf=1.0, uses=42. Агрегированный счётчик неудач занимает топ по uses, не несёт полезного сигнала.

В v2 run5: два неожиданных `OUTCOME_DENIED_SECURITY` на стандартных задачах (t13 и t43). Гипотеза: antipatterns из `errors/crm.md` накопили DENY-сигнал → агент интерпретировал как сигнал блокировки.

## Механизм

1. Агент получает CLARIFICATION/FAIL outcome → error ingest создаёт antipattern-узел
2. Antipattern попадает в retrieval через граф
3. Агент видит antipattern с высоким confidence → интерпретирует как "не делай это"
4. Если antipattern слишком общий (OUTCOME_FAIL, CLARIFICATION) — агент блокирует нормальные задачи

## Решение в v5 (Block A)

- `agent/postrun.py`: pattern-node ingest гейчен `outcome=OUTCOME_OK`
- `agent/wiki.py:format_fragment`: refusal-фрагменты роутятся в `refusals/<type>`, не в `<type>`
- Результат: OUTCOME_NONE_CLARIFICATION больше не попадает в success-pages и не создаёт поддельных pattern-узлов

## Оставшиеся проблемы

- `WIKI_GRAPH_MIN_CONFIDENCE` для antipatterns должен быть > 0.3 (v2 рекомендация: выше порог)
- Конфигурация Block D: epsilon 0.05→0.15, min_confidence 0.2→0.4 снижает влияние низкоуверенных узлов
- Предсуществующие poison-узлы (до Block A) остаются в графе — нужна разовая очистка

## Связи

- [[результаты/проблемы/graph-retrieval-mixing]] — смежная проблема retrieval
- [[результаты/фиксы/blocks-a-g-quality]] — Block A решает эту проблему
- [[результаты/задачи/t13-crm-reschedule]] — DENIED_SECURITY из-за antipatterns
- [[результаты/задачи/t43-lookup-temporal]] — DENIED_SECURITY из-за antipatterns
