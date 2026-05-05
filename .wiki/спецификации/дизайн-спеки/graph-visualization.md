---
wiki_sources:
  - docs/superpowers/specs/2026-04-29-graph-visualization-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, graph, visualization, fastapi, vis-js]
---

# Graph Visualization

**Дата:** 2026-04-29

Скрипт `scripts/visualize_graph.py` — интерактивная визуализация knowledge graph.

## Stack

- **Backend:** FastAPI + uvicorn (`uv sync --group viz`)
- **Frontend:** vis.js Network (CDN), embedded HTML
- **Data:** `agent/wiki_graph.load_graph()`

## API

```
GET /           → HTML page with vis.js
GET /api/graph  → JSON {nodes, edges}
  ?tag=<str>
  ?type=insight|rule|antipattern|pattern
  ?min_confidence=0.0..1.0
```

## Визуальное кодирование

| Размерность | Маппинг |
|---|---|
| Цвет | insight=#3b82f6, rule=#22c55e, antipattern=#ef4444, pattern=#f59e0b |
| Прозрачность | `0.4 + confidence × 0.6` |
| Радиус | `10 + log(uses + 1) × 8` |
| Tooltip | type, tags, text, confidence, uses, last_seen |

## UI Controls

Type checkboxes, text search, confidence slider, layout buttons (barnesHut/hierarchical/circular), legend.

## Установка

```toml
# pyproject.toml:
[dependency-groups]
viz = ["fastapi>=0.111", "uvicorn>=0.29"]
```

```bash
uv sync --group viz
uv run python scripts/visualize_graph.py
# → browser at http://localhost:8765
```
