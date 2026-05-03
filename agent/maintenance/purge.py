from __future__ import annotations
import json
import logging
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from agent.maintenance.health import DEFAULT_KEYWORDS

log = logging.getLogger(__name__)


@dataclass
class PurgeResult:
    removed_node_ids: list[str] = field(default_factory=list)
    purged_page_blocks: int = 0
    cleared_fragments: int = 0
    deduped_count: int = 0
    applied: bool = False


def run_purge(
    graph_path: Path | str = Path("data/wiki/graph.json"),
    archive_path: Path | str = Path("data/wiki/graph_archive.json"),
    pages_dir: Path | str = Path("data/wiki/pages"),
    fragments_dir: Path | str = Path("data/wiki/fragments/research"),
    keywords: list[str] | None = None,
    apply: bool = True,
) -> PurgeResult:
    graph_path = Path(graph_path)
    archive_path = Path(archive_path)
    pages_dir = Path(pages_dir)
    fragments_dir = Path(fragments_dir)
    kws = keywords if keywords is not None else DEFAULT_KEYWORDS

    result = PurgeResult(applied=apply)

    if not graph_path.exists():
        return result

    data = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes: dict = data.get("nodes", {})
    edges: list = data.get("edges", [])

    # Phase 1: contamination removal
    to_remove = [
        nid for nid, node in nodes.items()
        if kws and any(
            kw.lower() in (node.get("text", "") + " " + " ".join(node.get("tags", []))).lower()
            for kw in kws
        )
    ]
    result.removed_node_ids = list(to_remove)

    if apply and to_remove:
        archive_data = (
            json.loads(archive_path.read_text(encoding="utf-8"))
            if archive_path.exists() else {"nodes": {}, "edges": []}
        )
        for nid in to_remove:
            archive_data["nodes"][nid] = {**nodes[nid], "confidence": 0.0}
        _atomic_write(archive_path, archive_data)
        for nid in to_remove:
            nodes.pop(nid, None)

    # Phase 2: dedup by text (keep highest uses, tie-break by confidence)
    by_text: dict[str, list[str]] = {}
    for nid, node in nodes.items():
        key = (node.get("text") or "").strip().lower()
        if key:
            by_text.setdefault(key, []).append(nid)

    dups_to_remove: list[str] = []
    for text_key, ids in by_text.items():
        if len(ids) <= 1:
            continue
        ids_sorted = sorted(
            ids,
            key=lambda i: (nodes[i].get("uses", 1), nodes[i].get("confidence", 0.0)),
            reverse=True,
        )
        dups_to_remove.extend(ids_sorted[1:])

    result.deduped_count = len(dups_to_remove)
    if apply:
        for nid in dups_to_remove:
            nodes.pop(nid, None)

    # Save graph after both removal phases, pruning orphan edges
    if apply and (to_remove or dups_to_remove):
        valid_ids = set(nodes)
        data["edges"] = [e for e in edges if e.get("from") in valid_ids and e.get("to") in valid_ids]
        _atomic_write(graph_path, data)

    # Phase 3: wiki pages
    if pages_dir.exists():
        result.purged_page_blocks = _purge_pages(pages_dir, kws, apply)

    # Phase 4: research fragments
    if fragments_dir.exists():
        result.cleared_fragments = _clear_fragments(fragments_dir, apply)

    return result


def _purge_pages(pages_dir: Path, keywords: list[str], apply: bool) -> int:
    if not keywords:
        return 0
    removed = 0
    for page in pages_dir.rglob("*.md"):
        content = page.read_text(encoding="utf-8")
        blocks = re.split(r"(?=^## )", content, flags=re.MULTILINE)
        clean = [b for b in blocks if not any(kw.lower() in b.lower() for kw in keywords)]
        if len(clean) != len(blocks):
            removed += len(blocks) - len(clean)
            if apply:
                page.write_text("".join(clean), encoding="utf-8")
    return removed


def _clear_fragments(fragments_dir: Path, apply: bool) -> int:
    files = [f for f in fragments_dir.iterdir() if f.suffix in (".md", ".txt") and f.is_file()]
    if apply:
        backup = fragments_dir / "_purged"
        backup.mkdir(exist_ok=True)
        for f in files:
            shutil.move(str(f), backup / f.name)
    return len(files)


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
