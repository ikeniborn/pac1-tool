---
wiki_sources:
  - "agent/agents/wiki_graph_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - wiki-graph
  - dispatch
aliases:
  - "WikiGraphAgent"
---

# WikiGraphAgent (agent/agents/wiki_graph_agent.py)

Агент чтения и обновления wiki-графа в мультиагентной архитектуре. Объединяет загрузку wiki-паттернов и retrieval из графа знаний в единый контрактный интерфейс.

## Основные характеристики

- **Конструктор:** флаги `wiki_enabled` (default из `WIKI_ENABLED`) и `graph_enabled` (default из `WIKI_GRAPH_ENABLED`).

- **Метод `read(request: WikiReadRequest) → WikiContext`:**
  1. Если wiki включена → `load_wiki_patterns(request.task_type)` → `patterns_text`.
  2. Если граф включен → `load_graph()`, `retrieve_relevant_with_ids(g, task_type, task_text, top_k)` → `graph_section`, `injected_ids`.
  3. Оба пути fail-open при исключениях.
  - Env: `WIKI_GRAPH_TOP_K` (default 5).

- **Метод `write_feedback(request: WikiFeedbackRequest) → None`:**
  - Если `request.score >= 1.0` → `bump_uses(g, node_ids)` на инжектированных узлах.
  - Если `score < 1.0` → `degrade_confidence(g, node_ids, epsilon)`.
  - Сохраняет граф через `save_graph(g)`. Fail-open при исключениях.
  - Env: `WIKI_GRAPH_CONFIDENCE_EPSILON` (default 0.05).

- **Возвращает** `WikiContext`: `patterns_text`, `graph_section`, `injected_node_ids`.

## Связанные концепции

- [[wiki-graph]] — содержит `load_graph`, `retrieve_relevant_with_ids`, `bump_uses`, `degrade_confidence`
- [[wiki-memory]] — `load_wiki_patterns` для текстовых паттернов
- [[orchestrator]] — вызывает WikiGraphAgent для наполнения wiki-контекста
