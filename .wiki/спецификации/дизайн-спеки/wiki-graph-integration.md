---
wiki_sources:
  - docs/superpowers/specs/2026-04-29-wiki-graph-gaps-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, wiki, wiki-graph, edges, error-ingest]
---

# Wiki↔Graph Integration Gaps

**Дата:** 2026-04-29

Три разрыва между wiki и графом, три хирургических патча.

## Патч 1: Pages → граф (через lint)

**Добавить** `run_pages_lint(g: Graph, task_type: str)` в `agent/wiki.py`:
- Читает `data/wiki/pages/{task_type}.md`
- Вызывает `_llm_synthesize` только для graph_deltas (без rewrite страницы)
- Узлы получают тег `"wiki_page"`
- `merge_updates(g, deltas)` — стандартный путь

Вызов: `main.py` — сразу после `run_wiki_lint()`. Гейт: `WIKI_GRAPH_AUTOBUILD=1`.

## Патч 2: Рёбра между узлами

### LLM-рёбра

Расширить `_GRAPH_INSTRUCTION_SUFFIX` — добавить поле `edges` в JSON-схему:
```json
"edges": [{"from": "<text>", "rel": "requires|conflicts_with|generalizes|precedes", "to": "<text>"}]
```

LLM ссылается по тексту. `merge_updates` резолвит через `_mk_node_id(text)`. Если узел не найден — ребро пропускается.

### Детерминированные рёбра (post-merge)

Автоматически строить для узлов текущего batch:
- `antipattern → conflicts_with → rule` (если теги пересекаются)
- `pattern → requires → insight` / `pattern → requires → rule` (если теги пересекаются)

## Патч 3: Ошибки → граф (FIX: WIKI_GRAPH_ERRORS_INGEST=1)

`_ingest_error_fragments(g: Graph, category: str)`:
- Читает последние N=10 файлов из `archive/errors/{category}/`
- Парсит структурированные поля **без LLM**: OUTCOME, первые 3 строки STEP FACTS
- Создаёт antipattern-узлы с `confidence=0.4`
- `_upsert`: повторяющийся antipattern получает +0.02 conf при каждом merge

Гейт: `WIKI_GRAPH_ERRORS_INGEST=1`

## Поток данных после изменений

```
run_wiki_lint(category)
  fragments/ → LLM synthesis → graph_deltas (nodes + edges) → merge_updates
  archive/errors/ → _ingest_error_fragments → antipattern nodes → merge_updates

run_pages_lint(task_type)
  pages/{task_type}.md → LLM graph_deltas only → merge_updates

merge_updates(g, deltas)
  _upsert all nodes → resolve LLM edges → build deterministic edges
  _gc_orphan_edges() → save_graph()
```
