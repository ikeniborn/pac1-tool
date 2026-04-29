# tests/test_contract_monitor.py
from agent.contract_models import Contract


def _make_contract(plan_steps=None):
    return Contract(
        plan_steps=plan_steps or ["write /outbox/1.json", "read /contacts/"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["unauthorized delete"],
        is_default=False,
        rounds_taken=1,
    )


def test_no_warning_when_done_ops_empty():
    from agent.contract_monitor import check_step
    contract = _make_contract()
    assert check_step(contract, [], step_num=5) is None


def test_no_warning_on_expected_write():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["write to /outbox/"])
    result = check_step(contract, ["WRITTEN: /outbox/1.json"], step_num=5)
    assert result is None


def test_warning_on_unexpected_write_at_step_gte_3():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["read /contacts/", "write /outbox/"])
    # Writing to /secrets/ not mentioned in plan
    result = check_step(contract, ["WRITTEN: /secrets/key.txt"], step_num=4)
    assert result is not None
    assert "secrets" in result.lower()


def test_no_warning_on_unexpected_write_before_step_3():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["read /contacts/"])
    # Writing before step 3 — grace period, no warning
    result = check_step(contract, ["WRITTEN: /outbox/1.json"], step_num=2)
    assert result is None


def test_warning_on_unexpected_delete():
    from agent.contract_monitor import check_step
    # Plan says write only; delete to /important/ is unexpected
    contract = _make_contract(plan_steps=["write /outbox/1.json"])
    result = check_step(contract, ["DELETED: /important/file.md"], step_num=1)
    assert result is not None
    assert "important" in result.lower()


def test_no_warning_on_expected_delete():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["delete /01_capture/ contents", "write /outbox/"])
    result = check_step(contract, ["DELETED: /01_capture/note.md"], step_num=3)
    assert result is None


def test_only_last_op_checked():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["write /outbox/"])
    # Last op is expected, prior ops don't matter
    result = check_step(
        contract,
        ["DELETED: /bad/file.md", "WRITTEN: /outbox/1.json"],
        step_num=5,
    )
    assert result is None
