# tests/test_wiki_incremental.py
from pathlib import Path
from unittest.mock import patch
from agent.wiki import run_wiki_lint, _read_page_meta_from_content


def _write_fragment(frag_dir: Path, name: str, content: str) -> None:
    frag_dir.mkdir(parents=True, exist_ok=True)
    (frag_dir / name).write_text(content, encoding="utf-8")


FRAGMENT_CONTENT = (
    "---\ntask_id: t01\ntask_type: email\noutcome: OUTCOME_OK\ndate: 2026-04-30\n"
    "task: 'send email'\n---\n\nDONE OPS:\n- read /contacts/c.json\n"
    "- write /outbox/1.json\n\nSTEP FACTS:\n- read: /contacts/c.json → found\n"
)


def test_lint_writes_page_with_meta_header(tmp_path, monkeypatch):
    """After lint, the page must contain a <!-- wiki:meta --> block."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    archive_dir = tmp_path / "archive" / "email"
    pages_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Step 1: read contact.\nStep 2: write outbox."):
        run_wiki_lint(model="test-model", cfg={})

    page_path = pages_dir / "email.md"
    assert page_path.exists(), "email.md was not written"
    content = page_path.read_text()
    assert "<!-- wiki:meta" in content, "meta header missing"
    assert "quality:" in content
    assert "fragment_count:" in content


def test_lint_records_fragment_id_in_meta(tmp_path, monkeypatch):
    """Processed fragment stem appears in fragment_ids of the page meta."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Merged content here."):
        run_wiki_lint(model="test-model", cfg={})

    page_path = pages_dir / "email.md"
    content = page_path.read_text()
    meta = _read_page_meta_from_content(content)
    assert "t01_20260430T120000Z" in meta["fragment_ids"]


def test_lint_quality_nascent_for_single_fragment(tmp_path, monkeypatch):
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Content."):
        run_wiki_lint(model="test-model", cfg={})

    content = (pages_dir / "email.md").read_text()
    meta = _read_page_meta_from_content(content)
    assert meta["quality"] == "nascent"


def test_lint_archives_fragments_after_synthesis(tmp_path, monkeypatch):
    """Fragments are moved to archive/ after processing."""
    frag_dir = tmp_path / "fragments" / "email"
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)

    _write_fragment(frag_dir, "t01_20260430T120000Z.md", FRAGMENT_CONTENT)

    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    with patch("agent.dispatch.call_llm_raw", return_value="Content."):
        run_wiki_lint(model="test-model", cfg={})

    assert not (frag_dir / "t01_20260430T120000Z.md").exists(), "fragment not archived"
    assert (tmp_path / "archive" / "email" / "t01_20260430T120000Z.md").exists()
