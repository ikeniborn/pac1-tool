from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_KEYWORDS: list[str] = [
    "invalid_argument",
    "otp.txt",
    "artifact id",
    "seq.json",
    "reporttaskcompletion",
    "tool_result",
    "harness error",
    "bitgn",
    "pcm error",
]


@dataclass
class HealthResult:
    exit_code: int  # 0=OK, 1=WARN, 2=FAIL
    report: list[str] = field(default_factory=list)
    orphan_count: int = 0
    low_conf_count: int = 0
    contaminated_ids: list[str] = field(default_factory=list)
    duplicate_pairs: list[tuple[str, str]] = field(default_factory=list)


def run_health_check(
    graph_path: Path | str = Path("data/wiki/graph.json"),
    conf_threshold: float = 0.2,
    fail_ratio: float = 0.05,
    keywords: list[str] | None = None,
    quiet: bool = False,
) -> HealthResult:
    graph_path = Path(graph_path)
    kws = keywords if keywords is not None else DEFAULT_KEYWORDS

    if not graph_path.exists():
        return HealthResult(exit_code=0, report=["graph file absent — treating as clean"])

    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return HealthResult(exit_code=2, report=[f"graph JSON invalid: {exc}"])

    nodes: dict = data.get("nodes", {})
    edges: list = data.get("edges", [])
    n = len(nodes)

    orphans = _orphan_edges(nodes, edges)
    low_conf = _low_confidence(nodes, conf_threshold)
    contaminated = _contaminated(nodes, kws)
    dupes = _duplicate_text(nodes)

    report: list[str] = []
    exit_code = 0

    if orphans:
        report.append(f"WARN: {len(orphans)} orphan edge(s)")
        exit_code = max(exit_code, 1)
    if low_conf:
        report.append(f"WARN: {len(low_conf)} node(s) below conf={conf_threshold}")
        exit_code = max(exit_code, 1)
    if dupes:
        report.append(f"WARN: {len(dupes)} duplicate-text pair(s)")
        exit_code = max(exit_code, 1)
    if contaminated:
        ratio = len(contaminated) / max(n, 1)
        if ratio > fail_ratio:
            report.append(
                f"FAIL: {len(contaminated)}/{n} nodes contaminated "
                f"({ratio:.1%} > fail_ratio={fail_ratio:.1%})"
            )
            exit_code = 2
        else:
            report.append(
                f"WARN: {len(contaminated)}/{n} nodes contaminated (<= fail_ratio)"
            )
            exit_code = max(exit_code, 1)

    if exit_code == 0:
        report.append(f"OK: {n} nodes, {len(edges)} edges")

    if not quiet:
        for line in report:
            log.info("[health] %s", line)

    return HealthResult(
        exit_code=exit_code,
        report=report,
        orphan_count=len(orphans),
        low_conf_count=len(low_conf),
        contaminated_ids=contaminated,
        duplicate_pairs=dupes,
    )


def _orphan_edges(nodes: dict, edges: list) -> list[str]:
    ids = set(nodes)
    return [
        f"{e.get('from')}→{e.get('to')}"
        for e in edges
        if e.get("from") not in ids or e.get("to") not in ids
    ]


def _low_confidence(nodes: dict, threshold: float) -> list[str]:
    return [nid for nid, n in nodes.items() if n.get("confidence", 1.0) < threshold]


def _contaminated(nodes: dict, keywords: list[str]) -> list[str]:
    result = []
    for nid, node in nodes.items():
        hay = (node.get("text", "") + " " + " ".join(node.get("tags", []))).lower()
        if any(kw.lower() in hay for kw in keywords):
            result.append(nid)
    return result


def _duplicate_text(nodes: dict) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    for nid, node in nodes.items():
        key = node.get("text", "").strip().lower()
        if not key:
            continue
        if key in seen:
            pairs.append((seen[key], nid))
        else:
            seen[key] = nid
    return pairs
