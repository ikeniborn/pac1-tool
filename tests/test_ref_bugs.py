# tests/test_ref_bugs.py
from unittest.mock import MagicMock, patch

from agent.json_extract import _obj_mutation_tool
from agent.pipeline import _build_answer_user_msg, _extract_sku_refs, run_pipeline
from agent.prephase import PrephaseResult


def _make_pre():
    return PrephaseResult(
        agents_md_content="AGENTS",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(id INT)",
    )


# ── Bug 3 / Level 1: _obj_mutation_tool ──────────────────────────────────────

def test_obj_mutation_tool_function_as_string():
    """Bug t21: 'function' field is a string — must not crash, must return None."""
    obj = {"function": "checkout", "args": {}}
    assert _obj_mutation_tool(obj) is None


def test_obj_mutation_tool_function_as_dict_with_mutation_tool():
    """Normal case: 'function' is a dict with a valid mutation tool name."""
    obj = {"function": {"tool": "write", "path": "/x"}}
    assert _obj_mutation_tool(obj) == "write"


def test_obj_mutation_tool_top_level_tool():
    """Top-level 'tool' key wins regardless of 'function'."""
    obj = {"tool": "delete"}
    assert _obj_mutation_tool(obj) == "delete"


def test_obj_mutation_tool_no_mutation():
    """Read-type tool returns None."""
    obj = {"tool": "read"}
    assert _obj_mutation_tool(obj) is None
