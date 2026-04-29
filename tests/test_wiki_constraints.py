# tests/test_wiki_constraints.py
import textwrap
from unittest.mock import patch


def _load():
    from agent.wiki import load_contract_constraints
    return load_contract_constraints


def test_parse_single_constraint(tmp_path):
    """Single constraint block returns one dict with id and rule."""
    page = tmp_path / "queue.md"
    page.write_text(textwrap.dedent("""\
        ## Some patterns

        content here

        ---

        ## Contract constraints

        <!-- constraint: no_vault_docs_write -->
        **ID:** no_vault_docs_write
        **Rule:** Plan MUST NOT write result.txt.
    """))
    fn = _load()
    with patch("agent.wiki._PAGES_DIR", tmp_path):
        result = fn("queue")
    assert len(result) == 1
    assert result[0]["id"] == "no_vault_docs_write"
    assert "result.txt" in result[0]["rule"]


def test_parse_multiple_constraints(tmp_path):
    """Two constraint blocks return two dicts."""
    page = tmp_path / "queue.md"
    page.write_text(textwrap.dedent("""\
        ## Contract constraints

        <!-- constraint: no_vault_docs_write -->
        **ID:** no_vault_docs_write
        **Rule:** No vault docs writes.

        <!-- constraint: no_scope_overreach -->
        **ID:** no_scope_overreach
        **Rule:** Deletes only from explicit paths.
    """))
    fn = _load()
    with patch("agent.wiki._PAGES_DIR", tmp_path):
        result = fn("queue")
    assert len(result) == 2
    ids = [c["id"] for c in result]
    assert "no_vault_docs_write" in ids
    assert "no_scope_overreach" in ids


def test_missing_section_returns_empty(tmp_path):
    """Page without ## Contract constraints returns []."""
    page = tmp_path / "queue.md"
    page.write_text("## Some patterns\ncontent\n")
    fn = _load()
    with patch("agent.wiki._PAGES_DIR", tmp_path):
        result = fn("queue")
    assert result == []


def test_missing_page_returns_empty(tmp_path):
    """Non-existent page returns [] (fail-open)."""
    fn = _load()
    with patch("agent.wiki._PAGES_DIR", tmp_path):
        result = fn("nonexistent_type")
    assert result == []


def test_unknown_task_type_returns_empty(tmp_path):
    """Task type with no mapped page returns []."""
    fn = _load()
    with patch("agent.wiki._PAGES_DIR", tmp_path):
        result = fn("unknown_type_xyz")
    assert result == []
