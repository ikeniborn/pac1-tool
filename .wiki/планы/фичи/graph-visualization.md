---
wiki_title: "Graph Visualization Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-29-graph-visualization.md"
wiki_updated: "2026-05-06"
tags: [graph, visualization, fastapi, vis-js]
---

# Graph Visualization

**Источник:** `docs/superpowers/plans/2026-04-29-graph-visualization.md`

## Цель

Добавить `scripts/visualize_graph.py` — интерактивная визуализация knowledge graph через FastAPI + vis.js, запускается командой `uv run python scripts/visualize_graph.py`.

## Реализация

- FastAPI сервер на `localhost:8080`
- vis.js Network для рендеринга узлов/рёбер
- Цветовое кодирование по типу узла (`insight`, `rule`, `pattern`, `antipattern`)
- Размер узла пропорционален `uses`
- Tooltip: `confidence`, `tags`, `last_seen`
- Фильтрация по тегам через UI

**Ключевые файлы:**
- `scripts/visualize_graph.py` — FastAPI server + HTML template
- `data/wiki/graph.json` — источник данных (read-only)
