---
wiki_sources:
  - docs/architecture/07-wiki-memory.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, wiki, wiki-graph, memory, knowledge-accumulation]
---

# Wiki-память и Knowledge Graph

Кросс-сессионная память: per-task фрагменты → LLM-lint в страницы → инъекция в следующие задачи.

## Директории

```
data/wiki/
├── pages/         # скомпилированные LLM-synth страницы
│   ├── default.md
│   ├── errors.md
│   ├── contacts.md
│   ├── accounts.md
│   ├── inbox.md, queue.md, crm.md, ...
├── fragments/     # append-only per-task raw writes
└── archive/       # ротированные фрагменты
```

## Lifecycle фрагмента

1. Задача выполнена → `format_fragment(outcome, task_type, ...)` → list[(content, category)]
2. `write_fragment()` → `fragments/category/T.txt` (append)
3. `run_wiki_lint()` (два раза за run: до и после задач) → aspect-by-aspect synthesis → `pages/category.md`

## Aspect-by-aspect синтез (`_llm_synthesize_v2`)

```
fragments/* + existing page meta → knowledge_aspects из task_types.json
→ для каждого aspect: отдельный add-only LLM-вызов
→ _assemble_page_from_sections → pages/category.md + wiki:meta header
→ graph_deltas (если WIKI_GRAPH_AUTOBUILD=1) → merge_updates → save_graph
```

## Page quality lifecycle

| Уровень | fragment_count | Эффект |
|---|---|---|
| `nascent` | < 5 | `[draft — limited data]` заголовок в prompt |
| `developing` | 5–14 | нормальный инжект |
| `mature` | ≥ 15 | evaluator char limit 4000; граф-узлы получают тег `wiki_mature` |

## Инъекция в prompt

Wiki помещается в `preserve_prefix` (никогда не компактизируется):
- `WikiGraphAgent.read()` → `load_wiki_patterns(task_type)` → inject перед task_text
- Для classifier: `vault_hint` дополняется wiki-страницами → снижает flip inbox/queue

## Knowledge Graph

**Узлы**: `insight`, `rule`, `pattern`, `antipattern` с `{tags, confidence, uses, last_seen}`

**Рёбра**: `requires`, `conflicts_with`, `generalizes`, `precedes`

**Два пути заполнения:**
1. **LLM-extractor** (в run_wiki_lint): `_llm_synthesize` → fenced ` ```json {graph_deltas: ...} ``` ` → merge_updates. Гейт: `WIKI_GRAPH_AUTOBUILD=1`
2. **Confidence feedback** (post-trial в main.py): `score=1.0` → `bump_uses(injected_node_ids)` + `add_pattern_node`; `score=0.0` → `degrade_confidence(epsilon)`. Гейт: `WIKI_GRAPH_FEEDBACK=1`

**Retrieval**: `retrieve_relevant_with_ids(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses).

**Граф читается в трёх точках** (все гейтены `WIKI_GRAPH_ENABLED=1`): system prompt, DSPy addendum (`graph_context` field), evaluator.

## Конфигурация

```bash
WIKI_ENABLED=1
WIKI_LINT_ENABLED=1
WIKI_GRAPH_ENABLED=1
WIKI_GRAPH_TOP_K=5
WIKI_GRAPH_AUTOBUILD=1
WIKI_GRAPH_FEEDBACK=1
WIKI_GRAPH_CONFIDENCE_EPSILON=0.05
WIKI_GRAPH_MIN_CONFIDENCE=0.1
```

## Ключевые файлы

| Файл | Что делает |
|---|---|
| `agent/wiki.py` | `load_wiki_patterns`, `format_fragment`, `write_fragment`, `run_wiki_lint` |
| `agent/wiki_graph.py` | `load_graph`, `retrieve_relevant_with_ids`, `bump_uses`, `degrade_confidence` |
| `agent/agents/wiki_graph_agent.py` | `WikiGraphAgent` — обёртка wiki + wiki_graph |
