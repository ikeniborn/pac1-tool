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


def test_load_prompt_sql_plan_exists():
    text = load_prompt("sql_plan")
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
