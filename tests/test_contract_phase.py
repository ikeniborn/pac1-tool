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


@patch("agent.contract_phase._extract_json_from_text")
@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_max_rounds_empty_transcript(mock_llm, mock_extract):
    """All parse attempts exhausted every round → empty transcript → default contract."""
    mock_llm.return_value = "not json"
    mock_extract.return_value = None  # parse always fails
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=1,
    )
    assert contract.is_default is True
    assert rounds == []


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


@patch("agent.contract_phase.call_llm_raw")
def test_vault_tree_injected_into_llm_prompt(mock_llm):
    """vault_tree appears in the user prompt sent to both executor and evaluator."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    negotiate_contract(
        task_text="Write email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        vault_tree="├── 00_inbox\n└── 01_capture",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    for call_args in mock_llm.call_args_list:
        user_msg = call_args[0][1]
        assert "01_capture" in user_msg, f"vault_tree missing from prompt: {user_msg[:200]}"


@patch("agent.contract_phase.call_llm_raw")
def test_parse_retry_succeeds_on_third_attempt(mock_llm):
    """Executor parse fails twice then succeeds — contract finalized, not default."""
    bad_executor = "not json"
    good_executor = _make_executor_json(agreed=True)
    good_evaluator = _make_evaluator_json(agreed=True)
    # Round 1: executor fails 2x, succeeds 3rd; then evaluator succeeds
    mock_llm.side_effect = [
        bad_executor, bad_executor, good_executor,
        good_evaluator,
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Should finalize after retry success"


@patch("agent.contract_phase.call_llm_raw")
def test_parse_retry_exhausted_continues_to_next_round(mock_llm):
    """Executor parse fails 3x on round 1 → skips round, tries round 2 which succeeds."""
    bad_executor = "not json"
    good_executor = _make_executor_json(agreed=True)
    good_evaluator = _make_evaluator_json(agreed=True)
    # Round 1: executor fails 3x (exhausted); Round 2: both succeed
    mock_llm.side_effect = [
        bad_executor, bad_executor, bad_executor,
        good_executor, good_evaluator,
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Round 2 should succeed after round 1 retry exhaustion"


@patch("agent.contract_phase.call_llm_raw")
def test_partial_fallback_from_last_round(mock_llm):
    """max_rounds exceeded but transcript non-empty → non-default contract from last round."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["not satisfied"]),
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["still not"]),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Should use partial contract from last round"
    assert contract.rounds_taken == 2
    assert contract.plan_steps == ["list /", "write /out/1.json"]


def test_executor_proposal_json5_trailing_comma():
    """Contract negotiation survives trailing comma in executor JSON."""
    from unittest.mock import patch
    import agent.contract_phase as cp

    executor_response = '{"plan_steps": ["discover", "execute"], "expected_outcome": "done", "required_tools": ["read"], "open_questions": [], "agreed": true,}'
    evaluator_response = '{"success_criteria": ["task done"], "failure_conditions": ["no action"], "required_evidence": [], "objections": [], "counter_proposal": null, "agreed": true}'

    call_count = 0
    def fake_llm(system, user, model, cfg, **kwargs):
        nonlocal call_count
        call_count += 1
        tok = kwargs.get("token_out", {})
        if tok is not None:
            tok["input"] = 10
            tok["output"] = 10
        return executor_response if call_count % 2 == 1 else evaluator_response

    with patch("agent.contract_phase.call_llm_raw", side_effect=fake_llm):
        with patch("agent.contract_phase._load_prompt", return_value="system prompt"):
            contract, _, _, _ = cp.negotiate_contract(
                task_text="do the thing",
                task_type="email",
                agents_md="",
                wiki_context="",
                graph_context="",
                model="qwen3.5:cloud",
                cfg={},
                max_rounds=1,
            )
    assert not contract.is_default
    assert "discover" in contract.plan_steps
