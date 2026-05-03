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
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
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


def test_stall_hint_includes_contract_plan_steps():
    """When contract_plan_steps provided, stall hint mentions the agreed plan."""
    from collections import Counter, deque
    from agent.stall import _check_stall

    fingerprints = deque(["list:/", "list:/", "list:/"])
    hint = _check_stall(
        fingerprints=fingerprints,
        steps_since_write=0,
        error_counts=Counter(),
        contract_plan_steps=["list /", "read /contacts/c01.json", "write /out/1.json"],
    )
    assert hint is not None
    assert "agreed plan" in hint.lower() or "contract" in hint.lower()


def test_stall_without_contract_plan_steps_unchanged():
    """Without contract_plan_steps, stall hint is unchanged from current behaviour."""
    from collections import Counter, deque
    from agent.stall import _check_stall

    fingerprints = deque(["list:/", "list:/", "list:/"])
    hint = _check_stall(
        fingerprints=fingerprints,
        steps_since_write=0,
        error_counts=Counter(),
        contract_plan_steps=None,
    )
    assert hint is not None
    assert "3 times in a row" in hint


def test_contract_injected_into_system_prompt():
    """_format_contract_block builds the correct ## AGREED CONTRACT section."""
    from agent.contract_models import Contract
    from agent.loop import _format_contract_block

    contract = Contract(
        plan_steps=["list /outbox", "write /outbox/1.json"],
        success_criteria=["file written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["no write"],
        is_default=False,
        rounds_taken=1,
    )
    block = _format_contract_block(contract)
    assert "## AGREED CONTRACT" in block
    assert "list /outbox" in block
    assert "file written" in block
    assert "/outbox/1.json" in block


def test_executor_proposal_planned_mutations_default():
    """planned_mutations defaults to empty list."""
    p = ExecutorProposal(
        plan_steps=["list /", "write /outbox/1.json"],
        expected_outcome="email written",
        required_tools=["list", "write"],
        open_questions=[],
        agreed=False,
    )
    assert p.planned_mutations == []


def test_executor_proposal_planned_mutations_explicit():
    """planned_mutations accepts a list of path strings."""
    p = ExecutorProposal(
        plan_steps=["write /outbox/1.json"],
        expected_outcome="email written",
        required_tools=["write"],
        planned_mutations=["/outbox/1.json"],
        open_questions=[],
        agreed=True,
    )
    assert "/outbox/1.json" in p.planned_mutations


def test_contract_new_fields_defaults():
    """New Contract fields default to safe values."""
    c = Contract(
        plan_steps=["step 1"],
        success_criteria=["ok"],
        required_evidence=[],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
    )
    assert c.mutation_scope == []
    assert c.forbidden_mutations == []
    assert c.evaluator_only is False


def test_contract_evaluator_only_flag():
    """evaluator_only=True is preserved through model."""
    c = Contract(
        plan_steps=["read /inbox/msg.txt"],
        success_criteria=["no mutation"],
        required_evidence=[],
        failure_conditions=[],
        is_default=False,
        rounds_taken=3,
        evaluator_only=True,
        mutation_scope=[],
    )
    assert c.evaluator_only is True
    assert c.mutation_scope == []


def test_contract_mutation_scope_nonempty():
    """mutation_scope list is preserved through model."""
    c = Contract(
        plan_steps=["write /outbox/1.json"],
        success_criteria=["outbox written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
        mutation_scope=["/outbox/1.json"],
        evaluator_only=True,
    )
    assert "/outbox/1.json" in c.mutation_scope


def test_contract_has_planner_strategy_field():
    from agent.contract_models import Contract
    c = Contract(
        plan_steps=["step 1"],
        success_criteria=["done"],
        required_evidence=[],
        failure_conditions=[],
        is_default=True,
        rounds_taken=0,
    )
    assert hasattr(c, "planner_strategy")
    assert c.planner_strategy == ""


def test_default_temporal_contract_has_required_evidence():
    import json
    from pathlib import Path
    data = json.loads(Path("data/default_contracts/temporal.json").read_text())
    assert "planner_strategy" in data
    assert len(data.get("required_evidence", [])) >= 3


def test_default_lookup_contract_has_required_evidence():
    import json
    from pathlib import Path
    data = json.loads(Path("data/default_contracts/lookup.json").read_text())
    assert "planner_strategy" in data
    assert len(data.get("required_evidence", [])) >= 2


def test_all_default_contracts_have_planner_strategy():
    import json
    from pathlib import Path
    for f in sorted(Path("data/default_contracts").glob("*.json")):
        data = json.loads(f.read_text())
        assert "planner_strategy" in data, f"Missing planner_strategy in {f.name}"
