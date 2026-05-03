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
    assert "n1" in data["nodes"]
    assert "n2" not in data["nodes"]
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
