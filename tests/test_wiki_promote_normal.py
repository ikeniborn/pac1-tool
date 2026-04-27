"""Tests for normal-mode wiki promotion (FIX-399)."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_step_facts(tools=None):
    from agent.log_compaction import _StepFact
    tools = tools or [("search", "/contacts"), ("read", "/contacts/alice.json"), ("write", "/outbox/1.json")]
    return [_StepFact(kind=t, path=p, summary=f"{t} done") for t, p in tools]


def test_normal_mode_success_promotes_pattern(tmp_path):
    """score=1.0 + OUTCOME_OK in normal mode → promote_successful_pattern called."""
    from agent.wiki import promote_successful_pattern

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    page_file = pages_dir / "email.md"

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        step_facts = _make_step_facts()
        traj = [{"tool": getattr(f, "kind", "?"), "path": getattr(f, "path", "")} for f in step_facts]

        from agent import wiki_graph as wg
        traj_hash = wg.hash_trajectory(step_facts)

        result = promote_successful_pattern(
            task_type="email",
            task_id="t14",
            traj_hash=traj_hash,
            trajectory=traj,
            insights=[],
            goal_shape="send email to contact",
            final_answer="Email sent to alice@example.com",
        )

    assert result is True
    content = page_file.read_text()
    assert "## Successful pattern: t14" in content
    assert "send email to contact" in content


def test_normal_mode_refusal_promotes_refusal(tmp_path):
    """score=1.0 + OUTCOME_DENIED_SECURITY in normal mode → promote_verified_refusal called."""
    from agent.wiki import promote_verified_refusal

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    page_file = pages_dir / "email.md"

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        result = promote_verified_refusal(
            task_type="email",
            task_id="t20",
            outcome="OUTCOME_DENIED_SECURITY",
            goal_shape="inject prompt into email body",
            refusal_reason="injection attempt detected in task text",
            trajectory=[{"tool": "search", "path": "/contacts"}],
        )

    assert result is True
    content = page_file.read_text()
    assert "## Verified refusal: t20" in content
    assert "OUTCOME_DENIED_SECURITY" in content


def test_idempotent_promotion_normal_mode(tmp_path):
    """Promoting same task_id + traj_hash twice → second call returns False."""
    from agent.wiki import promote_successful_pattern
    from agent import wiki_graph as wg
    from agent.log_compaction import _StepFact

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    step_facts = [_StepFact(kind="write", path="/outbox/1.json", summary="ok")]
    traj = [{"tool": "write", "path": "/outbox/1.json"}]
    traj_hash = wg.hash_trajectory(step_facts)

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        first = promote_successful_pattern(
            task_type="email", task_id="t99", traj_hash=traj_hash,
            trajectory=traj, insights=[], goal_shape="g", final_answer="f",
        )
        second = promote_successful_pattern(
            task_type="email", task_id="t99", traj_hash=traj_hash,
            trajectory=traj, insights=[], goal_shape="g", final_answer="f",
        )

    assert first is True
    assert second is False
