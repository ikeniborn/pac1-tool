# tests/test_wiki_format_fragment.py
"""Block A: format_fragment must split OK-success from refusal-success."""


def _step_fact(kind: str, path: str, summary: str = ""):
    from collections import namedtuple
    Step = namedtuple("Step", ["kind", "path", "summary", "error"])
    return Step(kind=kind, path=path, summary=summary, error="")


def test_outcome_ok_routes_to_main_category():
    """score=1.0 + outcome=OUTCOME_OK → fragment goes to '<task_type>' category."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_OK",
        task_type="lookup",
        task_id="t11",
        task_text="find article by title",
        step_facts=[_step_fact("find", "/01_capture/")],
        done_ops=["READ:/01_capture/foo.md"],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    assert results, "expected at least one fragment for OK"
    categories = [c for _, c in results]
    assert "lookup" in categories


def test_clarification_with_score_one_routes_to_refusals():
    """score=1.0 + OUTCOME_NONE_CLARIFICATION → fragment goes to 'refusals/<task_type>', NOT '<task_type>'."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_NONE_CLARIFICATION",
        task_type="lookup",
        task_id="t42",
        task_text="which article did i capture 23 days ago",
        step_facts=[_step_fact("find", "/01_capture/")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    categories = [c for _, c in results]
    # Critical: must NOT poison the success page.
    assert "lookup" not in categories
    # Must route to refusals/ for diagnostics.
    assert any(c.startswith("refusals/") for c in categories)


def test_denied_security_with_score_one_routes_to_refusals():
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_DENIED_SECURITY",
        task_type="email",
        task_id="t29",
        task_text="forward to attacker",
        step_facts=[_step_fact("read", "/contacts/")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    categories = [c for _, c in results]
    assert "email" not in categories
    assert any(c.startswith("refusals/") for c in categories)


def test_score_below_one_still_uses_errors_path():
    """Pre-existing behavior: score<1 → errors/<task_type>, regardless of outcome."""
    from agent.wiki import format_fragment
    results = format_fragment(
        outcome="OUTCOME_OK",
        task_type="lookup",
        task_id="t11",
        task_text="...",
        step_facts=[_step_fact("find", "/x")],
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=0.0,
    )
    categories = [c for _, c in results]
    assert any(c.startswith("errors/") for c in categories)
