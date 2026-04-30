# tests/test_wiki_quality_header.py
from pathlib import Path
from unittest.mock import patch


def _load_funcs():
    from agent.wiki import load_wiki_patterns, _write_page_meta
    return load_wiki_patterns, _write_page_meta


def _write_page(pages_dir: Path, name: str, meta: dict, body: str) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    _, write_meta = _load_funcs()
    content = write_meta(meta) + "\n\n" + body
    (pages_dir / f"{name}.md").write_text(content, encoding="utf-8")


def test_nascent_page_adds_draft_marker(tmp_path):
    meta = {"category": "email", "quality": "nascent", "fragment_count": 2,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    _write_page(tmp_path / "pages", "email", meta, "## Workflow steps\nStep 1.")

    load_wiki_patterns, _ = _load_funcs()
    with patch("agent.wiki._PAGES_DIR", tmp_path / "pages"), \
         patch("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments"):
        result = load_wiki_patterns("email", include_negatives=False)
    assert "[draft" in result.lower() or "draft" in result


def test_developing_page_no_draft_marker(tmp_path):
    meta = {"category": "email", "quality": "developing", "fragment_count": 7,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    _write_page(tmp_path / "pages", "email", meta, "## Workflow steps\nStep 1.")

    load_wiki_patterns, _ = _load_funcs()
    with patch("agent.wiki._PAGES_DIR", tmp_path / "pages"), \
         patch("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments"):
        result = load_wiki_patterns("email", include_negatives=False)
    assert "draft" not in result.lower()


def test_page_without_meta_treated_as_nascent(tmp_path):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "email.md").write_text("## Workflow steps\nStep 1.", encoding="utf-8")

    load_wiki_patterns, _ = _load_funcs()
    with patch("agent.wiki._PAGES_DIR", tmp_path / "pages"), \
         patch("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments"):
        result = load_wiki_patterns("email", include_negatives=False)
    assert "draft" in result.lower()
