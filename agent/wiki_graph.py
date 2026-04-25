"""Researcher knowledge graph (FIX-362).

A compact, single-file graph that lets the researcher retrieve relevant
insights/rules/patterns as a focused addendum section rather than dumping the
full wiki page text. Persisted as JSON (tmp+rename for atomicity).

Nodes types:
    insight     — general observation
    rule        — hard constraint
    pattern     — promoted successful trajectory (mirrors pages/<type>.md)
    antipattern — failed approach worth avoiding

Edges:
    requires, conflicts_with, generalizes, precedes

Confidence decays on repeated negative outcomes via degrade_confidence();
nodes below MIN_CONFIDENCE are moved to graph_archive.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

_WIKI_DIR = Path(__file__).parent.parent / "data" / "wiki"
_GRAPH_PATH = _WIKI_DIR / "graph.json"
_ARCHIVE_PATH = _WIKI_DIR / "graph_archive.json"

_MIN_CONFIDENCE = float(os.environ.get("WIKI_GRAPH_MIN_CONFIDENCE", "0.2"))
_DEFAULT_CONFIDENCE = 0.6

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "and", "or", "but", "with",
    "by", "from", "as", "it", "this", "that", "these", "those",
})


@dataclass
class Graph:
    nodes: dict = field(default_factory=dict)  # id → {type, tags, text, confidence, uses, last_seen}
    edges: list = field(default_factory=list)  # [{from, rel, to}]


def _normalize(text: str) -> str:
    """Stop-word-stripped slug for fuzzy dedup."""
    tokens = _NORMALIZE_RE.split(text.lower())
    return " ".join(t for t in tokens if t and t not in _STOP_WORDS)


def _mk_node_id(prefix: str, text: str) -> str:
    digest = hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def hash_trajectory(step_facts: list) -> str:
    """Stable hash of the tool-call sequence for idempotency checks.

    step_facts is a list of objects with .kind and .path attributes (from
    agent.log_compaction); we fold to a canonical 'kind:path' string per step.
    """
    parts: list[str] = []
    for f in step_facts or []:
        kind = getattr(f, "kind", "")
        path = getattr(f, "path", "") or ""
        if kind:
            parts.append(f"{kind}:{path}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


def load_graph() -> Graph:
    if not _GRAPH_PATH.exists():
        return Graph()
    try:
        data = json.loads(_GRAPH_PATH.read_text(encoding="utf-8"))
        return Graph(nodes=data.get("nodes", {}), edges=data.get("edges", []))
    except Exception as e:
        print(f"[wiki-graph] load failed ({e}); starting empty")
        return Graph()


def save_graph(g: Graph) -> None:
    _WIKI_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _GRAPH_PATH.with_suffix(".json.tmp")
    payload = {"nodes": g.nodes, "edges": g.edges}
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_GRAPH_PATH)


def _archive_nodes(node_ids: list[str], nodes: dict) -> None:
    """Move nodes to graph_archive.json. Idempotent append."""
    if not node_ids:
        return
    archived: dict = {}
    if _ARCHIVE_PATH.exists():
        try:
            archived = json.loads(_ARCHIVE_PATH.read_text(encoding="utf-8"))
        except Exception:
            archived = {}
    for nid in node_ids:
        if nid in nodes:
            archived[nid] = nodes.pop(nid)
    _WIKI_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _ARCHIVE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(archived, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_ARCHIVE_PATH)


def merge_updates(g: Graph, updates: dict) -> list[str]:
    """Merge reflector-extracted deltas into the graph.

    updates schema (any key optional):
        {
          "new_insights":  [{"text": str, "tags": [str], "confidence": float}],
          "new_rules":     [{"text": str, "tags": [str]}],
          "antipatterns":  [{"text": str, "tags": [str]}],
          "reused_patterns": [str],   # existing node ids to bump uses
          "edges":         [{"from": str, "rel": str, "to": str}],
        }

    Returns the list of node ids that were touched (new or bumped).
    """
    touched: list[str] = []
    today = time.strftime("%Y-%m-%d")

    def _upsert(kind: str, prefix: str, item: dict) -> str:
        text = (item.get("text") or "").strip()
        if not text:
            return ""
        nid = _mk_node_id(prefix, text)
        tags = item.get("tags") or []
        if nid in g.nodes:
            n = g.nodes[nid]
            n["uses"] = int(n.get("uses", 0)) + 1
            n["last_seen"] = today
            # widen tags
            existing_tags = set(n.get("tags", []))
            existing_tags.update(tags)
            n["tags"] = sorted(existing_tags)
            # confidence reinforcement (bounded)
            conf = float(n.get("confidence", _DEFAULT_CONFIDENCE))
            n["confidence"] = min(1.0, conf + 0.02)
        else:
            g.nodes[nid] = {
                "type": kind,
                "tags": sorted(set(tags)),
                "text": text,
                "confidence": float(item.get("confidence", _DEFAULT_CONFIDENCE)),
                "uses": 1,
                "last_seen": today,
            }
        return nid

    for item in updates.get("new_insights", []) or []:
        nid = _upsert("insight", "n", item)
        if nid:
            touched.append(nid)
    for item in updates.get("new_rules", []) or []:
        nid = _upsert("rule", "r", item)
        if nid:
            touched.append(nid)
    for item in updates.get("antipatterns", []) or []:
        nid = _upsert("antipattern", "a", item)
        if nid:
            touched.append(nid)

    for reused_id in updates.get("reused_patterns", []) or []:
        if reused_id in g.nodes:
            n = g.nodes[reused_id]
            n["uses"] = int(n.get("uses", 0)) + 1
            n["last_seen"] = today
            touched.append(reused_id)

    # Dedup edges: (from, rel, to) triple.
    existing_edges = {(e.get("from"), e.get("rel"), e.get("to")) for e in g.edges}
    for e in updates.get("edges", []) or []:
        key = (e.get("from"), e.get("rel"), e.get("to"))
        if all(key) and key not in existing_edges and key[0] in g.nodes and key[2] in g.nodes:
            g.edges.append({"from": key[0], "rel": key[1], "to": key[2]})
            existing_edges.add(key)

    return touched


def add_pattern_node(
    g: Graph,
    task_type: str,
    task_id: str,
    traj_hash: str,
    trajectory: list[str],
    linked_node_ids: list[str],
) -> str:
    """Register a promoted pattern as a graph node; link it to supporting insights."""
    pid = f"p_{task_type}_{traj_hash}"
    today = time.strftime("%Y-%m-%d")
    if pid in g.nodes:
        n = g.nodes[pid]
        n["uses"] = int(n.get("uses", 0)) + 1
        n["last_seen"] = today
        if task_id not in n.get("task_ids", []):
            n.setdefault("task_ids", []).append(task_id)
    else:
        g.nodes[pid] = {
            "type": "pattern",
            "tags": [task_type],
            "text": f"pattern:{task_type}",
            "trajectory": [
                f"{s.get('tool','?')}({s.get('path','')})" if isinstance(s, dict) else str(s)
                for s in trajectory
            ],
            "task_ids": [task_id],
            "confidence": 0.8,
            "uses": 1,
            "last_seen": today,
        }
    existing_edges = {(e.get("from"), e.get("rel"), e.get("to")) for e in g.edges}
    for nid in linked_node_ids:
        key = (pid, "requires", nid)
        if nid in g.nodes and key not in existing_edges:
            g.edges.append({"from": pid, "rel": "requires", "to": nid})
            existing_edges.add(key)
    return pid


def degrade_confidence(g: Graph, node_ids: list[str], epsilon: float) -> list[str]:
    """Decrease confidence on listed nodes; archive those below MIN_CONFIDENCE.

    Returns the ids that were archived.
    """
    archived: list[str] = []
    for nid in node_ids:
        if nid not in g.nodes:
            continue
        n = g.nodes[nid]
        if n.get("type") == "pattern":
            # patterns decay slower — they represent verified success
            new_conf = float(n.get("confidence", _DEFAULT_CONFIDENCE)) - (epsilon * 0.5)
        else:
            new_conf = float(n.get("confidence", _DEFAULT_CONFIDENCE)) - epsilon
        n["confidence"] = round(new_conf, 4)
        if new_conf < _MIN_CONFIDENCE:
            archived.append(nid)
    if archived:
        _archive_nodes(archived, g.nodes)
        # prune dangling edges
        g.edges[:] = [
            e for e in g.edges
            if e.get("from") in g.nodes and e.get("to") in g.nodes
        ]
    return archived


def retrieve_relevant(
    g: Graph,
    task_type: str,
    task_text: str = "",
    top_k: int = 5,
    min_retrieve_confidence: float = 0.0,
    degraded_this_session: "set[str] | None" = None,
    quarantine_weak_antipatterns: bool = False,
) -> str:
    """Render the top-K most relevant nodes as a Markdown section for addendum injection.

    Scoring: tag overlap + text-token overlap + confidence × log(uses).
    Nothing to show → returns ''.

    FIX-376g: optional quarantine filters (researcher-only opt-in; defaults
    are permissive so normal-mode behaviour is unchanged):
      - min_retrieve_confidence: drop nodes whose confidence is below this
      - degraded_this_session: drop node IDs that were degrade_confidence'd
        during the current trial (avoid re-injecting just-poisoned nodes)
      - quarantine_weak_antipatterns: drop antipatterns with uses<2 AND conf<0.5
    """
    import math

    if not g.nodes:
        return ""

    task_tokens = set(_normalize(task_text).split()) if task_text else set()
    candidates: list[tuple[float, str, dict]] = []
    _quarantined: set[str] = set(degraded_this_session or ())

    for nid, node in g.nodes.items():
        if nid in _quarantined:
            continue
        conf = float(node.get("confidence", _DEFAULT_CONFIDENCE))
        if conf < min_retrieve_confidence:
            continue
        ntype = node.get("type", "node")
        if (
            quarantine_weak_antipatterns
            and ntype == "antipattern"
            and int(node.get("uses", 1)) < 2
            and conf < 0.5
        ):
            continue
        tags = set(node.get("tags", []))
        tag_score = 2.0 if (task_type in tags or "all_types" in tags) else 0.0
        text_tokens = set(_normalize(node.get("text", "")).split())
        overlap = len(task_tokens & text_tokens) * 0.5
        uses = max(1, int(node.get("uses", 1)))
        base = conf * (1.0 + math.log(uses))
        score = tag_score + overlap + base
        if score <= 0:
            continue
        candidates.append((score, nid, node))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: -x[0])
    top = candidates[:top_k]

    lines = ["## KNOWLEDGE GRAPH (relevant)"]
    for score, nid, node in top:
        ntype = node.get("type", "node")
        uses = node.get("uses", 1)
        conf = node.get("confidence", _DEFAULT_CONFIDENCE)
        text = node.get("text", "")
        if ntype == "pattern":
            raw_traj = node.get("trajectory", [])[:8]
            parts: list[str] = []
            for s in raw_traj:
                if isinstance(s, dict):
                    tool = s.get("tool", "?")
                    path = s.get("path", "")
                    parts.append(f"{tool}({path})" if path else str(tool))
                else:
                    parts.append(str(s))
            traj = " → ".join(parts)
            lines.append(f"- [pattern] {traj} (conf={conf:.2f}, uses={uses})")
        elif ntype == "antipattern":
            lines.append(f"- [AVOID] {text} (conf={conf:.2f})")
        else:
            lines.append(f"- [{ntype}] {text} (conf={conf:.2f}, uses={uses})")

    # Attached edges (requires) for patterns in top-k — only list rules/insights.
    top_ids = {nid for _, nid, _ in top}
    for e in g.edges:
        if e.get("from") in top_ids and e.get("rel") == "requires":
            target = g.nodes.get(e.get("to"))
            if target and target.get("type") in ("rule", "insight"):
                lines.append(f"  requires: [{target.get('type')}] {target.get('text', '')}")

    return "\n".join(lines)
