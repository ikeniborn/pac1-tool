"""Purge ложных anti-patterns из knowledge graph и связанных wiki-файлов (FIX-377).

Reflector ошибочно заносит в graph artefakты harness-ошибок (INVALID_ARGUMENT,
seq.json инкременты, OTP, "skipping the actual email" и т.п.) как antipattern'ы
и insight'ы. Этот скрипт:
  1) находит узлы графа, чей text/tags содержит хотя бы один из ключевиков,
  2) перемещает их в graph_archive.json с confidence=0,
  3) удаляет затронутые рёбра,
  4) удаляет блоки `## Successful pattern:` / `## Verified refusal:` из
     `data/wiki/pages/*.md`, если содержимое блока содержит ключевик,
  5) полностью очищает `data/wiki/fragments/research/`.

По умолчанию dry-run; реальные изменения требуют `--apply`.

НЕ запускается автоматически — только ручной вызов.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

DEFAULT_KEYWORDS = [
    "invalid_argument",
    "otp",
    "artifact id",
    "seq.json increment",
    "must populate required fields",
    "skipping the actual email",
    "reporttaskcompletion call rejected",
    "reporttaskcompletion returned error",
    "completion call rejected",
    "answer was already",
]


def _matches(haystack: str, keywords: list[str]) -> bool:
    h = haystack.lower()
    return any(k.lower() in h for k in keywords)


def _node_haystack(node: dict) -> str:
    text = node.get("text", "") or ""
    tags = node.get("tags", []) or []
    return f"{text} {' '.join(tags)}"


def find_candidates(graph: dict, keywords: list[str]) -> list[str]:
    candidates: list[str] = []
    for nid, node in graph.get("nodes", {}).items():
        if _matches(_node_haystack(node), keywords):
            candidates.append(nid)
    return candidates


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def archive_and_remove(graph: dict, archive_path: Path, ids: list[str]) -> int:
    if not ids:
        return 0
    archived = _load_json(archive_path)
    if not isinstance(archived, dict):
        archived = {}
    nodes = graph.setdefault("nodes", {})
    moved = 0
    for nid in ids:
        if nid in nodes:
            n = dict(nodes.pop(nid))
            n["confidence"] = 0
            archived[nid] = n
            moved += 1
    # Drop edges touching removed nodes.
    edges = graph.get("edges", [])
    graph["edges"] = [
        e for e in edges
        if e.get("from") in nodes and e.get("to") in nodes
    ]
    _atomic_write_json(archive_path, archived)
    return moved


def purge_pages(pages_dir: Path, keywords: list[str], apply: bool) -> int:
    """Strip `## Successful pattern:` / `## Verified refusal:` blocks containing keywords.

    Returns count of removed blocks (also in dry-run, where no file is written).
    """
    if not pages_dir.exists():
        return 0
    removed = 0
    block_prefixes = ("## Successful pattern:", "## Verified refusal:")
    for md in sorted(pages_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        i = 0
        n = len(lines)
        file_changed = False
        while i < n:
            line = lines[i]
            stripped = line.lstrip()
            if any(stripped.startswith(p) for p in block_prefixes):
                # Capture block until next "## " or EOF.
                j = i + 1
                while j < n and not lines[j].lstrip().startswith("## "):
                    j += 1
                block = "".join(lines[i:j])
                if _matches(block, keywords):
                    removed += 1
                    file_changed = True
                    print(f"[PAGE] removed block from {md}: {stripped.rstrip()}")
                else:
                    out.extend(lines[i:j])
                i = j
            else:
                out.append(line)
                i += 1
        if apply and file_changed:
            md.write_text("".join(out), encoding="utf-8")
    return removed


def clear_fragments(fragments_dir: Path, apply: bool) -> int:
    """Remove fragments/research/ subtree. Returns count of subdirs that existed."""
    if not fragments_dir.exists():
        return 0
    subdirs = [p for p in fragments_dir.iterdir() if p.is_dir()]
    count = len(subdirs)
    if apply:
        shutil.rmtree(fragments_dir)
    return count


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS)
    p.add_argument("--graph-path", default="data/wiki/graph.json")
    p.add_argument("--archive-path", default="data/wiki/graph_archive.json")
    p.add_argument("--pages-dir", default="data/wiki/pages")
    p.add_argument("--fragments-dir", default="data/wiki/fragments/research")
    p.add_argument("--apply", action="store_true", help="actually write changes (default: dry-run)")
    args = p.parse_args(argv)

    graph_path = Path(args.graph_path)
    archive_path = Path(args.archive_path)
    pages_dir = Path(args.pages_dir)
    fragments_dir = Path(args.fragments_dir)
    keywords = [k.lower() for k in args.keywords]

    graph = _load_json(graph_path)
    if not graph:
        print(f"[error] cannot load graph at {graph_path}", file=sys.stderr)
        return 2

    candidates = find_candidates(graph, keywords)
    print(f"[scan] graph nodes: {len(graph.get('nodes', {}))}, candidates: {len(candidates)}")
    for nid in candidates:
        node = graph["nodes"][nid]
        snippet = (node.get("text", "") or "")[:80].replace("\n", " ")
        print(
            f"[CANDIDATE] node_id={nid} type={node.get('type')} "
            f"conf={node.get('confidence')} uses={node.get('uses')} snippet={snippet!r}"
        )

    if not args.apply:
        # Dry-run still scans pages/fragments to report counts.
        page_blocks = purge_pages(pages_dir, keywords, apply=False)
        frag_dirs = sum(1 for _ in fragments_dir.iterdir()) if fragments_dir.exists() else 0
        print(
            f"[dry-run] purged_nodes={len(candidates)} archived=0 "
            f"pages_blocks_to_remove={page_blocks} fragments_dirs_to_clear={frag_dirs}"
        )
        return 0

    archived_count = archive_and_remove(graph, archive_path, candidates)
    _atomic_write_json(graph_path, graph)
    page_blocks = purge_pages(pages_dir, keywords, apply=True)
    frag_dirs = clear_fragments(fragments_dir, apply=True)
    print(
        f"[apply] purged_nodes={len(candidates)} archived={archived_count} "
        f"pages_blocks_removed={page_blocks} fragments_dirs_cleared={frag_dirs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
