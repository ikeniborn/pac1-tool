---
wiki_sources:
  - "agent/wiki_graph.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - wiki-graph
aliases:
  - "knowledge graph"
  - "retrieve_relevant"
  - "wiki_graph.py"
---

# Wiki Graph (agent/wiki_graph.py)

Компактный граф знаний для retrieval релевантных инсайтов/правил/паттернов как focused addendum вместо полного wiki-текста. Персистируется как JSON с атомарным write (tmp+rename). FIX-362.

## Основные характеристики

### Типы узлов

| Тип | Назначение |
|-----|-----------|
| `insight` | Общее наблюдение |
| `rule` | Жёсткое ограничение |
| `pattern` | Успешная траектория (зеркалит `pages/<type>.md`) |
| `antipattern` | Неудачный подход, которого надо избегать |

Узлы имеют поля: `tags`, `confidence`, `uses`, `last_seen`.

### Типы рёбер

`requires`, `conflicts_with`, `generalizes`, `precedes`

### Retrieval

`retrieve_relevant(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses). Stub: `retrieve_relevant_with_ids()` дополнительно возвращает list injected_node_ids для post-trial reinforcement.

### Confidence feedback

- **Позитивный** (score=1.0): `bump_uses` на injected nodes + `add_pattern_node` от `step_facts`
- **Негативный** (score=0.0): `degrade_confidence(epsilon)` на injected nodes
- Узлы ниже `WIKI_GRAPH_MIN_CONFIDENCE` → `graph_archive.json`

### Наполнение графа (два пути, FIX-389)

1. **LLM-extractor** в `run_wiki_lint`: `_llm_synthesize` возвращает markdown + fenced JSON с `graph_deltas`; один `merge_updates/save_graph` в конце lint. Гейт: `WIKI_GRAPH_AUTOBUILD=1`
2. **Pattern-extractor** в `main.py` после `end_trial()`. Гейт: `WIKI_GRAPH_FEEDBACK=1`

### Stemmer (Block G)

Встроенный tiny suffix-stripper (не Porter): убирает `-e` перед суффиксом, затем суффикс, коллапсирует doubled-consonant. Применяется в text-token overlap при scoring.

## Env-переменные

- `WIKI_GRAPH_ENABLED` — read-side gate (для всех трёх мест инжекции)
- `WIKI_GRAPH_TOP_K` — кол-во узлов для retrieval
- `WIKI_GRAPH_MIN_CONFIDENCE` (default 0.2) — порог архивации
- `WIKI_GRAPH_CONFIDENCE_EPSILON` — decay на негативном feedback
- `WIKI_GRAPH_AUTOBUILD=1` — автонаполнение из lint
- `WIKI_GRAPH_FEEDBACK=1` — feedback после end_trial

## Связанные концепции

- [[evaluator]] — graph инжектируется как `graph_insights` InputField (FIX-367)
- [[prompt-builder]] — graph инжектируется как `graph_context` InputField (FIX-389)
- [[wiki-memory]] — wiki pages как источник для graph autobuild
- [[orchestrator]] — `stats["graph_injected_node_ids"]` передаётся в main.py для feedback
