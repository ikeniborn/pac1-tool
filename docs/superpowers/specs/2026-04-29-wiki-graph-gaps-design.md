# Wiki↔Graph Integration Gaps — Design Spec
Date: 2026-04-29

## Problem

Wiki и граф — два параллельных хранилища знаний. Между ними три разрыва:

1. **Pages → граф:** успешные паттерны в `pages/*.md` видит только evaluator, но не агент при работе.
2. **Рёбра:** граф фактически несвязный — `requires`/`conflicts_with` не строятся ни LLM, ни кодом.
3. **Ошибки → граф:** `archive/errors/` никогда не читается в граф; повторяющиеся ошибки не замечаются.

## Подход: три хирургических патча (Approach A)

Каждый патч независим, гейтится env-переменной, не ломает существующий путь.

---

## Патч 1: Pages → граф (через lint)

**Файл:** `agent/wiki.py`

Добавить функцию `run_pages_lint(g: Graph, task_type: str) -> None`:
- Читает `data/wiki/pages/{task_type}.md`
- Вызывает `_llm_synthesize` с урезанным промптом: **только graph_deltas, без rewrite страницы**
- Полученные узлы получают дополнительный тег `"wiki_page"` для идентификации источника
- Вызывает `merge_updates(g, deltas)` — стандартный путь

**Вызов:** `main.py` — сразу после `run_wiki_lint()`, один раз на lint-сессию.

**Гейт:** `WIKI_GRAPH_AUTOBUILD=1` (существующий, без новой переменной).

**Инвариант:** pages-пасс не перезаписывает страницу — только добавляет узлы в граф.

---

## Патч 2: Рёбра между узлами

**Файл:** `agent/wiki.py` (промпт) + `agent/wiki_graph.py` (merge_updates)

### Слой 1 — LLM-рёбра

Расширить `_GRAPH_INSTRUCTION_SUFFIX` — добавить поле `edges` в JSON-схему:

```json
{
  "graph_deltas": {
    "new_insights": [...],
    "new_rules": [...],
    "antipatterns": [...],
    "edges": [
      {"from": "<text of node A>", "rel": "requires|conflicts_with|generalizes|precedes", "to": "<text of node B>"}
    ]
  }
}
```

LLM ссылается на узлы по тексту (не ID). `merge_updates` резолвит: вычисляет `_mk_node_id(text)` для каждого конца ребра и проверяет наличие в `g.nodes`. Если узел не найден (текст LLM расходится с нормализованным) — ребро пропускается, fail-open. Поэтому LLM-рёбра работают надёжно только внутри одного batch (узлы из того же `graph_deltas`), не по ссылкам на старые узлы.

### Слой 2 — детерминированные рёбра (post-merge)

В `merge_updates`, после upsert всех узлов из batch, автоматически строить:
- `antipattern →conflicts_with→ rule` — если теги пересекаются
- `pattern →requires→ insight` / `pattern →requires→ rule` — если теги пересекаются

Только для узлов **из текущего batch** (не ищем по всему графу — иначе O(n²) и лишний шум). Дубли подавляются через существующий `existing_edges` set.

**Рендеринг:** `_render_top` в `wiki_graph.py` уже показывает рёбра при retrieval — изменений не требуется.

---

## Патч 3: Ошибки → граф

**Файл:** `agent/wiki.py`

Добавить `_ingest_error_fragments(g: Graph, category: str) -> int`:
- Читает последние N=10 файлов из `archive/errors/{category}/` (сортировка по mtime убыванию — новейшие)
- Парсит структурированные поля **без LLM**: `OUTCOME:`, первые 3 строки `STEP FACTS:`
- Создаёт antipattern-узлы с `confidence=0.4` (ниже default 0.6 — слабее, чем синтезированные)
- `_upsert` обеспечивает накопление: повторяющийся antipattern получает +0.02 conf при каждом merge
- Возвращает число добавленных/обновлённых узлов

Вызывается в конце `run_wiki_lint`, после основного синтеза.

**Гейт:** `WIKI_GRAPH_ERRORS_INGEST=1` (новая env-переменная, добавить в `.env.example`).

---

## Компоненты и зависимости

```
wiki.py
  run_pages_lint()           ← новое
  _ingest_error_fragments()  ← новое

wiki_graph.py
  merge_updates()            ← расширить: резолвить LLM-рёбра + строить детерминированные

wiki.py (_GRAPH_INSTRUCTION_SUFFIX)  ← расширить: добавить edges в JSON-схему

main.py                      ← вызов run_pages_lint после run_wiki_lint

.env.example                 ← добавить WIKI_GRAPH_ERRORS_INGEST
```

---

## Поток данных после изменений

```
run_wiki_lint(category)
  fragments/ → LLM synthesis → graph_deltas (nodes + edges) → merge_updates
  archive/errors/ → _ingest_error_fragments → antipattern nodes → merge_updates

run_pages_lint(task_type)         ← новый вызов из main.py
  pages/{task_type}.md → LLM graph_deltas only → merge_updates

merge_updates(g, deltas)
  _upsert all nodes
  resolve LLM edges by text → add to g.edges
  build deterministic edges (antipattern↔rule, pattern↔insight)
  _gc_orphan_edges()
  save_graph()
```

---

## Критерии успеха

1. После lint-сессии `uv run python scripts/print_graph.py --edges` показывает не пустой список рёбер.
2. Узлы с тегом `"wiki_page"` появляются в графе после запуска с существующими страницами.
3. `archive/errors/` с WIKI_GRAPH_ERRORS_INGEST=1 добавляет antipattern-узлы с conf=0.4.
4. Retrieval (`retrieve_relevant`) возвращает связанные узлы через рёбра при рендеринге.

---

## Риски и ограничения

- **LLM-рёбра:** качество зависит от модели. Невалидные рёбра пропускаются — граф не сломается.
- **Pages-пасс:** дополнительный LLM-вызов на lint. Для задач без pages/{task_type}.md — пропускается.
- **Error ingest без LLM:** текстовый парсинг может пропустить нюансы. Низкий confidence (0.4) отражает это.
- **Граф не перестраивается с нуля** — накопленные узлы без рёбер остаются. Рёбра добавляются только при следующем lint.
