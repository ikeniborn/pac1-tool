# tests/test_contract_models.py
import pytest
from agent.contract_models import Contract, EvaluatorResponse, ExecutorProposal


def test_executor_proposal_defaults():
    p = ExecutorProposal(
        plan_steps=["list /", "read /file.txt"],
        expected_outcome="file updated",
        required_tools=["list", "read", "write"],
        open_questions=[],
        agreed=False,
    )
    assert p.plan_steps == ["list /", "read /file.txt"]
    assert p.agreed is False


def test_executor_proposal_requires_plan_steps():
    with pytest.raises(Exception):
        ExecutorProposal()  # type: ignore — missing required fields


def test_evaluator_response_counter_proposal_optional():
    r = EvaluatorResponse(
        success_criteria=["file written"],
        failure_conditions=["no file written"],
        required_evidence=["/outbox/1.json"],
        objections=[],
        counter_proposal=None,
        agreed=True,
    )
    assert r.counter_proposal is None
    assert r.agreed is True


def test_contract_is_default_flag():
    c = Contract(
        plan_steps=["step 1"],
        success_criteria=["criterion 1"],
        required_evidence=[],
        failure_conditions=[],
        is_default=True,
        rounds_taken=0,
    )
    assert c.is_default is True


def test_contract_from_negotiation():
    proposal = ExecutorProposal(
        plan_steps=["list /outbox", "write /outbox/1.json"],
        expected_outcome="email written",
        required_tools=["list", "write"],
        open_questions=[],
        agreed=True,
    )
    response = EvaluatorResponse(
        success_criteria=["file /outbox/1.json exists", "contains 'to' field"],
        failure_conditions=["file not written"],
        required_evidence=["/outbox/1.json"],
        objections=[],
        counter_proposal=None,
        agreed=True,
    )
    c = Contract(
        plan_steps=proposal.plan_steps,
        success_criteria=response.success_criteria,
        required_evidence=response.required_evidence,
        failure_conditions=response.failure_conditions,
        is_default=False,
        rounds_taken=1,
    )
    assert c.rounds_taken == 1
    assert "/outbox/1.json" in c.required_evidence
