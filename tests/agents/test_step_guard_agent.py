"""Tests for StepGuardAgent contract validation."""

from __future__ import annotations

from agent.agents.step_guard_agent import StepGuardAgent
from agent.contract_models import Contract
from agent.contracts import StepGuardRequest


def _make_contract(plan_steps=None):
    """Helper to create a test Contract."""
    return Contract(
        plan_steps=plan_steps or ["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
    )


def test_no_deviation_returns_valid():
    """Test that an operation matching the plan returns valid=True."""
    agent = StepGuardAgent()
    req = StepGuardRequest(
        step_index=4,
        tool_name="Req_Write",
        tool_args={"path": "/outbox/1.json", "content": "{}"},
        contract=_make_contract(["write /outbox/"]),
    )
    result = agent.check(req)
    assert result.valid is True
    assert result.deviation is None


def test_unexpected_delete_returns_deviation():
    """Test that an unexpected delete operation returns valid=False with deviation."""
    agent = StepGuardAgent()
    req = StepGuardRequest(
        step_index=5,
        tool_name="Req_Delete",
        tool_args={"path": "/important/file.md"},
        contract=_make_contract(["write /outbox/1.json"]),
    )
    result = agent.check(req)
    assert result.valid is False
    assert result.deviation is not None


def test_no_contract_always_valid():
    """Test that check_optional without a contract always returns valid=True."""
    agent = StepGuardAgent()
    result = agent.check_optional(
        step_index=5,
        tool_name="Req_Delete",
        tool_args={"path": "/important/file.md"},
        done_operations=["DELETED: /important/file.md"],
        contract=None,
    )
    assert result.valid is True
