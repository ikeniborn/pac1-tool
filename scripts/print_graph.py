"""Inspect the researcher knowledge graph.

Usage:
    uv run python scripts/print_graph.py           # top-20 nodes by confidence
    uv run python scripts/print_graph.py --all     # every node
    uv run python scripts/print_graph.py --tag email
    uv run python scripts/print_graph.py --edges
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.wiki_graph import load_graph  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Print every node")
    ap.add_argument("--tag", type=str, default="", help="Filter by tag")
    ap.add_argument("--edges", action="store_true", help="Also print edges")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    g = load_graph()
    if not g.nodes:
        print("(graph is empty)")
        return

    nodes = list(g.nodes.items())
    if args.tag:
        nodes = [(nid, n) for nid, n in nodes if args.tag in n.get("tags", [])]

    def score(n: dict) -> float:
        return float(n.get("confidence", 0.5)) * (1.0 + math.log(max(1, int(n.get("uses", 1)))))

    nodes.sort(key=lambda kv: -score(kv[1]))
    if not args.all:
        nodes = nodes[: args.top]

    print(f"# Nodes: {len(nodes)} (of {len(g.nodes)} total)")
    for _nid, n in nodes:
        tags = ",".join(n.get("tags", []))
        print(
            f"  [{n.get('type','?'):11}] conf={n.get('confidence',0):.2f} "
            f"uses={n.get('uses',0):3}  tags={tags:30}  {n.get('text','')[:90]}"
        )

    if args.edges:
        print(f"\n# Edges: {len(g.edges)}")
        for e in g.edges:
            print(f"  {e.get('from')} --[{e.get('rel')}]--> {e.get('to')}")


if __name__ == "__main__":
    main()
