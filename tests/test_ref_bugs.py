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


# ── Bug 2: _extract_sku_refs store_id ────────────────────────────────────────

def test_extract_sku_refs_store_id_only():
    """Bug t17: store_id column must produce /proc/stores/{id}.json."""
    results = ["store_id\nstore_vienna_praterstern\n"]
    refs = _extract_sku_refs([], results)
    assert refs == ["/proc/stores/store_vienna_praterstern.json"]


def test_extract_sku_refs_sku_and_store_id():
    """Inventory query has both sku and store_id — both refs must appear."""
    results = ["store_id,sku,available_today\nstore_vienna_praterstern,PLB-2GJZ9R7K,1\n"]
    refs = _extract_sku_refs([], results)
    assert "/proc/catalog/PLB-2GJZ9R7K.json" in refs
    assert "/proc/stores/store_vienna_praterstern.json" in refs
