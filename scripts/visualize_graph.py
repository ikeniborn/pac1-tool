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
div.vis-tooltip {
  max-width: 280px;
  white-space: normal !important;
  word-break: break-word;
  line-height: 1.6;
  padding: 8px 10px !important;
  background: #161b22 !important;
  border: 1px solid #30363d !important;
  color: #c9d1d9 !important;
  border-radius: 6px !important;
  font-size: 12px !important;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
}
</style>
</head>
<body>
<div id="toolbar">
  <b style="font-size:13px;color:#58a6ff">Knowledge Graph</b>
  <label><input type="checkbox" id="cb-insight" checked> <span style="color:#3b82f6">insight</span></label>
  <label><input type="checkbox" id="cb-rule" checked> <span style="color:#22c55e">rule</span></label>
  <label><input type="checkbox" id="cb-antipattern" checked> <span style="color:#ef4444">antipattern</span></label>
  <label><input type="checkbox" id="cb-pattern" checked> <span style="color:#f59e0b">pattern</span></label>
  <label style="gap:6px">conf&nbsp;&ge; <span id="conf-val">0.0</span>
    <input type="range" id="conf-slider" min="0" max="1" step="0.05" value="0">
  </label>
  <input type="text" id="search" placeholder="&crarr; поиск по тексту&hellip;">
  <label style="gap:6px">repulsion <span id="repulsion-val">8k</span>
    <input type="range" id="repulsion-slider" min="2000" max="30000" step="1000" value="8000" style="width:90px">
  </label>
  <label style="gap:6px">spacing <span id="spacing-val">120</span>
    <input type="range" id="spacing-slider" min="30" max="400" step="10" value="120" style="width:80px">
  </label>
  <button id="btn-physics" class="active" onclick="setLayout('physics')">Physics</button>
  <button id="btn-hierarchical" onclick="setLayout('hierarchical')">Hierarchical</button>
  <button id="btn-circular" onclick="setLayout('circular')">Circular</button>
  <button onclick="resetView()" title="Сбросить вид">&#8635; Reset</button>
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
    const matched = new Set(
      visible
        .filter(n => n.label.toLowerCase().includes(query) || (n.title || '').toLowerCase().includes(query))
        .map(n => n.id)
    );
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
  document.getElementById('stats').textContent = nodes.length + ' узлов · ' + edges.length + ' рёбер';

  const container = document.getElementById('graph');
  const nodeSet = new vis.DataSet(nodes.map(n => {
    const el = document.createElement('div');
    el.innerHTML = n.title || '';
    return { ...n, title: el };
  }));
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

function graphHeight() {
  return (window.innerHeight - document.getElementById('toolbar').offsetHeight) + 'px';
}

function getPhysicsParams() {
  return {
    repulsion: parseInt(document.getElementById('repulsion-slider').value),
    spacing:   parseInt(document.getElementById('spacing-slider').value),
  };
}

function buildOptions() {
  const { repulsion, spacing } = getPhysicsParams();
  const base = {
    nodes: { shape: 'dot', font: { color: '#c9d1d9', size: 11 }, borderWidth: 0 },
    edges: { smooth: { type: 'continuous' } },
    interaction: { hover: true, tooltipDelay: 150, zoomView: true },
    layout: { improvedLayout: false },
    height: graphHeight(),
  };
  if (currentLayout === 'hierarchical') {
    return { ...base,
      layout: { improvedLayout: false, hierarchical: { direction: 'UD', sortMethod: 'directed', levelSeparation: spacing } },
      physics: { enabled: false } };
  }
  if (currentLayout === 'circular') {
    return { ...base, layout: { improvedLayout: false, randomSeed: 42 }, physics: { enabled: false } };
  }
  return { ...base,
    physics: { solver: 'barnesHut', barnesHut: { gravitationalConstant: -repulsion, springLength: spacing } } };
}

function resetView() {
  if (network) network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
}

function setLayout(layout) {
  currentLayout = layout;
  ['physics','hierarchical','circular'].forEach(l => {
    document.getElementById('btn-' + l).classList.toggle('active', l === layout);
  });
  if (layout === 'circular') {
    render();
    if (network) {
      const ids = allNodes.map(n => n.id);
      const r = Math.min(400, ids.length * 12);
      ids.forEach((id, i) => {
        const a = (2 * Math.PI * i) / ids.length;
        network.moveNode(id, Math.cos(a) * r, Math.sin(a) * r);
      });
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
document.getElementById('repulsion-slider').addEventListener('input', e => {
  const v = parseInt(e.target.value);
  document.getElementById('repulsion-val').textContent = v >= 1000 ? Math.round(v/1000) + 'k' : v;
  if (network && currentLayout === 'physics') {
    network.setOptions({ physics: { barnesHut: { gravitationalConstant: -v } } });
  }
});
document.getElementById('spacing-slider').addEventListener('input', e => {
  const v = parseInt(e.target.value);
  document.getElementById('spacing-val').textContent = v;
  if (network && currentLayout === 'physics') {
    network.setOptions({ physics: { barnesHut: { springLength: v } } });
  }
});
document.getElementById('search').addEventListener('input', render);

loadGraph();
</script>
</body>
</html>"""


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
