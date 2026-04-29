# tests/test_loop_mutation_gate.py
"""Tests for FIX-415: evaluator-only mutation gate in _pre_dispatch."""
from unittest.mock import MagicMock, patch


def _make_contract(evaluator_only: bool, mutation_scope: list[str]):
    from agent.contract_models import Contract
    return Contract(
        plan_steps=["step 1"],
        success_criteria=["ok"],
        required_evidence=[],
        failure_conditions=[],
        evaluator_only=evaluator_only,
        mutation_scope=mutation_scope,
        is_default=False,
        rounds_taken=1,
    )


def _make_loop_state(contract):
    from agent.loop import _LoopState
    st = _LoopState()
    st.contract = contract
    return st


def _make_write_job(path: str):
    from agent.models import NextStep, Req_Write
    return NextStep(
        current_state="testing",
        plan_remaining_steps_brief=["write file"],
        done_operations=[],
        task_completed=False,
        function=Req_Write(tool="write", path=path, content="data"),
    )


def _make_delete_job(path: str):
    from agent.models import NextStep, Req_Delete
    return NextStep(
        current_state="testing",
        plan_remaining_steps_brief=["delete file"],
        done_operations=[],
        task_completed=False,
        function=Req_Delete(tool="delete", path=path),
    )


def test_no_gate_when_full_consensus():
    """Full-consensus contract (evaluator_only=False) → no gate, returns None."""
    contract = _make_contract(evaluator_only=False, mutation_scope=[])
    st = _make_loop_state(contract)
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None


def test_gate_blocks_out_of_scope_write():
    """Evaluator-only contract with empty mutation_scope blocks all writes."""
    contract = _make_contract(evaluator_only=True, mutation_scope=[])
    st = _make_loop_state(contract)
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None
    assert any(word in result.lower() for word in ("evaluator-only", "mutation_scope", "outside", "contract-gate"))


def test_gate_allows_in_scope_write():
    """Evaluator-only contract with mutation_scope=['/result.json'] allows that path."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/result.json"])
    st = _make_loop_state(contract)
    job = _make_write_job("/result.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None


def test_gate_blocks_out_of_scope_delete():
    """Evaluator-only contract blocks delete outside mutation_scope."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/outbox/1.json"])
    st = _make_loop_state(contract)
    job = _make_delete_job("/some/other/file.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None


def test_gate_no_contract():
    """No contract on state → gate is skipped, returns None."""
    from agent.loop import _LoopState
    st = _LoopState()
    st.contract = None
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None
