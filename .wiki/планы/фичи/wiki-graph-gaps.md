---
wiki_title: "Wiki↔Graph Gaps Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-29-wiki-graph-gaps.md"
wiki_updated: "2026-05-06"
tags: [wiki, graph, integration, feature]
---

# Wiki↔Graph Gaps

**Источник:** `docs/superpowers/plans/2026-04-29-wiki-graph-gaps.md`

## Цель

Закрыть три разрыва wiki↔graph: страницы → граф, рёбра между узлами, ошибки → граф.

## Три разрыва

### 1. Страницы → граф (pages-to-graph)
Синтезированные wiki-страницы не создают узлы в graph.json. Фикс: `run_wiki_lint` после создания/обновления страницы — `add_pattern_node` с контентом страницы.

### 2. Рёбра между узлами (edge wiring)
Узлы графа не имеют рёбер `requires`/`conflicts_with`/`generalizes`. Фикс: LLM-экстрактор в `_llm_synthesize` должен предлагать рёбра в `graph_deltas`.

### 3. Ошибки → граф (error-to-graph)
Провальные прогоны (score=0) не создают `antipattern` узлы. Фикс: в `main.py` при `score=0.0` + `step_facts` содержит ошибки → `add_pattern_node(type='antipattern', ...)`.

**Ключевые файлы:** `agent/wiki.py`, `agent/wiki_graph.py`, `main.py`
