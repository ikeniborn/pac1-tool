# tests/test_prompt_loader.py
from agent.prompt import load_prompt, build_system_prompt


def test_load_prompt_core():
    text = load_prompt("core")
    assert "Output PURE JSON" in text


def test_load_prompt_lookup():
    text = load_prompt("lookup")
    assert "grounding_refs" in text.lower() or "MANDATORY" in text


def test_load_prompt_unknown_returns_empty():
    assert load_prompt("nonexistent_block_xyz") == ""


def test_build_system_prompt_lookup_contains_core_and_catalogue():
    prompt = build_system_prompt("lookup")
    # Core block content
    assert "Output PURE JSON" in prompt
    # Catalogue block content
    assert "CATALOGUE STRATEGY" in prompt


def test_build_system_prompt_fallback_to_default_for_unknown():
    prompt = build_system_prompt("unknown_type_xyz")
    assert "Output PURE JSON" in prompt


def test_load_prompt_sdd_exists():
    text = load_prompt("sdd")
    assert len(text) > 50


def test_load_prompt_learn_exists():
    text = load_prompt("learn")
    assert len(text) > 50


def test_load_prompt_answer_exists():
    text = load_prompt("answer")
    assert len(text) > 50


def test_load_prompt_pipeline_evaluator_exists():
    text = load_prompt("pipeline_evaluator")
    assert len(text) > 50


def test_core_has_ecom_role():
    text = load_prompt("core")
    assert "e-commerce" in text.lower() or "ecom" in text.lower()


def test_core_has_exec_tool():
    text = load_prompt("core")
    assert "/bin/sql" in text


def test_core_has_no_vault_tools():
    text = load_prompt("core")
    for vault_tool in ('"list"', '"write"', '"delete"', '"find"', '"search"', '"tree"', '"move"', '"mkdir"'):
        assert vault_tool not in text, f"vault tool {vault_tool} still in core.md"


def test_lookup_has_sql_gate():
    text = load_prompt("lookup")
    assert "/bin/sql" in text


def test_lookup_has_no_vault_file_tools():
    text = load_prompt("lookup")
    for vault_tool in ("tree", "find", "search", "list"):
        assert vault_tool not in text.lower(), f"vault tool '{vault_tool}' still in lookup.md"


def test_email_prompt_not_loaded():
    assert load_prompt("email") == ""


def test_inbox_prompt_not_loaded():
    assert load_prompt("inbox") == ""


def test_task_blocks_has_no_email_inbox():
    from agent.prompt import _TASK_BLOCKS
    assert "email" not in _TASK_BLOCKS
    assert "inbox" not in _TASK_BLOCKS
    assert "queue" not in _TASK_BLOCKS
