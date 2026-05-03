# Scripts Lifecycle Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate 4 utility scripts into `agent/maintenance/`, create `agent/preflight.py` and `agent/postrun.py` lifecycle hooks, wire them into `main.py`, and replace the existing subprocess-based `_auto_purge_graph()` with direct module calls.

**Architecture:** New `agent/maintenance/` package exposes clean Python functions. `agent/preflight.py` and `agent/postrun.py` orchestrate these functions at run boundaries. `main.py` loses `_auto_purge_graph()` (subprocess-based, FIX-422) and gains `run_preflight()` / `run_postrun()` calls gated by env flags.

**Tech Stack:** Python stdlib only (no new deps), pytest for tests, existing `agent/wiki_graph.py` and `agent/wiki.py` imports.

---

## File Map

**Create:**
- `agent/maintenance/__init__.py` — empty package marker
- `agent/maintenance/health.py` — graph health check (from `scripts/check_graph_health.py`)
- `agent/maintenance/purge.py` — contamination purge + dedup (from `scripts/purge_research_contamination.py` + inline dedup in `main._auto_purge_graph`)
- `agent/maintenance/distill.py` — contract distillation (from `scripts/distill_contracts.py`)
- `agent/maintenance/candidates.py` — passive task-type candidate logging (from `scripts/analyze_task_types.py`)
- `agent/preflight.py` — preflight orchestrator
- `agent/postrun.py` — postrun orchestrator
- `tests/test_maintenance_health.py`
- `tests/test_maintenance_purge.py`
- `tests/test_maintenance_distill.py`
- `tests/test_maintenance_candidates.py`
- `tests/test_lifecycle.py`

**Modify:**
- `main.py:585-643` — remove `_auto_purge_graph()`, add preflight/postrun calls
- `.env.example` — add 5 new env vars
- `CHANGELOG.md` — document FIX-427

**Delete:**
- `scripts/check_graph_health.py`
- `scripts/purge_research_contamination.py`
- `scripts/distill_contracts.py`
- `scripts/analyze_task_types.py`

---

## Task 1: Create `agent/maintenance/` package skeleton + `health.py`

**Files:**
- Create: `agent/maintenance/__init__.py`
- Create: `agent/maintenance/health.py`
- Create: `tests/test_maintenance_health.py`

### Step 1.1 — Write failing tests

```python
# tests/test_maintenance_health.py
import json
import pytest
from pathlib import Path
from agent.maintenance.health import run_health_check, HealthResult


def _write_graph(path: Path, nodes: dict, edges: list = None) -> None:
    path.write_text(json.dumps({"nodes": nodes, "edges": edges or []}), encoding="utf-8")


def test_missing_file_returns_ok(tmp_path):
    result = run_health_check(graph_path=tmp_path / "missing.json")
    assert isinstance(result, HealthResult)
    assert result.exit_code == 0


def test_empty_graph_ok(tmp_path):
    gp = tmp_path / "graph.json"
    _write_graph(gp, {})
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 0
    assert result.contaminated_ids == []
    assert result.orphan_count == 0


def test_contamination_above_ratio_is_fail(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {
        "bad": {
            "type": "antipattern", "tags": [],
            "text": "INVALID_ARGUMENT error from harness",
            "confidence": 0.9, "uses": 1, "last_seen": "2026-05-03",
        }
    }
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp, keywords=["invalid_argument"], fail_ratio=0.0)
    assert result.exit_code == 2
    assert "bad" in result.contaminated_ids


def test_contamination_below_ratio_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    good = {f"g{i}": {"type": "rule", "tags": [], "text": f"tip {i}", "confidence": 0.9,
                       "uses": 1, "last_seen": "2026"} for i in range(99)}
    good["bad"] = {"type": "antipattern", "tags": [], "text": "invalid_argument",
                   "confidence": 0.9, "uses": 1, "last_seen": "2026"}
    _write_graph(gp, good)
    result = run_health_check(graph_path=gp, keywords=["invalid_argument"], fail_ratio=0.05)
    assert result.exit_code == 1  # 1/100 = 1% ≤ 5%, WARN not FAIL


def test_orphan_edge_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {"n1": {"type": "rule", "tags": [], "text": "tip", "confidence": 0.9, "uses": 1, "last_seen": "2026"}}
    edges = [{"from": "n1", "rel": "requires", "to": "MISSING"}]
    _write_graph(gp, nodes, edges)
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 1
    assert result.orphan_count == 1


def test_low_confidence_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {"n1": {"type": "rule", "tags": [], "text": "tip", "confidence": 0.05,
                    "uses": 1, "last_seen": "2026"}}
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp, conf_threshold=0.2)
    assert result.exit_code == 1
    assert result.low_conf_count == 1


def test_invalid_json_is_fail(tmp_path):
    gp = tmp_path / "graph.json"
    gp.write_text("{not valid json}", encoding="utf-8")
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 2


def test_duplicate_text_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {
        "n1": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.9, "uses": 1, "last_seen": "2026"},
        "n2": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.8, "uses": 1, "last_seen": "2026"},
    }
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 1
    assert len(result.duplicate_pairs) == 1
```

- [ ] Create `agent/maintenance/__init__.py` (empty file)
- [ ] Save the test file above to `tests/test_maintenance_health.py`

### Step 1.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_maintenance_health.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'agent.maintenance'`

### Step 1.3 — Implement `agent/maintenance/health.py`

```python
# agent/maintenance/health.py
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
                f"WARN: {len(contaminated)}/{n} nodes contaminated (≤ fail_ratio)"
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
```

### Step 1.4 — Run tests to verify they pass

```bash
uv run pytest tests/test_maintenance_health.py -v
```

Expected: all 8 tests PASS

### Step 1.5 — Commit

```bash
git add agent/maintenance/__init__.py agent/maintenance/health.py tests/test_maintenance_health.py
git commit -m "feat(maintenance): add agent/maintenance package + health.py — FIX-427"
```

---

## Task 2: `agent/maintenance/purge.py`

> Note: The existing `_auto_purge_graph()` in `main.py` (lines 585–635) does two things:  
> 1. Calls `scripts/purge_research_contamination.py --apply` via subprocess  
> 2. Deduplicates nodes by text in-process  
> This task merges both into `run_purge()`.

**Files:**
- Create: `agent/maintenance/purge.py`
- Create: `tests/test_maintenance_purge.py`

### Step 2.1 — Write failing tests

```python
# tests/test_maintenance_purge.py
import json
import pytest
from pathlib import Path
from agent.maintenance.purge import run_purge, PurgeResult


@pytest.fixture
def env(tmp_path):
    graph = {
        "nodes": {
            "bad": {
                "type": "antipattern", "tags": [],
                "text": "INVALID_ARGUMENT error from harness",
                "confidence": 0.9, "uses": 1, "last_seen": "2026",
            },
            "good": {
                "type": "rule", "tags": ["email"],
                "text": "always verify subject line",
                "confidence": 0.9, "uses": 3, "last_seen": "2026",
            },
        },
        "edges": [{"from": "bad", "rel": "conflicts_with", "to": "good"}],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    pages = tmp_path / "pages"
    pages.mkdir()
    fragments = tmp_path / "fragments"
    fragments.mkdir()
    return {
        "graph": graph_path,
        "archive": tmp_path / "archive.json",
        "pages": pages,
        "fragments": fragments,
    }


def test_purge_removes_contaminated_node(env):
    result = run_purge(
        graph_path=env["graph"], archive_path=env["archive"],
        pages_dir=env["pages"], fragments_dir=env["fragments"],
        keywords=["invalid_argument"], apply=True,
    )
    assert isinstance(result, PurgeResult)
    assert "bad" in result.removed_node_ids
    assert "good" not in result.removed_node_ids
    data = json.loads(env["graph"].read_text())
    assert "bad" not in data["nodes"]
    assert "good" in data["nodes"]


def test_purge_removes_orphan_edges(env):
    run_purge(
        graph_path=env["graph"], archive_path=env["archive"],
        pages_dir=env["pages"], fragments_dir=env["fragments"],
        keywords=["invalid_argument"], apply=True,
    )
    data = json.loads(env["graph"].read_text())
    assert not any(e["from"] == "bad" or e["to"] == "bad" for e in data["edges"])


def test_purge_archives_removed_nodes(env):
    run_purge(
        graph_path=env["graph"], archive_path=env["archive"],
        pages_dir=env["pages"], fragments_dir=env["fragments"],
        keywords=["invalid_argument"], apply=True,
    )
    archive = json.loads(env["archive"].read_text())
    assert "bad" in archive["nodes"]
    assert archive["nodes"]["bad"]["confidence"] == 0.0


def test_purge_dry_run_no_changes(env):
    original = env["graph"].read_text()
    result = run_purge(
        graph_path=env["graph"], archive_path=env["archive"],
        pages_dir=env["pages"], fragments_dir=env["fragments"],
        keywords=["invalid_argument"], apply=False,
    )
    assert env["graph"].read_text() == original
    assert result.applied is False
    assert "bad" in result.removed_node_ids


def test_purge_removes_contaminated_page_block(env):
    page = env["pages"] / "email.md"
    page.write_text(
        "## Good pattern\nSome good advice.\n## Bad block\nINVALID_ARGUMENT note.\n",
        encoding="utf-8",
    )
    result = run_purge(
        graph_path=env["graph"], archive_path=env["archive"],
        pages_dir=env["pages"], fragments_dir=env["fragments"],
        keywords=["invalid_argument"], apply=True,
    )
    assert result.purged_page_blocks >= 1
    content = page.read_text()
    assert "INVALID_ARGUMENT" not in content
    assert "Good pattern" in content


def test_purge_deduplicates_by_text(tmp_path):
    pages = tmp_path / "pages"; pages.mkdir()
    fragments = tmp_path / "fragments"; fragments.mkdir()
    graph = {
        "nodes": {
            "n1": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.9, "uses": 5, "last_seen": "2026"},
            "n2": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.8, "uses": 1, "last_seen": "2026"},
            "n3": {"type": "rule", "tags": [], "text": "unique text", "confidence": 0.9, "uses": 1, "last_seen": "2026"},
        },
        "edges": [],
    }
    gp = tmp_path / "graph.json"
    gp.write_text(json.dumps(graph), encoding="utf-8")
    result = run_purge(
        graph_path=gp, archive_path=tmp_path / "archive.json",
        pages_dir=pages, fragments_dir=fragments,
        keywords=[], apply=True,
    )
    data = json.loads(gp.read_text())
    assert "n1" in data["nodes"]   # higher uses → kept
    assert "n2" not in data["nodes"]  # duplicate → removed
    assert "n3" in data["nodes"]
    assert result.deduped_count == 1


def test_purge_missing_graph_returns_empty(tmp_path):
    pages = tmp_path / "pages"; pages.mkdir()
    fragments = tmp_path / "fragments"; fragments.mkdir()
    result = run_purge(
        graph_path=tmp_path / "missing.json",
        archive_path=tmp_path / "archive.json",
        pages_dir=pages, fragments_dir=fragments,
        apply=True,
    )
    assert result.removed_node_ids == []
```

- [ ] Save tests above to `tests/test_maintenance_purge.py`

### Step 2.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_maintenance_purge.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PurgeResult' from 'agent.maintenance.purge'`

### Step 2.3 — Implement `agent/maintenance/purge.py`

```python
# agent/maintenance/purge.py
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

    # Phase 2: dedup (keep node with highest uses; tie-break by confidence)
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

    # Remove orphan edges after both phases
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
        # Split on H2 section boundaries
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
```

### Step 2.4 — Run tests

```bash
uv run pytest tests/test_maintenance_purge.py -v
```

Expected: all 7 tests PASS

### Step 2.5 — Commit

```bash
git add agent/maintenance/purge.py tests/test_maintenance_purge.py
git commit -m "feat(maintenance): add purge.py — contamination removal + dedup — FIX-427"
```

---

## Task 3: `agent/maintenance/distill.py`

**Files:**
- Create: `agent/maintenance/distill.py`
- Create: `tests/test_maintenance_distill.py`

### Step 3.1 — Write failing tests

```python
# tests/test_maintenance_distill.py
import json
import pytest
from pathlib import Path
from agent.maintenance.distill import run_distill, DistillResult


def _write_examples(path: Path, task_type: str, count: int, score: float = 1.0) -> None:
    lines = []
    for i in range(count):
        lines.append(json.dumps({
            "task_type": task_type,
            "score": score,
            "plan_steps": [f"step_{i % 3}"],
            "success_criteria": [f"criterion_{i % 3}"],
            "required_evidence": [f"evidence_{i % 3}"],
            "failure_conditions": [f"fail_{i % 3}"],
        }))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_distill_skips_below_threshold(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=5)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert isinstance(result, DistillResult)
    assert "email" in result.types_skipped
    assert "email" not in result.types_processed
    assert not list(contracts.iterdir())


def test_distill_processes_above_threshold(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert "email" in result.types_processed
    out = contracts / "email.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "plan_steps" in data
    assert "success_criteria" in data
    assert "required_evidence" in data
    assert "failure_conditions" in data


def test_distill_ignores_low_score_examples(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15, score=0.5)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert "email" in result.types_skipped
    assert not list(contracts.iterdir())


def test_distill_dry_run_no_files(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=False)
    assert "email" in result.types_processed
    assert result.applied is False
    assert not list(contracts.iterdir())


def test_distill_missing_examples_file(tmp_path):
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(
        min_examples=10,
        examples_path=tmp_path / "missing.jsonl",
        contracts_dir=contracts,
        apply=True,
    )
    assert result.types_processed == []
    assert result.types_skipped == []


def test_distill_task_type_filter(tmp_path):
    ex = tmp_path / "examples.jsonl"
    lines = [
        json.dumps({"task_type": "email", "score": 1.0, "plan_steps": ["s1"],
                    "success_criteria": ["c1"], "required_evidence": ["e1"], "failure_conditions": ["f1"]}),
    ] * 15 + [
        json.dumps({"task_type": "lookup", "score": 1.0, "plan_steps": ["s2"],
                    "success_criteria": ["c2"], "required_evidence": ["e2"], "failure_conditions": ["f2"]}),
    ] * 15
    ex.write_text("\n".join(lines), encoding="utf-8")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, task_type="email", examples_path=ex,
                         contracts_dir=contracts, apply=True)
    assert "email" in result.types_processed
    assert "lookup" not in result.types_processed
    assert not (contracts / "lookup.json").exists()
```

- [ ] Save tests to `tests/test_maintenance_distill.py`

### Step 3.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_maintenance_distill.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'DistillResult'`

### Step 3.3 — Implement `agent/maintenance/distill.py`

```python
# agent/maintenance/distill.py
from __future__ import annotations
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_TOP_N = 5


@dataclass
class DistillResult:
    types_processed: list[str] = field(default_factory=list)
    types_skipped: list[str] = field(default_factory=list)
    applied: bool = False


def run_distill(
    min_examples: int = 10,
    task_type: str | None = None,
    examples_path: Path | str = Path("data/dspy_contract_examples.jsonl"),
    contracts_dir: Path | str = Path("data/default_contracts"),
    apply: bool = True,
) -> DistillResult:
    examples_path = Path(examples_path)
    contracts_dir = Path(contracts_dir)
    result = DistillResult(applied=apply)

    if not examples_path.exists():
        return result

    by_type: dict[str, list[dict]] = {}
    for line in examples_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ex = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ex.get("score", 0.0) < 1.0:
            continue
        t = ex.get("task_type", "")
        if task_type and t != task_type:
            continue
        by_type.setdefault(t, []).append(ex)

    for t, examples in by_type.items():
        if len(examples) < min_examples:
            result.types_skipped.append(t)
            log.info("[distill] %s: %d examples < min_examples=%d, skipping", t, len(examples), min_examples)
            continue

        contract = _distill_one(examples)
        result.types_processed.append(t)

        if apply:
            contracts_dir.mkdir(parents=True, exist_ok=True)
            out = contracts_dir / f"{t}.json"
            out.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("[distill] %s: wrote %s", t, out)

    return result


def _distill_one(examples: list[dict]) -> dict:
    def top_n(field_name: str) -> list[str]:
        items: list[str] = []
        for ex in examples:
            val = ex.get(field_name, [])
            if isinstance(val, list):
                items.extend(val)
        return [item for item, _ in Counter(items).most_common(_TOP_N)]

    return {
        "plan_steps": top_n("plan_steps"),
        "success_criteria": top_n("success_criteria"),
        "required_evidence": top_n("required_evidence"),
        "failure_conditions": top_n("failure_conditions"),
    }
```

### Step 3.4 — Run tests

```bash
uv run pytest tests/test_maintenance_distill.py -v
```

Expected: all 6 tests PASS

### Step 3.5 — Commit

```bash
git add agent/maintenance/distill.py tests/test_maintenance_distill.py
git commit -m "feat(maintenance): add distill.py — contract distillation from scored examples — FIX-427"
```

---

## Task 4: `agent/maintenance/candidates.py`

**Files:**
- Create: `agent/maintenance/candidates.py`
- Create: `tests/test_maintenance_candidates.py`

### Step 4.1 — Write failing tests

```python
# tests/test_maintenance_candidates.py
import json
import pytest
from pathlib import Path
from agent.maintenance.candidates import log_candidates, CandidatesReport, _normalize


def test_normalize_lowercases_and_underscores():
    assert _normalize("Email Task") == "email_task"
    assert _normalize("LOOKUP--TYPE") == "lookup_type"
    assert _normalize("  crm  ") == "crm"
    assert _normalize("new-type-v2") == "new_type_v2"


def test_missing_file_returns_empty(tmp_path):
    report = log_candidates(candidates_path=tmp_path / "missing.jsonl", min_count=5)
    assert isinstance(report, CandidatesReport)
    assert report.total == 0
    assert report.above_threshold == {}


def test_below_threshold_not_in_above(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 3),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 3
    assert "new_type" not in report.above_threshold
    assert report.all_counts.get("new_type") == 3


def test_above_threshold_included(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join([json.dumps({"llm_suggested": "new_type"})] * 7),
        encoding="utf-8",
    )
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 7
    assert report.above_threshold == {"new_type": 7}


def test_multiple_types(tmp_path):
    path = tmp_path / "candidates.jsonl"
    lines = (
        [json.dumps({"llm_suggested": "alpha"})] * 6 +
        [json.dumps({"llm_suggested": "beta"})] * 3
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 9
    assert "alpha" in report.above_threshold
    assert "beta" not in report.above_threshold


def test_empty_file_returns_empty(tmp_path):
    path = tmp_path / "candidates.jsonl"
    path.write_text("", encoding="utf-8")
    report = log_candidates(candidates_path=path, min_count=5)
    assert report.total == 0
```

- [ ] Save tests to `tests/test_maintenance_candidates.py`

### Step 4.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_maintenance_candidates.py -v 2>&1 | head -15
```

Expected: `ImportError`

### Step 4.3 — Implement `agent/maintenance/candidates.py`

```python
# agent/maintenance/candidates.py
from __future__ import annotations
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class CandidatesReport:
    total: int = 0
    above_threshold: dict[str, int] = field(default_factory=dict)
    all_counts: dict[str, int] = field(default_factory=dict)


def log_candidates(
    candidates_path: Path | str = Path("data/task_type_candidates.jsonl"),
    min_count: int = 5,
) -> CandidatesReport:
    candidates_path = Path(candidates_path)
    report = CandidatesReport()

    if not candidates_path.exists():
        return report

    labels: list[str] = []
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        label = _normalize(rec.get("llm_suggested", ""))
        if label:
            labels.append(label)

    counts = Counter(labels)
    report.total = len(labels)
    report.all_counts = dict(counts)
    report.above_threshold = {k: v for k, v in counts.items() if v >= min_count}

    if report.above_threshold:
        log.warning(
            "[candidates] %d type(s) above min_count=%d: %s",
            len(report.above_threshold), min_count, report.above_threshold,
        )
    else:
        log.info("[candidates] no candidates above min_count=%d (total=%d)", min_count, report.total)

    return report


def _normalize(label: str) -> str:
    label = label.lower().strip()
    label = re.sub(r"[^a-z0-9]+", "_", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label
```

### Step 4.4 — Run tests

```bash
uv run pytest tests/test_maintenance_candidates.py -v
```

Expected: all 6 tests PASS

### Step 4.5 — Commit

```bash
git add agent/maintenance/candidates.py tests/test_maintenance_candidates.py
git commit -m "feat(maintenance): add candidates.py — passive task-type candidate logging — FIX-427"
```

---

## Task 5: `agent/preflight.py` + integration tests

**Files:**
- Create: `agent/preflight.py`
- Create: `tests/test_lifecycle.py` (preflight section)

### Step 5.1 — Write failing preflight integration tests

```python
# tests/test_lifecycle.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.maintenance.health import HealthResult
from agent.maintenance.purge import PurgeResult


def _health_ok() -> HealthResult:
    return HealthResult(exit_code=0, report=["OK: 0 nodes, 0 edges"])


def _health_warn() -> HealthResult:
    return HealthResult(exit_code=1, report=["WARN: 1 orphan edge"], orphan_count=1)


def _health_fail() -> HealthResult:
    return HealthResult(exit_code=2, report=["FAIL: 1/1 contaminated"], contaminated_ids=["bad"])


def _purge_ok() -> PurgeResult:
    return PurgeResult(removed_node_ids=["bad"], applied=True)


class TestPreflight:
    def test_clean_graph_passes(self):
        with patch("agent.preflight.run_health_check", return_value=_health_ok()), \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()  # must not raise

    def test_warn_health_passes_without_purge(self):
        with patch("agent.preflight.run_health_check", return_value=_health_warn()) as mock_health, \
             patch("agent.preflight.run_purge") as mock_purge, \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()
        mock_purge.assert_not_called()

    def test_fail_graph_triggers_auto_purge(self):
        health_seq = [_health_fail(), _health_ok()]
        with patch("agent.preflight.run_health_check", side_effect=health_seq) as mock_health, \
             patch("agent.preflight.run_purge", return_value=_purge_ok()) as mock_purge, \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()  # must not raise

        mock_purge.assert_called_once()
        assert mock_health.call_count == 2

    def test_fail_still_after_purge_exits(self):
        with patch("agent.preflight.run_health_check", return_value=_health_fail()), \
             patch("agent.preflight.run_purge", return_value=_purge_ok()), \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            with pytest.raises(SystemExit) as exc:
                pf.run_preflight()
            assert exc.value.code == 1

    def test_empty_wiki_page_exits(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "email.md").write_text("", encoding="utf-8")

        import agent.preflight as pf
        with pytest.raises(SystemExit) as exc:
            pf._check_wiki_pages(pages_dir=pages)
        assert exc.value.code == 1

    def test_valid_wiki_pages_pass(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "email.md").write_text("## Pattern\nsome content", encoding="utf-8")

        import agent.preflight as pf
        pf._check_wiki_pages(pages_dir=pages)  # must not raise

    def test_invalid_graph_json_exits(self, tmp_path):
        gp = tmp_path / "graph.json"
        gp.write_text("{bad json}", encoding="utf-8")

        import agent.preflight as pf
        with pytest.raises(SystemExit) as exc:
            pf._check_graph_loadable(graph_path=gp)
        assert exc.value.code == 1

    def test_missing_graph_is_ok(self, tmp_path):
        import agent.preflight as pf
        pf._check_graph_loadable(graph_path=tmp_path / "missing.json")  # must not raise
```

- [ ] Save the preflight tests to `tests/test_lifecycle.py`

### Step 5.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_lifecycle.py::TestPreflight -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'run_preflight' from 'agent.preflight'`

### Step 5.3 — Implement `agent/preflight.py`

```python
# agent/preflight.py
from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

from agent.maintenance.health import run_health_check
from agent.maintenance.purge import run_purge

log = logging.getLogger(__name__)


def run_preflight() -> None:
    """FIX-427: Run preflight checks. Raises SystemExit(1) on failure."""
    _check_graph()
    _check_wiki_pages()
    _check_graph_loadable()
    log.info("[preflight] all checks passed")


def _check_graph() -> None:
    result = run_health_check()
    for line in result.report:
        log.info("[preflight] %s", line)

    if result.exit_code < 2:
        return  # OK or WARN — continue

    log.warning("[preflight] graph FAIL — auto-purging contamination")
    run_purge(apply=True)

    result2 = run_health_check()
    for line in result2.report:
        log.info("[preflight] re-check: %s", line)

    if result2.exit_code == 2:
        msg = "; ".join(result2.report)
        log.error("[preflight] graph still FAIL after purge: %s", msg)
        sys.exit(1)


def _check_wiki_pages(pages_dir: Path = Path("data/wiki/pages")) -> None:
    if not pages_dir.exists():
        return
    for page in pages_dir.rglob("*.md"):
        if page.stat().st_size == 0:
            log.error("[preflight] wiki page is empty: %s", page)
            sys.exit(1)


def _check_graph_loadable(graph_path: Path = Path("data/wiki/graph.json")) -> None:
    if not graph_path.exists():
        return
    try:
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        if not isinstance(data.get("nodes"), dict) or not isinstance(data.get("edges"), list):
            raise ValueError("missing 'nodes' dict or 'edges' list")
    except Exception as exc:
        log.error("[preflight] graph.json invalid: %s", exc)
        sys.exit(1)
```

### Step 5.4 — Run tests

```bash
uv run pytest tests/test_lifecycle.py::TestPreflight -v
```

Expected: all 8 tests PASS

### Step 5.5 — Commit

```bash
git add agent/preflight.py tests/test_lifecycle.py
git commit -m "feat(preflight): add run_preflight() — health check + auto-purge + wiki integrity — FIX-427"
```

---

## Task 6: `agent/postrun.py` + integration tests

**Files:**
- Create: `agent/postrun.py`
- Modify: `tests/test_lifecycle.py` — add `TestPostrun` class

### Step 6.1 — Write failing postrun integration tests

Append to `tests/test_lifecycle.py`:

```python
# Append to tests/test_lifecycle.py

import subprocess  # already imported via stdlib


class TestPostrun:
    def test_all_steps_run_in_order(self, monkeypatch):
        call_log: list[str] = []
        monkeypatch.setenv("POSTRUN_ENABLED", "1")
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)

        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)) as mp, \
             patch("agent.postrun.run_wiki_lint") as mw, \
             patch("agent.postrun.run_distill") as md, \
             patch("agent.postrun.log_candidates") as mc, \
             patch("subprocess.run") as ms:
            mp.side_effect = lambda **kw: call_log.append("purge") or PurgeResult(applied=True)
            mw.side_effect = lambda **kw: call_log.append("wiki_lint")
            md.side_effect = lambda **kw: call_log.append("distill") or __import__("agent.maintenance.distill", fromlist=["DistillResult"]).DistillResult()
            mc.side_effect = lambda **kw: call_log.append("candidates") or __import__("agent.maintenance.candidates", fromlist=["CandidatesReport"]).CandidatesReport()

            import agent.postrun as pr
            # Make distill threshold low
            with patch.object(Path, "exists", return_value=True), \
                 patch("agent.postrun._count_contract_examples", return_value=100):
                pr.run_postrun()

        assert "purge" in call_log
        assert "wiki_lint" in call_log
        ms.assert_not_called()  # POSTRUN_OPTIMIZE not set

    def test_optimize_subprocess_called_when_enabled(self, monkeypatch):
        monkeypatch.setenv("POSTRUN_OPTIMIZE", "1")

        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates"), \
             patch("agent.postrun._count_contract_examples", return_value=0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
            import agent.postrun as pr
            pr.run_postrun()

        mock_run.assert_called_once_with(
            ["python", "scripts/optimize_prompts.py", "--target", "all"],
            check=True, capture_output=True, text=True,
        )

    def test_optimize_not_called_by_default(self, monkeypatch):
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates"), \
             patch("agent.postrun._count_contract_examples", return_value=0), \
             patch("subprocess.run") as mock_run:
            import agent.postrun as pr
            pr.run_postrun()
        mock_run.assert_not_called()

    def test_purge_failure_exits(self):
        with patch("agent.postrun.run_purge", side_effect=RuntimeError("disk full")):
            import agent.postrun as pr
            with pytest.raises(SystemExit) as exc:
                pr.run_postrun()
            assert exc.value.code == 1

    def test_wiki_lint_failure_exits(self):
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint", side_effect=RuntimeError("LLM error")):
            import agent.postrun as pr
            with pytest.raises(SystemExit) as exc:
                pr.run_postrun()
            assert exc.value.code == 1

    def test_candidates_failure_does_not_exit(self, monkeypatch):
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates", side_effect=RuntimeError("oops")), \
             patch("agent.postrun._count_contract_examples", return_value=0):
            import agent.postrun as pr
            pr.run_postrun()  # must NOT raise — candidates failure is non-critical
```

- [ ] Append the `TestPostrun` class to `tests/test_lifecycle.py`

### Step 6.2 — Run tests to verify they fail

```bash
uv run pytest tests/test_lifecycle.py::TestPostrun -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'run_postrun' from 'agent.postrun'`

### Step 6.3 — Implement `agent/postrun.py`

```python
# agent/postrun.py
from __future__ import annotations
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from agent.maintenance.purge import run_purge
from agent.maintenance.distill import run_distill
from agent.maintenance.candidates import log_candidates
from agent.wiki import run_wiki_lint

log = logging.getLogger(__name__)

_CONTRACT_EXAMPLES = Path("data/dspy_contract_examples.jsonl")


def run_postrun() -> None:
    """FIX-427: Run postrun maintenance. Raises SystemExit(1) on non-candidate failures."""
    _do_purge()
    _do_wiki_lint()
    _do_distill_contracts()
    _do_log_candidates()
    _do_optimize_if_enabled()
    log.info("[postrun] all steps complete")


def _do_purge() -> None:
    try:
        result = run_purge(apply=True)
        log.info(
            "[postrun] purge: removed=%d nodes, deduped=%d, page_blocks=%d, fragments=%d",
            len(result.removed_node_ids), result.deduped_count,
            result.purged_page_blocks, result.cleared_fragments,
        )
    except Exception as exc:
        log.error("[postrun] purge failed: %s", exc)
        sys.exit(1)


def _do_wiki_lint() -> None:
    model = os.getenv("MODEL_WIKI") or os.getenv("MODEL_DEFAULT") or ""
    cfg: dict = {}
    models_path = Path("models.json")
    if models_path.exists():
        try:
            cfg = json.loads(models_path.read_text(encoding="utf-8")).get(model, {})
        except Exception:
            pass
    try:
        run_wiki_lint(model=model, cfg=cfg)
    except Exception as exc:
        log.error("[postrun] wiki lint failed: %s", exc)
        sys.exit(1)


def _do_distill_contracts() -> None:
    min_ex = int(os.getenv("POSTRUN_DISTILL_MIN_EXAMPLES", "10"))
    count = _count_contract_examples()
    if count < min_ex:
        log.info("[postrun] %d contract examples < min=%d, skipping distill", count, min_ex)
        return
    try:
        result = run_distill(min_examples=min_ex, apply=True)
        log.info("[postrun] distill: processed=%s skipped=%s", result.types_processed, result.types_skipped)
    except Exception as exc:
        log.error("[postrun] distill failed: %s", exc)
        sys.exit(1)


def _do_log_candidates() -> None:
    min_count = int(os.getenv("POSTRUN_PROMOTE_MIN_COUNT", "5"))
    try:
        log_candidates(min_count=min_count)
    except Exception as exc:
        log.warning("[postrun] candidates log failed (non-critical): %s", exc)


def _do_optimize_if_enabled() -> None:
    if os.getenv("POSTRUN_OPTIMIZE", "0") != "1":
        return
    try:
        proc = subprocess.run(
            ["python", "scripts/optimize_prompts.py", "--target", "all"],
            check=True,
            capture_output=True,
            text=True,
        )
        tail = proc.stdout[-500:] if proc.stdout else ""
        log.info("[postrun] optimize done: %s", tail)
    except subprocess.CalledProcessError as exc:
        tail = exc.stderr[-500:] if exc.stderr else ""
        log.error("[postrun] optimize failed (exit %d): %s", exc.returncode, tail)
        sys.exit(1)


def _count_contract_examples() -> int:
    if not _CONTRACT_EXAMPLES.exists():
        return 0
    return sum(1 for ln in _CONTRACT_EXAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip())
```

### Step 6.4 — Run tests

```bash
uv run pytest tests/test_lifecycle.py -v
```

Expected: all tests in TestPreflight and TestPostrun PASS

### Step 6.5 — Commit

```bash
git add agent/postrun.py tests/test_lifecycle.py
git commit -m "feat(postrun): add run_postrun() — purge + wiki lint + distill + candidates + optimize — FIX-427"
```

---

## Task 7: Wire preflight/postrun into `main.py`

**Files:**
- Modify: `main.py:585-643`

> Key context: `main.py` has `_auto_purge_graph()` (lines 585–635, FIX-422) that calls `scripts/purge_research_contamination.py` via subprocess. This is replaced by `run_preflight()` / `run_postrun()`. The always-on subprocess purge is removed; users enable the new hooks via env flags.

### Step 7.1 — Remove `_auto_purge_graph()` and its call

Replace the block from line 585 to 643 (the `_auto_purge_graph` function definition + its call at line 643 inside `main()`):

Remove this entire function (lines 585–635):
```python
def _auto_purge_graph() -> None:
    """FIX-422: auto-purge contaminated/duplicate graph nodes before each run.
    ...
    """
    ...
```

Remove this call inside `main()` (line 643):
```python
    # FIX-422: auto-purge graph contamination and duplicates before each run
    _auto_purge_graph()
```

Using Edit tool — find and remove `_auto_purge_graph`:

```
old_string (lines 585-643 in main.py):

def _auto_purge_graph() -> None:
    """FIX-422: auto-purge contaminated/duplicate graph nodes before each run.

    Replaces the manual 'purge then re-run' workflow. Runs purge_research_contamination
    in apply mode and then removes exact-text duplicate nodes (same text, different
    type prefix). Fail-open: any error is printed but does not abort the run.
    """
    try:
        import importlib.util, subprocess, sys as _sys
        result = subprocess.run(
            [_sys.executable, "scripts/purge_research_contamination.py", "--apply"],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                print(f"[graph-purge] {line}")
    except Exception as exc:
        print(f"[graph-purge] contamination purge skipped: {exc}")

    try:
        import json
        from pathlib import Path as _Path
        _gp = _Path("data/wiki/graph.json")
        if not _gp.exists():
            return
        _g = json.loads(_gp.read_text())
        _by_text: dict[str, list[str]] = {}
        for _nid, _n in _g.get("nodes", {}).items():
            _key = (_n.get("text") or "").strip().lower()
            if _key:
                _by_text.setdefault(_key, []).append(_nid)
        _removed = 0
        for _text, _ids in _by_text.items():
            if len(_ids) <= 1:
                continue
            # Keep node with highest uses; break ties by confidence, then keep first
            _ids_sorted = sorted(
                _ids,
                key=lambda i: (_g["nodes"][i].get("uses", 1), _g["nodes"][i].get("confidence", 0.0)),
                reverse=True,
            )
            for _dup in _ids_sorted[1:]:
                del _g["nodes"][_dup]
                _removed += 1
        if _removed:
            _before = len(_g["edges"])
            _g["edges"] = [e for e in _g["edges"] if e.get("from") in _g["nodes"] and e.get("to") in _g["nodes"]]
            _gp.write_text(json.dumps(_g, ensure_ascii=False, indent=2))
            print(f"[graph-purge] removed {_removed} duplicate-text nodes, edges {_before}→{len(_g['edges'])}")
    except Exception as exc:
        print(f"[graph-purge] dedup pass skipped: {exc}")


def main() -> None:
    # Split comma-joined args: "t01,t02,t03" → ['t01', 't02', 't03']
    task_filter = [t for arg in sys.argv[1:] for t in arg.split(",") if t]

    # FIX-422: auto-purge graph contamination and duplicates before each run
    _auto_purge_graph()
```

Replace with:

```python
def main() -> None:
    # Split comma-joined args: "t01,t02,t03" → ['t01', 't02', 't03']
    task_filter = [t for arg in sys.argv[1:] for t in arg.split(",") if t]

    # FIX-427: lifecycle hooks — preflight before tasks, postrun after
    if os.getenv("PREFLIGHT_ENABLED", "0") == "1":
        from agent.preflight import run_preflight
        run_preflight()
```

- [ ] Apply the Edit to `main.py` to remove `_auto_purge_graph()` and add the preflight call

### Step 7.2 — Add postrun call after the final wiki lint in `main.py`

Find the block that ends the run (after the final wiki lint, around line 698):

```python
            # Wiki-Memory lint after: compile fragments written in this run (FIX-105)
            if os.getenv("WIKI_LINT_ENABLED", "1") == "1":
                try:
                    _run_wiki_lint(model=_model_wiki, cfg=MODEL_CONFIGS.get(_model_wiki, {}))
                except Exception as _wiki_exc:
                    print(f"[wiki-lint-after] skipped: {_wiki_exc}")
```

Replace with:

```python
            # Wiki-Memory lint after: compile fragments written in this run (FIX-105)
            if os.getenv("WIKI_LINT_ENABLED", "1") == "1":
                try:
                    _run_wiki_lint(model=_model_wiki, cfg=MODEL_CONFIGS.get(_model_wiki, {}))
                except Exception as _wiki_exc:
                    print(f"[wiki-lint-after] skipped: {_wiki_exc}")

            # FIX-427: postrun maintenance — purge, wiki lint, distill, candidates, optimize
            if os.getenv("POSTRUN_ENABLED", "0") == "1":
                from agent.postrun import run_postrun
                run_postrun()
```

- [ ] Apply the Edit to `main.py`

### Step 7.3 — Run the full test suite to verify no regressions

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests still PASS (lifecycle tests PASS, no regressions)

### Step 7.4 — Commit

```bash
git add main.py
git commit -m "feat(main): wire preflight/postrun hooks, remove _auto_purge_graph() subprocess — FIX-427"
```

---

## Task 8: Update `.env.example` and `CHANGELOG.md`

**Files:**
- Modify: `.env.example`
- Modify: `CHANGELOG.md`

### Step 8.1 — Read current `.env.example` tail to find insertion point

```bash
grep -n "WIKI_GRAPH_FEEDBACK\|POSTRUN\|PREFLIGHT" .env.example | tail -10
```

Find the `WIKI_GRAPH_FEEDBACK` variable section, then add after it.

### Step 8.2 — Add new env vars to `.env.example`

Find the last WIKI_GRAPH_* variable block and add after it:

```
# --- Lifecycle hooks (FIX-427) ---
# PREFLIGHT_ENABLED=0    # Set to 1: run health check + auto-purge before benchmark; fail-closed
# POSTRUN_ENABLED=0      # Set to 1: run purge + wiki lint + distill + candidates after benchmark; fail-closed
# POSTRUN_DISTILL_MIN_EXAMPLES=10   # Min score=1.0 contract examples to trigger distillation
# POSTRUN_PROMOTE_MIN_COUNT=5       # Min candidate count to emit a warning log
# POSTRUN_OPTIMIZE=0     # Set to 1: run scripts/optimize_prompts.py --target all after postrun
```

- [ ] Apply the Edit to `.env.example` to add the 5 new variables

### Step 8.3 — Read CHANGELOG.md and add FIX-427 entry

Read current head of CHANGELOG.md, then prepend:

```markdown
## FIX-427 — Scripts lifecycle automation (2026-05-03)

- Added `agent/maintenance/` package: `health.py`, `purge.py`, `distill.py`, `candidates.py`
- Migrated `scripts/check_graph_health.py` → `agent/maintenance/health.py`
- Migrated `scripts/purge_research_contamination.py` → `agent/maintenance/purge.py` (includes dedup from `_auto_purge_graph`)
- Migrated `scripts/distill_contracts.py` → `agent/maintenance/distill.py`
- Migrated `scripts/analyze_task_types.py` → `agent/maintenance/candidates.py` (passive log only; interactive --promote removed)
- Added `agent/preflight.py`: health check + auto-purge + wiki integrity; fail-closed when `PREFLIGHT_ENABLED=1`
- Added `agent/postrun.py`: purge + wiki lint + distill + candidates + optional optimize; fail-closed when `POSTRUN_ENABLED=1`
- Removed `_auto_purge_graph()` subprocess call from `main.py` (FIX-422 superseded)
- New env vars: `PREFLIGHT_ENABLED`, `POSTRUN_ENABLED`, `POSTRUN_DISTILL_MIN_EXAMPLES`, `POSTRUN_PROMOTE_MIN_COUNT`, `POSTRUN_OPTIMIZE`
```

- [ ] Apply the Edit to `CHANGELOG.md`

### Step 8.4 — Commit

```bash
git add .env.example CHANGELOG.md
git commit -m "docs: add FIX-427 lifecycle hooks to CHANGELOG and .env.example"
```

---

## Task 9: Delete migrated scripts

> Before deleting, verify no other files reference these scripts (besides the docs we already know about in CLAUDE.md).

### Step 9.1 — Check for remaining references

```bash
grep -r "purge_research_contamination\|check_graph_health\|distill_contracts\|analyze_task_types" \
  --include="*.py" --include="*.md" --include="Makefile" . \
  | grep -v "docs/superpowers/" | grep -v "CHANGELOG.md"
```

Expected: only `CLAUDE.md` references these scripts (in the documentation of the soft-label workflow and graph health workflow). No Python code imports them.

If any `.py` file still imports them, fix it before deleting.

### Step 9.2 — Update `CLAUDE.md` references

Read the relevant sections in `CLAUDE.md` and update:
- `uv run python scripts/check_graph_health.py` → note that this is now `PREFLIGHT_ENABLED=1` in `.env`
- `uv run python scripts/analyze_task_types.py --promote` → note that interactive promotion is now done manually; passive logging is in `POSTRUN_ENABLED=1`

Add a note:
```
# Lifecycle hooks (FIX-427)
# Replaces manual scripts — set in .env:
#   PREFLIGHT_ENABLED=1   # health check + auto-purge before run
#   POSTRUN_ENABLED=1     # purge + wiki lint + distill + candidates after run
#   POSTRUN_OPTIMIZE=1    # also run DSPy optimizer after postrun
```

- [ ] Apply targeted Edit to `CLAUDE.md`

### Step 9.3 — Delete the 4 migrated scripts

```bash
git rm scripts/check_graph_health.py scripts/purge_research_contamination.py \
       scripts/distill_contracts.py scripts/analyze_task_types.py
```

### Step 9.4 — Commit deletion

```bash
git commit -m "chore: delete migrated scripts — logic now in agent/maintenance/ — FIX-427"
```

---

## Task 10: Final verification

### Step 10.1 — Run full test suite

```bash
uv run python -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests PASS, no failures

### Step 10.2 — Verify imports work

```bash
uv run python -c "
from agent.maintenance.health import run_health_check
from agent.maintenance.purge import run_purge
from agent.maintenance.distill import run_distill
from agent.maintenance.candidates import log_candidates
from agent.preflight import run_preflight
from agent.postrun import run_postrun
print('All imports OK')
"
```

Expected: `All imports OK`

### Step 10.3 — Verify main.py starts clean

```bash
uv run python -c "import main" 2>&1 | grep -E "Error|Traceback" | head -5
```

Expected: no output (no import errors)

### Step 10.4 — Final commit

```bash
git log --oneline -8
```

Verify 8 commits from this feature are present in order. All done.

---

## Self-Review

**Spec coverage:**
- ✅ Migrate 4 scripts to `agent/maintenance/` — Tasks 1–4
- ✅ Delete originals — Task 9
- ✅ `agent/preflight.py` with health check + auto-purge + wiki integrity — Task 5
- ✅ `agent/postrun.py` with purge + wiki lint + distill + candidates + optimize — Task 6
- ✅ Wire into `main.py` — Task 7
- ✅ Env vars in `.env.example` — Task 8
- ✅ Tests — unit (Tasks 1–4) + integration (Tasks 5–6)
- ✅ FIX-427 label in code and CHANGELOG

**Dedup logic note:** `purge.py` includes the dedup pass that was in `_auto_purge_graph()` (lines 604–635 of main.py). The `deduped_count` field on `PurgeResult` is verified in `test_purge_deduplicates_by_text`.

**Behavior change:** `_auto_purge_graph()` ran unconditionally with fail-open. After this change, purge only runs when `PREFLIGHT_ENABLED=1` or `POSTRUN_ENABLED=1`. Users upgrading should set `POSTRUN_ENABLED=1` in `.env` to preserve the old always-on purge behavior.
