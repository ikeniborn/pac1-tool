"""Capture snapshot of graph/wiki state for comparative analysis."""
import json
import os
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "wiki"


def snapshot() -> dict:
    graph_path = DATA / "graph.json"
    g = {}
    if graph_path.exists():
        g = json.loads(graph_path.read_text())

    nodes = g.get("nodes", {})
    edges = g.get("edges", {})
    types = Counter(n.get("type", "?") for n in nodes.values())
    confs = [n.get("confidence", 0.0) for n in nodes.values()]
    uses_list = [n.get("uses", 0) for n in nodes.values()]

    # wiki pages
    pages_dir = DATA / "pages"
    pages = {}
    if pages_dir.exists():
        for p in pages_dir.rglob("*.md"):
            key = str(p.relative_to(pages_dir))
            pages[key] = len(p.read_text().splitlines())

    # fragments
    frags_dir = DATA / "fragments"
    frag_count = 0
    if frags_dir.exists():
        frag_count = sum(1 for _ in frags_dir.rglob("*.md"))

    # dspy programs
    dspy_programs = {}
    for name in ["builder", "evaluator", "classifier"]:
        p = ROOT / "data" / f"{name}_program.json"
        dspy_programs[name] = p.exists()

    dspy_examples = ROOT / "data" / "dspy_examples.jsonl"
    dspy_example_count = 0
    if dspy_examples.exists():
        dspy_example_count = sum(1 for _ in dspy_examples.read_text().splitlines() if _.strip())

    return {
        "graph": {
            "nodes": len(nodes),
            "edges": len(edges),
            "by_type": dict(types),
            "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
            "total_uses": sum(uses_list),
        },
        "wiki": {
            "pages": pages,
            "fragment_count": frag_count,
        },
        "dspy": {
            "programs": dspy_programs,
            "example_count": dspy_example_count,
        },
    }


if __name__ == "__main__":
    s = snapshot()
    print(json.dumps(s, indent=2))
