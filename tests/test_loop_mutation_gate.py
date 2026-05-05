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
        function=Req_Write(tool="write", path=path, content="data"),  # type: ignore[call-arg]
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
    """Negotiated contract with mutation_scope=['/expected.json'] blocks write to '/result.txt'."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/expected.json"])
    st = _make_loop_state(contract)
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None
    assert any(word in result.lower() for word in ("outside", "contract-gate"))


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


def test_gate_active_for_negotiated_contract_with_scope():
    """Block E: negotiated contract (is_default=False) with mutation_scope blocks out-of-scope."""
    contract = _make_contract(evaluator_only=False, mutation_scope=["/outbox/1.json"])
    st = _make_loop_state(contract)
    job = _make_write_job("/wrong/path.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is not None
    assert "contract-gate" in result.lower() or "outside" in result.lower()


def test_gate_inactive_for_default_contract():
    """Block E: default contract (is_default=True) → gate skipped even with non-empty scope."""
    from agent.contract_models import Contract
    from agent.loop import _LoopState, _pre_dispatch
    contract = Contract(
        plan_steps=["x"], success_criteria=["y"], required_evidence=[], failure_conditions=[],
        mutation_scope=["/expected.json"],
        is_default=True,
        rounds_taken=0,
    )
    st = _LoopState()
    st.contract = contract
    job = _make_write_job("/anywhere.json")
    vm = MagicMock()
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None


def test_gate_inactive_when_no_scope_specified():
    """Block E: negotiated contract with empty mutation_scope → no gate (no scope to enforce)."""
    contract = _make_contract(evaluator_only=False, mutation_scope=[])
    st = _make_loop_state(contract)
    job = _make_write_job("/anywhere.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "queue", vm, st)
    assert result is None


def _make_report(outcome: str = "OUTCOME_OK", steps=None):
    from agent.models import ReportTaskCompletion
    return ReportTaskCompletion(
        tool="report_completion",
        completed_steps_laconic=steps or [],
        message="done",
        outcome=outcome,  # type: ignore[arg-type]
        grounding_refs=[],
    )


def test_lookup_bypass_when_explored():
    """FIX-424: lookup OUTCOME_OK with exploration steps → must NOT bypass evaluator.

    This test was updated from FIX-420 which had the bug: it incorrectly
    bypassed for OUTCOME_OK + exploration. FIX-424 fixes this.
    """
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=["listed /01_capture/influential — 5 articles"])
    assert _should_bypass_evaluator_lookup(report) is False


def test_lookup_no_bypass_when_no_exploration():
    """FIX-420: lookup OUTCOME_OK with zero exploration → evaluator must run."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=[])
    assert _should_bypass_evaluator_lookup(report) is False


def test_lookup_bypass_for_clarification():
    """FIX-420: OUTCOME_NONE_CLARIFICATION never needs evaluator."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_NONE_CLARIFICATION", steps=[])
    assert _should_bypass_evaluator_lookup(report) is True


def test_bypass_lookup_outcome_ok_with_exploration_should_not_bypass():
    """FIX-424: OUTCOME_OK + exploration must NOT bypass evaluator for lookup."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=["read /contacts/cont_001.json", "found contact"])
    # Pre-FIX-424: this returned True (bug). Post-fix: must return False.
    assert _should_bypass_evaluator_lookup(report) is False


def test_bypass_lookup_none_clarification_still_bypasses():
    """FIX-424: NONE_CLARIFICATION must still bypass evaluator for lookup."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_NONE_CLARIFICATION", steps=[])
    assert _should_bypass_evaluator_lookup(report) is True


def test_bypass_lookup_outcome_ok_no_exploration_does_not_bypass():
    """FIX-424: OUTCOME_OK without exploration also must not bypass (unchanged)."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=[])
    assert _should_bypass_evaluator_lookup(report) is False


def test_crm_date_anchor_gate_blocks_when_no_vault_date_in_steps():
    """FIX-425: CRM OUTCOME_OK without VAULT_DATE in steps → gate rejects."""
    from agent.loop import _check_crm_date_anchor
    from unittest.mock import MagicMock

    report = MagicMock()
    report.outcome = "OUTCOME_OK"
    report.completed_steps_laconic = [
        "searched reminders for Nordlicht",
        "wrote due_on=2026-08-08",
    ]

    result = _check_crm_date_anchor(report)
    assert result is not None
    assert "vault_date" in result.lower() or "VAULT_DATE" in result


def test_crm_date_anchor_gate_blocks_when_no_offset_in_steps():
    """FIX-425: VAULT_DATE present but +8 absent → gate rejects."""
    from agent.loop import _check_crm_date_anchor
    from unittest.mock import MagicMock

    report = MagicMock()
    report.outcome = "OUTCOME_OK"
    report.completed_steps_laconic = [
        "VAULT_DATE=2026-07-25",
        "wrote due_on=2026-08-08",
    ]

    result = _check_crm_date_anchor(report)
    assert result is not None


def test_crm_date_anchor_gate_passes_with_vault_date_and_offset():
    """FIX-425: steps with VAULT_DATE + TOTAL_DAYS → gate approves."""
    from agent.loop import _check_crm_date_anchor
    from unittest.mock import MagicMock

    report = MagicMock()
    report.outcome = "OUTCOME_OK"
    report.completed_steps_laconic = [
        "VAULT_DATE=2026-07-25, stated=2 weeks=14 days, TOTAL_DAYS=14+8=22, due_on=2026-07-25+22=2026-08-16",
    ]

    result = _check_crm_date_anchor(report)
    assert result is None


def test_crm_date_anchor_gate_skips_for_none_clarification():
    """FIX-425: gate only applies to OUTCOME_OK, not NONE_CLARIFICATION."""
    from agent.loop import _check_crm_date_anchor
    from unittest.mock import MagicMock

    report = MagicMock()
    report.outcome = "OUTCOME_NONE_CLARIFICATION"
    report.completed_steps_laconic = []

    result = _check_crm_date_anchor(report)
    assert result is None


def test_consecutive_contract_blocks_counter_increments():
    """_pre_dispatch increments st.consecutive_contract_blocks on each blocked write."""
    contract = _make_contract(evaluator_only=True, mutation_scope=["/expected.json"])
    st = _make_loop_state(contract)
    assert st.consecutive_contract_blocks == 0

    # Path /result.txt is outside scope ["/expected.json"] → gate fires.
    job = _make_write_job("/result.txt")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    result = _pre_dispatch(job, "crm", vm, st)
    assert result is not None, "gate should fire"
    assert st.consecutive_contract_blocks == 1

    result2 = _pre_dispatch(job, "crm", vm, st)
    assert result2 is not None, "gate should fire again"
    assert st.consecutive_contract_blocks == 2
