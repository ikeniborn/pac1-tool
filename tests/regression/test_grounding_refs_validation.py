"""FIX-377 regression tests — grounding_refs validation hard-gate.

Covers `agent.evaluator.validate_grounding_refs` and its integration as a
pre-check in `evaluate_completion()`. The gate rejects any agent message
that names a vault ID (`<2-5 letters>_<2-4 digits>`) without including a
matching path in `grounding_refs`.
"""
import types
from unittest.mock import patch


def _make_report(message="", grounding_refs=None, outcome="OUTCOME_OK"):
    return types.SimpleNamespace(
        outcome=outcome,
        message=message,
        completed_steps_laconic=[],
        done_operations=[],
        grounding_refs=grounding_refs or [],
    )


def _validate():
    from agent.evaluator import validate_grounding_refs
    return validate_grounding_refs


# ---------------------------------------------------------------------------
# Direct tests of validate_grounding_refs
# ---------------------------------------------------------------------------

def test_tc1_id_in_message_no_refs_rejected():
    fn = _validate()
    ok, issue = fn(_make_report(message="The followup is for acct_009", grounding_refs=[]))
    assert not ok
    assert "acct_009" in issue


def test_tc2_single_id_covered_by_ref_approved():
    fn = _validate()
    ok, issue = fn(_make_report(
        message="Followup drafted for acct_009.",
        grounding_refs=["accounts/acct_009.json"],
    ))
    assert ok
    assert issue == ""


def test_tc3_multiple_ids_partial_coverage_rejected():
    fn = _validate()
    ok, issue = fn(_make_report(
        message="Linked acct_009 and mgr_002 together.",
        grounding_refs=["accounts/acct_009.json"],
    ))
    assert not ok
    assert "mgr_002" in issue
    assert "acct_009" not in issue  # only the missing one is reported


def test_tc4_multiple_ids_all_covered_approved():
    fn = _validate()
    ok, issue = fn(_make_report(
        message="Linked acct_009 and mgr_002 together.",
        grounding_refs=["accounts/acct_009.json", "contacts/mgr_002.json"],
    ))
    assert ok
    assert issue == ""


def test_tc5_message_without_id_pattern_skipped():
    fn = _validate()
    ok, issue = fn(_make_report(
        message="Task completed. No specific entity referenced.",
        grounding_refs=[],
    ))
    assert ok
    assert issue == ""


def test_tc6_case_insensitive_match():
    fn = _validate()
    ok, issue = fn(_make_report(
        message="Followup ACCT_009 done.",
        grounding_refs=["accounts/acct_009.json"],
    ))
    assert ok
    assert issue == ""


# ---------------------------------------------------------------------------
# Integration: evaluate_completion() rejects without calling LLM when refs missing
# ---------------------------------------------------------------------------

def test_evaluate_completion_pre_check_rejects_missing_refs():
    """When grounding_refs are missing, evaluate_completion short-circuits to
    reject without invoking the DSPy/LLM path."""
    from agent.evaluator import evaluate_completion

    report = _make_report(
        message="Sent followup for acct_009.",
        grounding_refs=[],
    )
    # Patch the LLM call so we can assert it's never reached.
    with patch("agent.dspy_lm.call_llm_raw") as mock_llm:
        verdict = evaluate_completion(
            task_text="Send a followup for the customer.",
            task_type="email",
            report=report,
            done_ops=["WRITTEN: outbox/followup.md"],
            digest_str="",
            model="any-model",
            cfg={},
            skepticism="mid",
            efficiency="mid",
        )
    assert mock_llm.call_count == 0
    assert verdict.approved is False
    assert any("acct_009" in i for i in verdict.issues)
    assert "acct_009" in verdict.correction_hint
