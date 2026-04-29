# Graph Visualization — Design Spec

**Date:** 2026-04-29  
**Status:** Approved

## Goal

Script `scripts/visualize_graph.py` — interactive visualization of the knowledge graph (`data/wiki/graph.json`).  
Launch: `uv run python scripts/visualize_graph.py` → browser at `http://localhost:8765`.

## Stack

- **Backend:** FastAPI + uvicorn (new optional dependency group `viz` in `pyproject.toml`)
- **Frontend:** vis.js Network (CDN), embedded HTML served from Python
- **Data source:** `agent/wiki_graph.load_graph()` — reuses existing loader

## Architecture

Single file `scripts/visualize_graph.py`:

```
FastAPI app
  GET /           → HTML page with vis.js
  GET /api/graph  → JSON {nodes, edges}
    params: ?tag=<str>, ?type=<str>, ?min_confidence=<float>

uvicorn.run(host="0.0.0.0", port=8765, reload=False)
```

On startup the script opens `http://localhost:8765` in the default browser automatically.

## API: GET /api/graph

Query parameters (all optional):
- `tag` — filter nodes where tag is in node's tags list
- `type` — filter by node type (`insight|rule|antipattern|pattern`)
- `min_confidence` — exclude nodes below this confidence threshold (float 0–1)

Response shape:
```json
{
  "nodes": [{"id": "n_abc", "label": "...", "title": "<tooltip html>",
             "color": {"background": "#3b82f6", "border": "#2563eb"},
             "size": 18, "opacity": 0.82}],
  "edges": [{"from": "p_xyz", "to": "n_abc", "label": "requires"}]
}
```

## Visual Encoding

| Dimension | Mapping |
|-----------|---------|
| Node color | Type: insight=#3b82f6, rule=#22c55e, antipattern=#ef4444, pattern=#f59e0b |
| Node opacity | `0.4 + confidence × 0.6` |
| Node radius | `10 + log(uses + 1) × 8` |
| Hover tooltip | type, tags, text, confidence, uses, last_seen |
| Edge | directed arrow, label="requires", thin grey |

## UI Controls

- **Type checkboxes** — show/hide insight / rule / antipattern / pattern independently
- **Text search** — live filter: highlights matching nodes, dims others
- **Confidence slider** — hides nodes below threshold (0.0–1.0)
- **Layout buttons** — barnesHut/physics (default) / hierarchical / circular
- **Legend** — color key in corner
- **Drag nodes** — vis.js built-in
- **Zoom/pan** — mouse wheel + drag background

## Dependencies

Add to `pyproject.toml` as optional group:
```toml
[dependency-groups]
viz = ["fastapi>=0.111", "uvicorn>=0.29"]
```

Install: `uv sync --group viz`

## File Layout

```
scripts/
  visualize_graph.py   ← new file (single file, ~250 LOC)
```

No new directories. No changes to existing files except `pyproject.toml`.
