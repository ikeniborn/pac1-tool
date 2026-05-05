---
wiki_sources:
  - "agent/wiki.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - wiki-graph
  - wiki-memory
aliases:
  - "wiki.py"
  - "run_wiki_lint"
  - "write_fragment"
---

# Wiki Memory (agent/wiki.py)

Персистентное кросс-сессионное хранилище знаний. Двухуровневая структура: `data/wiki/fragments/` (append-only raw writes агентов) → `data/wiki/pages/` (LLM-синтезированные страницы после lint).

## Основные характеристики

### Структура директорий

```
data/wiki/
├── pages/      # LLM-синтез, читается агентом и evaluator
│   ├── email.md, crm.md, lookup.md, temporal.md, inbox.md, ...
└── fragments/  # append-only, один файл на task_id
    ├── errors/, contacts/, accounts/, email/, ...
```

### Lint (LLM-синтез)

`run_wiki_lint` запускается дважды за `make run`: до задач (compile previous runs) и после (compile this run). LLM-синтез категорийных промптов, не дедупликация.

**Graph autobuild (FIX-389, гейт `WIKI_GRAPH_AUTOBUILD=1`):** `_llm_synthesize` просит модель приложить fenced ```json {graph_deltas: ...}``` после markdown-страницы. Парсинг fail-open: невалидный JSON → только markdown. Один `merge_updates/save_graph` в конце lint.

### Fragments

`write_fragment(task_id, category, content)` — append-only write в `fragments/<category>/<task_id>.md`. `task_id` санируется от path-unsafe символов (FIX-N+6).

### Negatives injection (FIX-410, гейт `WIKI_NEGATIVES_ENABLED=1`)

`load_wiki_patterns(task_type, include_negatives=True)` — загружает `pages/<task_type>.md` + error fragments для инжекции "dead-end" паттернов в промпт агента на старте.

### Graph instruction suffix

`_GRAPH_INSTRUCTION_SUFFIX` — суффикс к lint-промптам, требующий fenced JSON с `graph_deltas` (new_insights, new_rules, antipatterns, edges).

## Env-переменные

- `WIKI_GRAPH_AUTOBUILD=1` — autobuild graph при lint
- `WIKI_GRAPH_ERRORS_INGEST=0` — ingest archived errors как antipatterns
- `WIKI_NEGATIVES_ENABLED=1` — инжекция negatives в промпт
- `WIKI_NEGATIVES_MAX_CHARS=800` — лимит символов для negatives

## Связанные концепции

- [[wiki-graph]] — graph.json наполняется из lint через wiki.py
- [[evaluator]] — `load_wiki_patterns` используется для reference_patterns
- [[contract-phase]] — `load_contract_constraints` и `load_refusal_hints` из wiki.py
