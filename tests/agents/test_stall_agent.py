"""Tests for StallAgent."""

import pytest


def _make_req(fingerprints=None, steps_without_write=0, error_counts=None):
    """Helper to construct a StallRequest for testing."""
    from agent.contracts import StallRequest
    return StallRequest(
        step_index=steps_without_write,
        fingerprints=fingerprints or [],
        error_counts=error_counts or {},
        steps_without_write=steps_without_write,
    )


def test_no_stall_returns_not_detected():
    """No stall detected for low step count."""
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=2))
    assert result.detected is False
    assert result.hint is None


def test_repeated_fingerprint_detected():
    """Repeated same fingerprint triggers stall detection."""
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(
        fingerprints=["Req_Read:/notes/x.md:ok"] * 3,
        steps_without_write=2,
    ))
    assert result.detected is True
    assert result.hint is not None
    assert "Req_Read" in result.hint


def test_exploration_stall_at_6_steps():
    """Exploration stall detected at 6 steps without write."""
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=6))
    assert result.detected is True
    assert result.hint is not None


def test_escalation_at_12_steps():
    """Escalation level increases at 12 steps and hint contains ESCALATION."""
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=12))
    assert result.detected is True
    assert result.escalation_level >= 2
    assert "ESCALATION" in (result.hint or "")


def test_escalation_at_18_steps():
    """Escalation level reaches 3 at 18 steps."""
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=18))
    assert result.detected is True
    assert result.escalation_level >= 3
    assert "ESCALATION" in (result.hint or "")
