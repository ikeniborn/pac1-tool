# tests/test_contract_phase.py
import json
from unittest.mock import patch

from agent.contract_models import Contract


def _make_executor_json(agreed=False, steps=None):
    return json.dumps({
        "plan_steps": steps or ["list /", "write /out/1.json"],
        "expected_outcome": "file written",
        "required_tools": ["list", "write"],
        "open_questions": [],
        "agreed": agreed,
    })


def _make_evaluator_json(agreed=False, objections=None):
    return json.dumps({
        "success_criteria": ["file /out/1.json written"],
        "failure_conditions": ["no file written"],
        "required_evidence": ["/out/1.json"],
        "objections": objections or [],
        "counter_proposal": None,
        "agreed": agreed,
    })


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_on_round_1(mock_llm):
    """Both agents agree on round 1 → contract finalized, is_default=False."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok = negotiate_contract(
        task_text="Write email to bob@x.com",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    assert isinstance(contract, Contract)
    assert contract.is_default is False
    assert contract.rounds_taken == 1
    assert "/out/1.json" in contract.required_evidence


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_on_round_2(mock_llm):
    """Evaluator objects on round 1, agrees on round 2 → rounds_taken=2."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["missing read step"]),
        _make_executor_json(agreed=True, steps=["list /", "read /f.json", "write /out/1.json"]),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.rounds_taken == 2
    assert contract.is_default is False


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_max_rounds(mock_llm):
    """Never agree → falls back to default contract after max_rounds."""
    mock_llm.return_value = _make_executor_json(agreed=False)
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_llm_error(mock_llm):
    """LLM returns None (all tiers failed) → falls back to default contract."""
    mock_llm.return_value = None
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_invalid_json(mock_llm):
    """LLM returns malformed JSON → falls back to default contract."""
    mock_llm.return_value = "not json at all"
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_token_counting(mock_llm):
    """in_tok and out_tok are populated from LLM calls."""
    def side_effect(system, user_msg, model, cfg, max_tokens=800, token_out=None, **kwargs):
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 50
        if "executor" in system.lower():
            return _make_executor_json(agreed=True)
        return _make_evaluator_json(agreed=True)

    mock_llm.side_effect = side_effect
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert in_tok > 0
    assert out_tok > 0
