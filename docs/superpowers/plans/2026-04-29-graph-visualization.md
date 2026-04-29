# Graph Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `scripts/visualize_graph.py` — интерактивная визуализация knowledge graph через FastAPI + vis.js, запускается командой `uv run python scripts/visualize_graph.py`.

**Architecture:** Один Python-файл поднимает FastAPI-сервер на порту 8765. `GET /` отдаёт встроенную HTML-страницу с vis.js. `GET /api/graph` возвращает отфильтрованный граф в формате vis.js. Узлы: цвет по типу, opacity по confidence, размер по uses.

**Tech Stack:** FastAPI, uvicorn, vis.js Network (CDN), Python stdlib `math`, `webbrowser`. Тесты через `fastapi[testclient]` (httpx уже в зависимостях).

---

## File Layout

```
scripts/
  visualize_graph.py       ← NEW: весь сервер + встроенный HTML (~280 LOC)
tests/
  test_visualize_graph.py  ← NEW: тесты API-эндпоинтов
pyproject.toml             ← MODIFY: добавить dependency-groups.viz
```

---

### Task 1: Добавить зависимости viz в pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Добавить dependency group**

В `pyproject.toml` после секции `[dependency-groups]` дописать:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.3",
]
viz = [
    "fastapi>=0.111",
    "uvicorn>=0.29",
]
```

- [ ] **Step 2: Синхронизировать зависимости**

```bash
uv sync --group viz
```

Ожидаемый вывод: установка fastapi и uvicorn без ошибок.

- [ ] **Step 3: Проверить что fastapi импортируется**

```bash
uv run python -c "import fastapi; import uvicorn; print('OK')"
```

Ожидаемый вывод: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add viz dependency group (fastapi, uvicorn)"
```

---

### Task 2: API-слой — `/api/graph` с фильтрами

**Files:**
- Create: `scripts/visualize_graph.py`
- Create: `tests/test_visualize_graph.py`

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_visualize_graph.py`:

```python
"""Tests for scripts/visualize_graph.py API endpoints."""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client with a fake graph of 4 nodes covering all types."""
    import visualize_graph as vg

    fake_graph = vg.Graph(
        nodes={
            "n_ins1": {"type": "insight", "tags": ["email"], "text": "Insight one",
                       "confidence": 0.9, "uses": 5, "last_seen": "2026-04-29"},
            "r_rule1": {"type": "rule", "tags": ["email", "workflow"], "text": "Rule one",
                        "confidence": 0.6, "uses": 1, "last_seen": "2026-04-29"},
            "a_anti1": {"type": "antipattern", "tags": ["crm"], "text": "Antipattern one",
                        "confidence": 0.4, "uses": 2, "last_seen": "2026-04-29"},
            "p_pat1": {"type": "pattern", "tags": ["email"], "text": "Pattern one",
                       "confidence": 0.8, "uses": 3, "last_seen": "2026-04-29"},
        },
        edges=[{"from": "p_pat1", "rel": "requires", "to": "n_ins1"}],
    )
    monkeypatch.setattr(vg, "load_graph", lambda: fake_graph)
    return TestClient(vg.app)


def test_get_graph_returns_all_nodes(client):
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 4
    assert len(data["edges"]) == 1


def test_filter_by_tag(client):
    resp = client.get("/api/graph?tag=email")
    data = resp.json()
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"n_ins1", "r_rule1", "p_pat1"}


def test_filter_by_type(client):
    resp = client.get("/api/graph?type=rule")
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "r_rule1"


def test_filter_by_min_confidence(client):
    resp = client.get("/api/graph?min_confidence=0.7")
    data = resp.json()
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"n_ins1", "p_pat1"}


def test_edges_filtered_to_visible_nodes(client):
    # только antipattern виден, но edge идёт от pattern к insight — оба скрыты
    resp = client.get("/api/graph?type=antipattern")
    data = resp.json()
    assert len(data["edges"]) == 0


def test_node_size_formula(client):
    resp = client.get("/api/graph?type=insight")
    data = resp.json()
    node = data["nodes"][0]
    expected = round(10 + math.log(5 + 1) * 8, 4)
    assert abs(node["size"] - expected) < 0.01


def test_node_opacity_formula(client):
    resp = client.get("/api/graph?type=insight")
    data = resp.json()
    node = data["nodes"][0]
    expected = round(0.4 + 0.9 * 0.6, 4)
    assert abs(node["opacity"] - expected) < 0.01


def test_node_color_by_type(client):
    resp = client.get("/api/graph")
    data = resp.json()
    colors = {n["id"]: n["color"]["background"] for n in data["nodes"]}
    assert colors["n_ins1"] == "#3b82f6"
    assert colors["r_rule1"] == "#22c55e"
    assert colors["a_anti1"] == "#ef4444"
    assert colors["p_pat1"] == "#f59e0b"


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "vis-network" in resp.text
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_visualize_graph.py -v 2>&1 | head -20
```

Ожидаемый вывод: `ModuleNotFoundError: No module named 'visualize_graph'`

- [ ] **Step 3: Создать `scripts/visualize_graph.py` с API-слоем**

```python
"""Interactive knowledge graph visualizer.

Usage:
    uv run python scripts/visualize_graph.py [--port 8765] [--no-browser]
"""
from __future__ import annotations

import argparse
import math
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.wiki_graph import Graph, load_graph  # noqa: E402

app = FastAPI(title="Graph Visualizer")

TYPE_COLORS: dict[str, str] = {
    "insight": "#3b82f6",
    "rule": "#22c55e",
    "antipattern": "#ef4444",
    "pattern": "#f59e0b",
}
_DEFAULT_COLOR = "#888888"


def _node_size(uses: int) -> float:
    return 10 + math.log(max(uses, 0) + 1) * 8


def _node_opacity(confidence: float) -> float:
    return round(0.4 + max(0.0, min(1.0, confidence)) * 0.6, 4)


def _build_tooltip(nid: str, n: dict) -> str:
    tags = ", ".join(n.get("tags", [])) or "—"
    return (
        f"<b>{n.get('type', '?')}</b><br>"
        f"<small>{tags}</small><br>"
        f"{n.get('text', nid)}<br>"
        f"conf: {float(n.get('confidence', 0)):.2f} &nbsp; "
        f"uses: {int(n.get('uses', 0))} &nbsp; {n.get('last_seen', '')}"
    )


@app.get("/api/graph")
def get_graph(
    tag: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
):
    g = load_graph()
    nodes = []
    for nid, n in g.nodes.items():
        if tag and tag not in n.get("tags", []):
            continue
        if type and n.get("type") != type:
            continue
        conf = float(n.get("confidence", 0.6))
        if min_confidence is not None and conf < min_confidence:
            continue
        uses = int(n.get("uses", 1))
        color = TYPE_COLORS.get(n.get("type", ""), _DEFAULT_COLOR)
        nodes.append({
            "id": nid,
            "label": n.get("text", nid)[:45],
            "title": _build_tooltip(nid, n),
            "color": {"background": color, "border": color},
            "size": round(_node_size(uses), 4),
            "opacity": _node_opacity(conf),
        })

    visible_ids = {nd["id"] for nd in nodes}
    edges = [
        {"from": e["from"], "to": e["to"], "label": e.get("rel", "")}
        for e in g.edges
        if e.get("from") in visible_ids and e.get("to") in visible_ids
    ]
    return {"nodes": nodes, "edges": edges}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(_HTML)


_HTML = ""  # заглушка — заполним в Task 3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if not args.no_browser:
        webbrowser.open(f"http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Запустить тесты — все кроме `test_root_returns_html` должны пройти**

```bash
uv run pytest tests/test_visualize_graph.py -v -k "not test_root_returns_html"
```

Ожидаемый вывод: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/visualize_graph.py tests/test_visualize_graph.py
git commit -m "feat(viz): add FastAPI graph server with /api/graph endpoint and filters"
```

---

### Task 3: Встроенный HTML с vis.js

**Files:**
- Modify: `scripts/visualize_graph.py` — заменить `_HTML = ""` на полный HTML

- [ ] **Step 1: Заменить заглушку `_HTML` на полный HTML**

В `scripts/visualize_graph.py` найти строку `_HTML = ""` и заменить на:

```python
_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Knowledge Graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; height: 100vh; display: flex; flex-direction: column; }
#toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 10px 16px; background: #161b22; border-bottom: 1px solid #30363d; flex-shrink: 0; }
#toolbar label { font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 4px; }
#toolbar input[type=range] { width: 120px; accent-color: #58a6ff; }
#toolbar input[type=text] { background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; border-radius: 4px; padding: 4px 8px; font-size: 13px; width: 160px; }
#toolbar button { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; border-radius: 4px; padding: 4px 10px; font-size: 12px; cursor: pointer; }
#toolbar button:hover { background: #30363d; }
#toolbar button.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
#graph { flex: 1; }
#legend { position: absolute; bottom: 16px; right: 16px; background: #161b22cc; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; font-size: 12px; line-height: 1.8; }
#legend span { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
#stats { font-size: 12px; color: #8b949e; margin-left: auto; }
</style>
</head>
<body>
<div id="toolbar">
  <b style="font-size:13px;color:#58a6ff">Knowledge Graph</b>
  <label><input type="checkbox" id="cb-insight" checked> <span style="color:#3b82f6">insight</span></label>
  <label><input type="checkbox" id="cb-rule" checked> <span style="color:#22c55e">rule</span></label>
  <label><input type="checkbox" id="cb-antipattern" checked> <span style="color:#ef4444">antipattern</span></label>
  <label><input type="checkbox" id="cb-pattern" checked> <span style="color:#f59e0b">pattern</span></label>
  <label style="gap:6px">conf&nbsp;≥ <span id="conf-val">0.0</span>
    <input type="range" id="conf-slider" min="0" max="1" step="0.05" value="0">
  </label>
  <input type="text" id="search" placeholder="Поиск по тексту…">
  <button id="btn-physics" class="active" onclick="setLayout('physics')">Physics</button>
  <button id="btn-hierarchical" onclick="setLayout('hierarchical')">Hierarchical</button>
  <button id="btn-circular" onclick="setLayout('circular')">Circular</button>
  <span id="stats"></span>
</div>
<div id="graph"></div>
<div id="legend">
  <div><span style="background:#3b82f6"></span>insight</div>
  <div><span style="background:#22c55e"></span>rule</div>
  <div><span style="background:#ef4444"></span>antipattern</div>
  <div><span style="background:#f59e0b"></span>pattern</div>
  <div style="margin-top:6px;color:#8b949e;font-size:11px">размер = uses &nbsp; яркость = confidence</div>
</div>

<script>
let network = null;
let allNodes = [], allEdges = [];
let currentLayout = 'physics';

async function loadGraph() {
  const tag = new URLSearchParams(window.location.search).get('tag') || '';
  const url = '/api/graph' + (tag ? '?tag=' + encodeURIComponent(tag) : '');
  const resp = await fetch(url);
  const data = await resp.json();
  allNodes = data.nodes;
  allEdges = data.edges;
  render();
}

function getFilters() {
  const types = ['insight','rule','antipattern','pattern']
    .filter(t => document.getElementById('cb-' + t).checked);
  const minConf = parseFloat(document.getElementById('conf-slider').value);
  const query = document.getElementById('search').value.toLowerCase().trim();
  return { types, minConf, query };
}

function applyFilters(nodes, edges, { types, minConf, query }) {
  let visible = nodes.filter(n => {
    const type = (n.color.background === '#3b82f6' ? 'insight'
                : n.color.background === '#22c55e' ? 'rule'
                : n.color.background === '#ef4444' ? 'antipattern'
                : 'pattern');
    if (!types.includes(type)) return false;
    if (n.opacity < (0.4 + minConf * 0.6 - 0.001)) return false;
    return true;
  });

  if (query) {
    const matched = new Set(visible.filter(n => n.label.toLowerCase().includes(query) || (n.title || '').toLowerCase().includes(query)).map(n => n.id));
    visible = visible.map(n => ({
      ...n,
      color: matched.has(n.id) ? n.color : { background: '#2d333b', border: '#444c56' },
      opacity: matched.has(n.id) ? n.opacity : 0.15,
    }));
  }

  const visibleIds = new Set(visible.map(n => n.id));
  const visibleEdges = edges.filter(e => visibleIds.has(e.from) && visibleIds.has(e.to));
  return { nodes: visible, edges: visibleEdges };
}

function render() {
  const { nodes, edges } = applyFilters(allNodes, allEdges, getFilters());
  document.getElementById('stats').textContent = `${nodes.length} узлов · ${edges.length} рёбер`;

  const container = document.getElementById('graph');
  const nodeSet = new vis.DataSet(nodes);
  const edgeSet = new vis.DataSet(edges.map(e => ({
    ...e, arrows: 'to', color: { color: '#444c56' }, font: { color: '#8b949e', size: 10 }
  })));

  const options = buildOptions();
  if (network) {
    network.setData({ nodes: nodeSet, edges: edgeSet });
    network.setOptions(options);
  } else {
    network = new vis.Network(container, { nodes: nodeSet, edges: edgeSet }, options);
  }
}

function buildOptions() {
  const base = {
    nodes: { shape: 'dot', font: { color: '#c9d1d9', size: 11 }, borderWidth: 0 },
    edges: { smooth: { type: 'continuous' } },
    interaction: { hover: true, tooltipDelay: 150, zoomView: true },
    height: '100%',
  };
  if (currentLayout === 'hierarchical') {
    return { ...base, layout: { hierarchical: { direction: 'UD', sortMethod: 'directed', levelSeparation: 120 } }, physics: { enabled: false } };
  }
  if (currentLayout === 'circular') {
    return { ...base, layout: { randomSeed: 42 }, physics: { enabled: false },
      configure: { enabled: false } };
  }
  return { ...base, physics: { solver: 'barnesHut', barnesHut: { gravitationalConstant: -8000, springLength: 120 } } };
}

function setLayout(layout) {
  currentLayout = layout;
  ['physics','hierarchical','circular'].forEach(l => {
    document.getElementById('btn-' + l).classList.toggle('active', l === layout);
  });
  if (layout === 'circular') {
    // arrange in circle manually after disable physics
    render();
    if (network) {
      const ids = allNodes.map(n => n.id);
      const r = Math.min(400, ids.length * 12);
      const positions = {};
      ids.forEach((id, i) => {
        const a = (2 * Math.PI * i) / ids.length;
        positions[id] = { x: Math.cos(a) * r, y: Math.sin(a) * r };
      });
      network.setOptions({ physics: { enabled: false } });
      network.moveNode && ids.forEach(id => network.moveNode(id, positions[id].x, positions[id].y));
    }
  } else {
    render();
  }
}

['cb-insight','cb-rule','cb-antipattern','cb-pattern'].forEach(id =>
  document.getElementById(id).addEventListener('change', render)
);
document.getElementById('conf-slider').addEventListener('input', e => {
  document.getElementById('conf-val').textContent = parseFloat(e.target.value).toFixed(2);
  render();
});
document.getElementById('search').addEventListener('input', render);

loadGraph();
</script>
</body>
</html>"""
```

- [ ] **Step 2: Запустить все тесты включая `test_root_returns_html`**

```bash
uv run pytest tests/test_visualize_graph.py -v
```

Ожидаемый вывод: 9 PASSED

- [ ] **Step 3: Commit**

```bash
git add scripts/visualize_graph.py
git commit -m "feat(viz): embed vis.js HTML with type filters, confidence slider, layout switcher"
```

---

### Task 4: Smoke-тест живого сервера

**Files:**
- No file changes — только проверка что сервер стартует

- [ ] **Step 1: Запустить сервер в фоне, проверить `/api/graph`**

```bash
uv run python scripts/visualize_graph.py --no-browser --port 8765 &
sleep 2
curl -s http://localhost:8765/api/graph | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'nodes={len(d[\"nodes\"])} edges={len(d[\"edges\"])}')"
kill %1
```

Ожидаемый вывод: `nodes=198 edges=130` (или близко к тому)

- [ ] **Step 2: Запустить финальный тест-сьют**

```bash
uv run pytest tests/test_visualize_graph.py -v
```

Ожидаемый вывод: 9 PASSED, 0 failed

- [ ] **Step 3: Проверить что существующие тесты не сломались**

```bash
uv run pytest tests/ -x -q --ignore=tests/regression 2>&1 | tail -5
```

Ожидаемый вывод: все тесты проходят, нет новых failures.

- [ ] **Step 4: Финальный commit**

```bash
git add .
git commit -m "feat(viz): add graph visualization script (scripts/visualize_graph.py)"
```
