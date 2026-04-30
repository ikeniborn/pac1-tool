"""Tests for FIX-412: _run_pages_lint_pass — pages → graph."""
import json
from unittest.mock import patch, MagicMock
from agent.wiki import _run_pages_lint_pass
from agent.wiki_graph import Graph


SAMPLE_PAGE = """\
## Successful pattern: send email

1. Read /outbox/seq.json to get next id.
2. Write email JSON to /outbox/{id}.json.
3. Increment seq and write back.

## Key rules

- Always read seq.json before writing to determine the correct filename.
- Do not overwrite existing emails.
"""


def _make_graph_module(touched_ids):
    gm = MagicMock()
    gm.merge_updates.return_value = touched_ids
    return gm


def test_pages_lint_pass_calls_merge_updates(tmp_path, monkeypatch):
    """_run_pages_lint_pass reads a page and calls merge_updates with wiki_page tag."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(SAMPLE_PAGE, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq.json before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [],
            "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"

    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    graph_module.merge_updates.assert_called_once()
    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert any("wiki_page" in r.get("tags", []) for r in rules), \
        f"wiki_page tag missing: {rules}"


def test_pages_lint_pass_skips_empty_page(tmp_path, monkeypatch):
    """Empty pages are skipped without calling merge_updates."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text("", encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    graph_module = _make_graph_module([])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=""):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    graph_module.merge_updates.assert_not_called()


def test_pages_lint_pass_skipped_when_autobuild_off(tmp_path, monkeypatch):
    """When _GRAPH_AUTOBUILD is False the pass is a no-op."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(SAMPLE_PAGE, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", False)

    graph_module = _make_graph_module([])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw") as mock_llm:
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    mock_llm.assert_not_called()
    graph_module.merge_updates.assert_not_called()


def test_pages_lint_pass_adds_wiki_mature_tag_for_mature_page(tmp_path, monkeypatch):
    """Nodes from mature pages get the wiki_mature tag."""
    from agent.wiki import _write_page_meta
    meta = {"category": "email", "quality": "mature", "fragment_count": 20,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    meta_header = _write_page_meta(meta)
    mature_page = meta_header + "\n\n" + SAMPLE_PAGE

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(mature_page, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [], "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"
    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert any("wiki_mature" in r.get("tags", []) for r in rules), \
        f"wiki_mature tag missing from rules: {rules}"


def test_pages_lint_pass_no_wiki_mature_for_nascent_page(tmp_path, monkeypatch):
    """Nodes from nascent pages do NOT get the wiki_mature tag."""
    from agent.wiki import _write_page_meta
    meta = {"category": "email", "quality": "nascent", "fragment_count": 2,
            "fragment_ids": [], "last_synthesized": "2026-04-30", "aspects_covered": "workflow_steps"}
    meta_header = _write_page_meta(meta)
    nascent_page = meta_header + "\n\n" + SAMPLE_PAGE

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text(nascent_page, encoding="utf-8")

    monkeypatch.setattr("agent.wiki._PAGES_DIR", pages_dir)
    monkeypatch.setattr("agent.wiki._GRAPH_AUTOBUILD", True)

    fake_deltas_obj = {
        "graph_deltas": {
            "new_rules": [{"text": "read seq before write", "tags": ["email"], "confidence": 0.7}],
            "new_insights": [], "antipatterns": [],
        }
    }
    llm_response = "```json\n" + json.dumps(fake_deltas_obj) + "\n```"
    graph_module = _make_graph_module(["r_abc123"])
    graph_state = Graph()

    with patch("agent.dispatch.call_llm_raw", return_value=llm_response):
        _run_pages_lint_pass(graph_module, graph_state, model="test-model", cfg={})

    call_args = graph_module.merge_updates.call_args[0]
    deltas_arg = call_args[1]
    rules = deltas_arg.get("new_rules", [])
    assert not any("wiki_mature" in r.get("tags", []) for r in rules), \
        f"wiki_mature should NOT be in nascent page rules: {rules}"
