from unittest.mock import patch
from agent.wiki import _llm_synthesize_aspects, _assemble_page_from_sections


ASPECTS = [
    {"id": "workflow_steps", "header": "Workflow steps", "prompt": "Proven steps"},
    {"id": "pitfalls",       "header": "Key pitfalls",   "prompt": "Risks"},
]

NEW_FRAGS = ["---\noutcome: OUTCOME_OK\n---\n\nDONE OPS:\n- read /contacts/c.json\n"]


def test_assemble_page_from_sections_includes_all_aspects():
    meta = {
        "category": "email", "quality": "nascent", "fragment_count": 1,
        "fragment_ids": ["t01_ts"], "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps,pitfalls",
    }
    sections = {"workflow_steps": "Step 1: read contact.", "key_pitfalls": "Avoid X."}
    result = _assemble_page_from_sections(meta, sections, ASPECTS)
    assert "<!-- wiki:meta" in result
    assert "## Workflow steps" in result
    assert "Step 1: read contact." in result
    assert "## Key pitfalls" in result
    assert "Avoid X." in result


def test_assemble_page_preserves_promoted_sections():
    meta = {
        "category": "email", "quality": "developing", "fragment_count": 6,
        "fragment_ids": [], "last_synthesized": "2026-04-30",
        "aspects_covered": "workflow_steps",
    }
    sections = {
        "workflow_steps": "Step 1: do this.",
        "successful_pattern_t01_2026_04_01": "trajectory details here",
    }
    result = _assemble_page_from_sections(meta, sections, ASPECTS)
    assert "## Workflow steps" in result
    assert "trajectory details here" in result


def test_llm_synthesize_aspects_calls_llm_per_aspect():
    responses = ["merged workflow content", "merged pitfalls content"]

    with patch("agent.dispatch.call_llm_raw", side_effect=responses) as mock_llm:
        result_sections = _llm_synthesize_aspects(
            existing_sections={"workflow_steps": "old step", "key_pitfalls": "old risk"},
            new_entries=NEW_FRAGS,
            aspects=ASPECTS,
            model="test-model",
            cfg={},
        )

    assert mock_llm.call_count == 2
    assert result_sections["workflow_steps"] == "merged workflow content"
    assert result_sections["key_pitfalls"] == "merged pitfalls content"


def test_llm_synthesize_aspects_no_model_returns_concat():
    result_sections = _llm_synthesize_aspects(
        existing_sections={"workflow_steps": "old"},
        new_entries=["new fragment"],
        aspects=ASPECTS,
        model="",
        cfg={},
    )
    assert "old" in result_sections.get("workflow_steps", "")
    assert "new fragment" in result_sections.get("workflow_steps", "")


def test_llm_synthesize_aspects_preserves_existing_on_empty_llm_response():
    with patch("agent.dispatch.call_llm_raw", return_value=""):
        result_sections = _llm_synthesize_aspects(
            existing_sections={"workflow_steps": "must survive"},
            new_entries=["fragment"],
            aspects=ASPECTS,
            model="test-model",
            cfg={},
        )
    assert result_sections["workflow_steps"] == "must survive"
