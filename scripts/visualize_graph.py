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
