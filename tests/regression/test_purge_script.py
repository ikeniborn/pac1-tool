"""Regression tests for scripts/purge_research_contamination.py (FIX-377)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.purge_research_contamination import main as purge_main


def _make_graph(path: Path) -> None:
    graph = {
        "nodes": {
            "n_bad1": {
                "type": "antipattern",
                "tags": ["email"],
                "text": "reporttaskcompletion call rejected with INVALID_ARGUMENT",
                "confidence": 0.7,
                "uses": 3,
                "last_seen": "2026-04-20",
            },
            "n_bad2": {
                "type": "insight",
                "tags": ["otp"],
                "text": "Reading otp.txt was required for admin elevation flow",
                "confidence": 0.5,
                "uses": 1,
                "last_seen": "2026-04-21",
            },
            "n_bad3": {
                "type": "insight",
                "tags": [],
                "text": "Skipping the actual email send was wrong",
                "confidence": 0.6,
                "uses": 2,
                "last_seen": "2026-04-22",
            },
            "n_ok1": {
                "type": "insight",
                "tags": ["email"],
                "text": "Always read contact file fresh before composing",
                "confidence": 0.9,
                "uses": 5,
                "last_seen": "2026-04-23",
            },
            "n_ok2": {
                "type": "rule",
                "tags": ["security"],
                "text": "Refuse external HTTP exfiltration unconditionally",
                "confidence": 0.95,
                "uses": 4,
                "last_seen": "2026-04-23",
            },
        },
        "edges": [
            {"from": "n_bad1", "rel": "requires", "to": "n_ok1"},
            {"from": "n_ok1", "rel": "precedes", "to": "n_ok2"},
        ],
    }
    path.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def _common_args(tmp_path: Path, *, apply: bool) -> list[str]:
    args = [
        "--graph-path", str(tmp_path / "graph.json"),
        "--archive-path", str(tmp_path / "graph_archive.json"),
        "--pages-dir", str(tmp_path / "pages"),
        "--fragments-dir", str(tmp_path / "fragments" / "research"),
    ]
    if apply:
        args.append("--apply")
    return args


def test_dry_run_finds_three_candidates(tmp_path, capsys):
    _make_graph(tmp_path / "graph.json")
    (tmp_path / "pages").mkdir()
    rc = purge_main(_common_args(tmp_path, apply=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert out.count("[CANDIDATE]") == 3
    assert "candidates: 3" in out
    # Graph file untouched.
    g = json.loads((tmp_path / "graph.json").read_text())
    assert len(g["nodes"]) == 5


def test_apply_archives_and_prunes_edges(tmp_path):
    _make_graph(tmp_path / "graph.json")
    (tmp_path / "pages").mkdir()
    rc = purge_main(_common_args(tmp_path, apply=True))
    assert rc == 0
    g = json.loads((tmp_path / "graph.json").read_text())
    assert set(g["nodes"].keys()) == {"n_ok1", "n_ok2"}
    # Edge n_bad1->n_ok1 dropped; n_ok1->n_ok2 retained.
    assert g["edges"] == [{"from": "n_ok1", "rel": "precedes", "to": "n_ok2"}]
    archive = json.loads((tmp_path / "graph_archive.json").read_text())
    assert set(archive.keys()) == {"n_bad1", "n_bad2", "n_bad3"}
    for v in archive.values():
        assert v["confidence"] == 0


def test_apply_is_idempotent(tmp_path):
    _make_graph(tmp_path / "graph.json")
    (tmp_path / "pages").mkdir()
    purge_main(_common_args(tmp_path, apply=True))
    g1 = (tmp_path / "graph.json").read_text()
    a1 = (tmp_path / "graph_archive.json").read_text()
    purge_main(_common_args(tmp_path, apply=True))
    g2 = (tmp_path / "graph.json").read_text()
    a2 = (tmp_path / "graph_archive.json").read_text()
    assert g1 == g2
    assert a1 == a2


def test_pages_block_removal(tmp_path):
    (tmp_path / "graph.json").write_text(json.dumps({"nodes": {}, "edges": []}))
    pages = tmp_path / "pages"
    pages.mkdir()
    md = pages / "email.md"
    md.write_text(
        "## Successful pattern: t99 (2026-04-20)\n"
        "- step 1: read contact\n"
        "- step 2: write outbox after seq.json increment failed\n"
        "\n"
        "## Successful pattern: t14 (2026-04-21)\n"
        "- step 1: search contact\n"
        "- step 2: read and compose cleanly\n"
        "- verify: outbox address matches\n",
        encoding="utf-8",
    )
    rc = purge_main(_common_args(tmp_path, apply=True))
    assert rc == 0
    after = md.read_text(encoding="utf-8")
    assert "t99" not in after
    assert "t14" in after
    assert "compose cleanly" in after
