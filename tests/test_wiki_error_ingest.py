"""Tests for FIX-413: _ingest_error_fragments without LLM."""
from pathlib import Path
from agent.wiki import _ingest_error_fragments


def _write_error_frag(tmp_path: Path, category: str, filename: str, content: str) -> Path:
    d = tmp_path / "errors" / category
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(content, encoding="utf-8")
    return p


DEAD_END_FRAGMENT = """\
---
task_id: t11
task_type: email
outcome: OUTCOME_NONE_CLARIFICATION
date: 2026-04-29
task: 'Write email to sam@example.com'
---

DONE OPS:
(none)

STEP FACTS:
- stall:  → You have taken 6 steps without writing

## Dead end: t11
Outcome: OUTCOME_NONE_CLARIFICATION
What failed:
- stall(/outbox): You have taken 6 steps without writing anything meaningful
"""

LEGACY_FRAGMENT = """\
---
task_id: t09
task_type: email
outcome: OUTCOME_FAIL
date: 2026-04-28
task: 'some task'
---

STEP FACTS:
- stall:  → repeated search with no results found
"""


def test_ingest_dead_end_format(tmp_path, monkeypatch):
    """Dead-end block format produces antipattern item."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    _write_error_frag(tmp_path, "email", "t11_001.md", DEAD_END_FRAGMENT)

    items = _ingest_error_fragments("email")
    assert len(items) == 1
    item = items[0]
    assert item["confidence"] == 0.4
    assert "email" in item["tags"]
    assert len(item["text"]) > 5
    assert "sam@example.com" not in item["text"]


def test_ingest_legacy_format(tmp_path, monkeypatch):
    """Legacy fragment (no dead-end block) falls back to outcome+stall."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    _write_error_frag(tmp_path, "email", "t09_001.md", LEGACY_FRAGMENT)

    items = _ingest_error_fragments("email")
    assert len(items) == 1
    assert items[0]["confidence"] == 0.4


def test_ingest_respects_n_limit(tmp_path, monkeypatch):
    """Only last N files by mtime are processed."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    for i in range(15):
        _write_error_frag(tmp_path, "email", f"t{i:02d}_001.md", DEAD_END_FRAGMENT)

    items = _ingest_error_fragments("email", n=5)
    assert len(items) <= 5


def test_ingest_missing_category_returns_empty(tmp_path, monkeypatch):
    """Missing category directory returns empty list without error."""
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path)
    items = _ingest_error_fragments("nonexistent_category")
    assert items == []
