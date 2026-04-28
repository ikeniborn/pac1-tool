# tests/test_contract_files.py
import json
from pathlib import Path

import pytest

from agent.contract_models import Contract

_DATA = Path(__file__).parent.parent / "data"

TASK_TYPES = [
    "default", "email", "inbox", "queue", "lookup",
    "capture", "crm", "temporal", "distill", "preject",
]


@pytest.mark.parametrize("task_type", TASK_TYPES)
def test_executor_prompt_exists(task_type):
    p = _DATA / "prompts" / task_type / "executor_contract.md"
    assert p.exists(), f"Missing: {p}"
    assert p.read_text(encoding="utf-8").strip(), f"Empty: {p}"


@pytest.mark.parametrize("task_type", TASK_TYPES)
def test_evaluator_prompt_exists(task_type):
    p = _DATA / "prompts" / task_type / "evaluator_contract.md"
    assert p.exists(), f"Missing: {p}"
    assert p.read_text(encoding="utf-8").strip(), f"Empty: {p}"


@pytest.mark.parametrize("task_type", TASK_TYPES)
def test_default_contract_valid(task_type):
    p = _DATA / "default_contracts" / f"{task_type}.json"
    assert p.exists(), f"Missing: {p}"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["is_default"] = True
    data.setdefault("rounds_taken", 0)
    contract = Contract(**data)
    assert contract.plan_steps, "plan_steps must be non-empty"
    assert contract.success_criteria, "success_criteria must be non-empty"
    assert contract.failure_conditions, "failure_conditions must be non-empty"
    assert contract.required_evidence == [], "required_evidence must be []"


def test_load_prompt_returns_nonempty_for_all_types():
    """Integration: _load_prompt must return non-empty for every type."""
    from agent.contract_phase import _load_prompt
    for task_type in TASK_TYPES:
        for role in ("executor", "evaluator"):
            result = _load_prompt(role, task_type)
            assert result, f"_load_prompt('{role}', '{task_type}') returned empty"


def test_load_default_contract_for_all_types():
    """Integration: _load_default_contract must return file-based contract (not hardcoded stub)."""
    from agent.contract_phase import _load_default_contract
    for task_type in TASK_TYPES:
        contract = _load_default_contract(task_type)
        assert contract.plan_steps != ["discover vault", "execute task", "report"], \
            f"_load_default_contract('{task_type}') returned hardcoded stub — file missing"
