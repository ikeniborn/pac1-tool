"""Pre-flight health check for the researcher knowledge graph (FIX-388).

Read-only inspection of `data/wiki/graph.json`. Reports:
  - orphan edges (from/to references missing nodes)
  - low-confidence nodes (conf < threshold)
  - keyword-contamination hits (reuses scripts/purge_research_contamination.DEFAULT_KEYWORDS)
  - duplicate nodes (same normalized text under different ids)

Exit codes:
  0 — OK (all metrics under threshold)
  1 — WARN (something exceeds soft threshold; benchmark may continue)
  2 — FAIL (contamination ratio > --fail-ratio; block the run)

Wired into `make run` so a contaminated graph blocks a benchmark before tokens burn.
Cleanup itself stays manual — this script never writes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent
_GRAPH = _REPO / "data" / "wiki" / "graph.json"

# Reuse keyword list + matchers from the purge script — it's the source of truth.
_PURGE_PATH = Path(__file__).parent / "purge_research_contamination.py"
_spec = importlib.util.spec_from_file_location("_purge", _PURGE_PATH)
assert _spec and _spec.loader
_purge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_purge)
DEFAULT_KEYWORDS = _purge.DEFAULT_KEYWORDS
_matches = _purge._matches
_node_haystack = _purge._node_haystack


def _load(path: Path) -> dict:
    if not path.exists():
        return {"nodes": {}, "edges": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _orphan_edges(graph: dict) -> list[tuple[str, str, str]]:
    nodes = graph.get("nodes", {})
    out: list[tuple[str, str, str]] = []
    for e in graph.get("edges", []):
        f, r, t = e.get("from"), e.get("rel"), e.get("to")
        if f not in nodes or t not in nodes:
            out.append((f or "?", r or "?", t or "?"))
    return out


def _low_confidence(graph: dict, threshold: float) -> list[str]:
    return [
        nid for nid, n in graph.get("nodes", {}).items()
        if float(n.get("confidence", 1.0)) < threshold
    ]


def _contaminated(graph: dict, keywords: list[str]) -> list[str]:
    return [
        nid for nid, n in graph.get("nodes", {}).items()
        if _matches(_node_haystack(n), keywords)
    ]


def _duplicate_text(graph: dict) -> list[tuple[str, list[str]]]:
    by_text: dict[str, list[str]] = {}
    for nid, n in graph.get("nodes", {}).items():
        key = (n.get("text") or "").strip().lower()
        if not key:
            continue
        by_text.setdefault(key, []).append(nid)
    return [(k, v) for k, v in by_text.items() if len(v) > 1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Researcher graph pre-flight health check.")
    p.add_argument("--graph-path", type=Path, default=_GRAPH)
    p.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS)
    p.add_argument("--conf-threshold", type=float, default=0.2,
                   help="WARN if any node has confidence < this (default: 0.2)")
    p.add_argument("--fail-ratio", type=float, default=0.05,
                   help="FAIL exit if contaminated/total > this (default: 0.05)")
    p.add_argument("--quiet", action="store_true",
                   help="Print only verdict line, no per-issue listing")
    args = p.parse_args(argv)

    graph = _load(args.graph_path)
    total = len(graph.get("nodes", {}))
    orphans = _orphan_edges(graph)
    low_conf = _low_confidence(graph, args.conf_threshold)
    contam = _contaminated(graph, args.keywords)
    dups = _duplicate_text(graph)

    contam_ratio = (len(contam) / total) if total else 0.0
    fail = contam_ratio > args.fail_ratio
    warn = bool(orphans or low_conf or dups) and not fail

    print(f"[graph-health] nodes={total} edges={len(graph.get('edges', []))}")
    print(f"[graph-health] orphan_edges={len(orphans)} low_conf<{args.conf_threshold}={len(low_conf)}"
          f" contaminated={len(contam)} ({contam_ratio:.1%}) duplicates={len(dups)}")

    if not args.quiet:
        if orphans:
            print("[graph-health] orphan edges (first 5):")
            for f, r, t in orphans[:5]:
                print(f"  {f} -[{r}]-> {t}")
        if contam:
            print("[graph-health] contaminated nodes (first 5):")
            for nid in contam[:5]:
                txt = (graph["nodes"][nid].get("text", "") or "")[:80]
                print(f"  {nid}: {txt}")
        if dups:
            print(f"[graph-health] duplicate-text node groups: {len(dups)}")

    if fail:
        print(f"[graph-health] FAIL: contamination {contam_ratio:.1%} > --fail-ratio {args.fail_ratio:.1%}")
        print("[graph-health] run: uv run python scripts/purge_research_contamination.py --apply")
        return 2
    if warn:
        print("[graph-health] WARN: minor issues; consider purge or save_graph() to GC orphans")
        return 1
    print("[graph-health] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
