# tests/test_evaluator_wiki_quality.py
from pathlib import Path
from agent.evaluator import _load_reference_patterns
from agent.wiki import _write_page_meta


def _make_page(pages_dir: Path, name: str, quality: str, fragment_count: int) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    meta = {"category": name, "quality": quality, "fragment_count": fragment_count,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    body = "## Workflow steps\n" + ("Step X.\n" * 50)  # ~50 lines of content
    content = _write_page_meta(meta) + "\n\n" + body
    (pages_dir / f"{name}.md").write_text(content, encoding="utf-8")


def test_nascent_page_truncated_to_short_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", True)
    _make_page(tmp_path / "pages", "email", "nascent", 2)

    result = _load_reference_patterns("email")
    assert len(result) <= 600, f"nascent page should be truncated to ≤600 chars, got {len(result)}"


def test_mature_page_has_higher_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.wiki._PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr("agent.wiki._FRAGMENTS_DIR", tmp_path / "fragments")
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", True)
    _make_page(tmp_path / "pages", "email", "mature", 20)

    result = _load_reference_patterns("email")
    # Mature gets up to 4000 chars — 50 lines of "Step X.\n" is ~500 chars, fits fully
    assert len(result) > 0
    assert "Step X." in result


def test_wiki_eval_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr("agent.evaluator._WIKI_EVAL_ENABLED", False)
    result = _load_reference_patterns("email")
    assert result == ""
