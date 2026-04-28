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
    contract, in_tok, out_tok, _rounds = negotiate_contract(
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
    contract, _, _, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.rounds_taken == 2
    assert contract.is_default is False


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_max_rounds(mock_llm):
    """Never agree → falls back to default contract after max_rounds exhausted."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["not satisfied"]),
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["still not satisfied"]),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is True
    assert mock_llm.call_count == 4  # both rounds fully executed


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_llm_error(mock_llm):
    """LLM returns None (all tiers failed) → falls back to default contract."""
    mock_llm.return_value = None
    from agent.contract_phase import negotiate_contract
    contract, _, _, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_invalid_json(mock_llm):
    """LLM returns malformed JSON → falls back to default contract."""
    mock_llm.return_value = "not json at all"
    from agent.contract_phase import negotiate_contract
    contract, _, _, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_token_counting(mock_llm):
    """in_tok and out_tok are populated from LLM calls."""
    call_count = 0

    def side_effect(system, user_msg, model, cfg, max_tokens=800, token_out=None, **kwargs):
        nonlocal call_count
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 50
        call_count += 1
        if call_count % 2 == 1:  # odd = executor
            return _make_executor_json(agreed=True)
        return _make_evaluator_json(agreed=True)  # even = evaluator

    mock_llm.side_effect = side_effect
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is False
    assert contract.rounds_taken == 1
    assert in_tok > 0
    assert out_tok > 0


def test_strip_fences_plain_json():
    from agent.contract_phase import _strip_fences
    raw = '{"agreed": true}'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_json_block():
    from agent.contract_phase import _strip_fences
    raw = '```json\n{"agreed": true}\n```'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_plain_block():
    from agent.contract_phase import _strip_fences
    raw = '```\n{"agreed": true}\n```'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_with_whitespace():
    from agent.contract_phase import _strip_fences
    raw = '\n\n```json\n  {"agreed": true}\n```\n'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_empty():
    from agent.contract_phase import _strip_fences
    assert _strip_fences("") == ""
    assert _strip_fences("   ") == ""


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_with_fenced_json(mock_llm):
    """LLM returns markdown-fenced JSON — must be stripped before parsing."""
    executor_json = _make_executor_json(agreed=True)
    evaluator_json = _make_evaluator_json(agreed=True)
    mock_llm.side_effect = [
        f"```json\n{executor_json}\n```",
        f"```json\n{evaluator_json}\n```",
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _rounds = negotiate_contract(
        task_text="Send email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-3.5-sonnet",
        cfg={},
        max_rounds=3,
    )
    assert contract.is_default is False
    assert contract.rounds_taken == 1


@patch("agent.contract_phase.call_llm_raw")
def test_executor_and_evaluator_get_separate_schemas(mock_llm):
    """Each role gets a cfg with its own cc_json_schema derived from its Pydantic model."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    from agent.contract_models import ExecutorProposal, EvaluatorResponse

    negotiate_contract(
        task_text="Send email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-3.5-sonnet",
        cfg={"cc_options": {"cc_effort": "low"}},
        max_rounds=1,
    )  # return value not unpacked — just checking call args

    assert mock_llm.call_count == 2
    executor_call_cfg = mock_llm.call_args_list[0][0][3]   # positional arg index 3
    evaluator_call_cfg = mock_llm.call_args_list[1][0][3]

    ex_schema = executor_call_cfg["cc_options"]["cc_json_schema"]
    ev_schema = evaluator_call_cfg["cc_options"]["cc_json_schema"]

    # Schemas come from Pydantic and differ
    assert ex_schema == ExecutorProposal.model_json_schema()
    assert ev_schema == EvaluatorResponse.model_json_schema()
    assert ex_schema != ev_schema

    # Original cc_effort preserved
    assert executor_call_cfg["cc_options"]["cc_effort"] == "low"
    assert evaluator_call_cfg["cc_options"]["cc_effort"] == "low"


@patch("agent.contract_phase.call_llm_raw")
def test_cc_tier_skips_negotiation_no_llm_calls(mock_llm):
    """CC tier model → immediate default contract, zero LLM calls."""
    from agent.contract_phase import negotiate_contract

    contract, in_tok, out_tok, rounds = negotiate_contract(
        task_text="Write email to bob@x.com",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-code/sonnet-4.6",
        cfg={},
        max_rounds=3,
    )
    assert contract.is_default is True
    assert in_tok == 0
    assert out_tok == 0
    mock_llm.assert_not_called()


@patch("agent.contract_phase.call_llm_raw")
def test_negotiate_returns_rounds_transcript(mock_llm):
    """negotiate_contract returns 4-tuple with list containing one ContractRound dict."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    result = negotiate_contract(
        task_text="Write email to bob@x.com",
        task_type="email",
        agents_md="", wiki_context="", graph_context="",
        model="test-model", cfg={}, max_rounds=3,
    )
    assert len(result) == 4
    contract, in_tok, out_tok, rounds = result
    assert len(rounds) == 1
    assert rounds[0]["round_num"] == 1
    assert "plan_steps" in rounds[0]["executor_proposal"]
    assert "success_criteria" in rounds[0]["evaluator_response"]


@patch("agent.contract_phase.call_llm_raw")
def test_default_fallback_returns_empty_rounds(mock_llm):
    """CC-tier model path returns empty rounds list."""
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok, rounds = negotiate_contract(
        task_text="task",
        task_type="email",
        agents_md="", wiki_context="", graph_context="",
        model="claude-code/opus",
        cfg={}, max_rounds=3,
    )
    assert rounds == []
    assert contract.is_default is True


def test_effective_model_uses_env(monkeypatch):
    """_effective_model returns MODEL_CONTRACT when set."""
    from agent.contract_phase import _effective_model
    monkeypatch.setenv("MODEL_CONTRACT", "openrouter/anthropic/claude-3-5-haiku")
    assert _effective_model("anthropic/claude-sonnet-4.6") == "openrouter/anthropic/claude-3-5-haiku"
    monkeypatch.delenv("MODEL_CONTRACT", raising=False)
    assert _effective_model("anthropic/claude-sonnet-4.6") == "anthropic/claude-sonnet-4.6"
