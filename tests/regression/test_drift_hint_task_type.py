"""FIX-377: drift hints must reference patterns from the same task_type
(and, when reflector provided a goal_shape, only patterns with overlapping
goal_shape). Without this filter, an email task got advised to align its
tool-sequence with a t35-lookup pattern — structurally meaningless.
"""
from types import SimpleNamespace

from agent.researcher import _detect_drift, _detect_drift_lcs


def _f(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind)


def test_tc1_same_task_type_pattern_used():
    """TC1: mixed task_types in patterns — only same-type pattern reached."""
    step_facts = [_f("read"), _f("write"), _f("report_completion")]
    patterns = [
        {
            "task_id": "t10",
            "task_type": "email",
            # different prefix from current → must be referenced by drift hint
            "trajectory_tools": ["search", "list", "read"],
            "goal_shape": "send email about report",
        },
        {
            "task_id": "t35",
            "task_type": "default",
            # closer prefix to current — but cross-task, must be ignored
            "trajectory_tools": ["read", "write", "report_completion"],
            "goal_shape": "lookup file content",
        },
    ]
    hint = _detect_drift(step_facts, patterns, prefix_len=3, task_type="email")
    assert hint, "expected a drift hint when same-type pattern differs"
    assert "t10" in hint
    assert "t35" not in hint


def test_tc2_no_same_type_patterns_returns_none():
    """TC2: task_type=lookup, no patterns of that type → empty hint."""
    step_facts = [_f("read"), _f("write")]
    patterns = [
        {
            "task_id": "t10",
            "task_type": "email",
            "trajectory_tools": ["search", "list"],
            "goal_shape": "send email",
        },
    ]
    hint = _detect_drift(step_facts, patterns, prefix_len=3, task_type="lookup")
    assert hint == ""


def test_tc3_goal_shape_jaccard_filter():
    """TC3: two same-type patterns; only goal-shape-similar one survives."""
    step_facts = [_f("read"), _f("write"), _f("report_completion")]
    patterns = [
        {
            "task_id": "t100",
            "task_type": "email",
            # very different goal_shape — Jaccard < 0.3 → filtered out
            "trajectory_tools": ["read", "write", "report_completion"],
            "goal_shape": "schedule meeting timezone calendar",
        },
        {
            "task_id": "t101",
            "task_type": "email",
            # matching goal_shape tokens with current → kept
            "trajectory_tools": ["search", "list", "read"],
            "goal_shape": "send email reply customer",
        },
    ]
    hint = _detect_drift(
        step_facts, patterns, prefix_len=3,
        task_type="email", goal_shape="send email reply",
    )
    assert hint, "expected drift hint from goal-shape-matching pattern"
    assert "t101" in hint
    assert "t100" not in hint


def test_tc4_backward_compat_pattern_without_task_type():
    """TC4: legacy patterns without task_type field → kept (default behaviour)."""
    step_facts = [_f("read"), _f("write")]
    patterns = [
        {
            "task_id": "t99",
            # no task_type key — must not crash, must not be filtered out
            "trajectory_tools": ["search", "list"],
            "goal_shape": "anything",
        },
    ]
    hint = _detect_drift(step_facts, patterns, prefix_len=2, task_type="email")
    assert hint
    assert "t99" in hint


def test_lcs_variant_applies_same_filter():
    """_detect_drift_lcs (FIX-376h) inherits the same task-type filter."""
    step_facts = [_f("read"), _f("write"), _f("report_completion")]
    # All patterns are cross-task → after filter, none left → empty hint.
    patterns = [
        {
            "task_id": "t35",
            "task_type": "default",
            "trajectory_tools": ["search", "list", "tree", "read"],
            "goal_shape": "lookup",
        },
    ]
    hint = _detect_drift_lcs(
        step_facts, patterns, lcs_min=0.4, task_type="email",
    )
    assert hint == ""
