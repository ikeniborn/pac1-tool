---
wiki_title: "Graph retrieval — смешивание правил между task_type"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04_v2.md
  - docs/results/run_analysis_2026-05-04_v3.md
wiki_domain: результаты
wiki_type: system-problem
tags: [wiki-graph, retrieval, task-type-filter, temporal, lookup, system-problem]
---

# Graph retrieval — смешивание правил между task_type

**Статус:** не решена  
**Приоритет:** ВЫСОКИЙ (v2 рекомендации)

## Симптом

Граф накапливает temporal-правила из задач t41/t42/t43 (temporal reasoning), которые попадают в retrieval для t40 (lookup задача) из-за текстового совпадения.

**Конкретный пример (v2 run4, задача t40 — lookup):**
```
## KNOWLEDGE GRAPH (relevant)
- [rule] For relative time references, ask user to confirm which date...
- [rule] Expand search window ±1-2 days to account for timezone/timestamp...
```
Это temporal-правила, которые не должны попадать в lookup-задачу.

## Причина

`retrieve_relevant()` в `agent/wiki_graph.py` использует scoring = tag_overlap + text-token overlap + confidence × log(uses). Текстовое совпадение ("days", "date") достаточно велико, чтобы temporal-правила побеждали в ранжировании для lookup-задач с похожими токенами.

Нет фильтрации по `task_type` — узлы из temporal попадают в lookup и наоборот.

## Влияние

- Нерелевантные temporal-правила засоряют prefill lookup задач
- Нет явного негативного влияния на score, но снижает SNR (signal-to-noise ratio) в Knowledge Graph секции
- В теории может дезориентировать агента при принятии решений

## Рекомендации

1. Добавить `task_type` фильтр в `retrieve_relevant()`: при задании `task_type` — приоритизировать узлы с тем же тегом task_type.
2. При добавлении узлов в граф — тегировать их `task_type` источника.
3. Soft-фильтр: если узел не имеет тега нужного task_type — понижать score на коэффициент (не исключать полностью, т.к. некоторые правила кросс-типовые).

## Связи

- [[результаты/проблемы/antipattern-poisoning]] — смежная проблема качества retrieval
- [[результаты/задачи/t40-crm-lookup]] — задача, получающая нерелевантные узлы
- [[результаты/сессии/run-v1-v2-v3]] — контекст обнаружения
