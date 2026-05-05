---
wiki_title: "Wiki Big Bang Restructure Implementation Plan"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-04-30-wiki-big-bang-restructure.md"
wiki_updated: "2026-05-06"
tags: [wiki, restructure, pipeline, knowledge, aspects]
---

# Wiki Big Bang Restructure

**Источник:** `docs/superpowers/plans/2026-04-30-wiki-big-bang-restructure.md`

## Цель

Перестроить wiki-pipeline агента: add-only синтез по knowledge_aspects, provenance tracking через fragment_ids, quality lifecycle (nascent/developing/mature).

## Ключевые изменения

### Add-only синтез
Вместо перезаписи страниц — только добавление новых фрагментов. Каждый фрагмент имеет уникальный `fragment_id`.

### Knowledge aspects
Страница разбивается на аспекты: `successful_patterns`, `failure_modes`, `edge_cases`, `security_rules`, `timing_constraints`. Каждый аспект синтезируется отдельно.

### Quality lifecycle
- `nascent` — 1-2 источника, мало data
- `developing` — 3-9 источников
- `mature` — 10+ источников, стабильный контент

### Provenance tracking
`wiki_sources` содержит список `{path, fragment_id, ingested_at}`. При lint — cross-check источники.

## Файлы

- `agent/wiki.py` — перестроить `_llm_synthesize_aspects()`, add-only merge
- `agent/wiki_graph.py` — `fragment_ids` в узлах
- `data/wiki/pages/*.md` — migrate frontmatter схему
