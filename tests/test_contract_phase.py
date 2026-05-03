# tests/test_contract_phase.py
import json
from unittest.mock import patch

from agent.contract_models import Contract


def _make_planner_json():
    """Minimal planner Round 0 response."""
    import json
    return json.dumps({
        "search_scope": ["/01_capture"],
        "interpretation": "test task",
        "critical_paths": [],
        "ambiguities": [],
    })


def _make_executor_json(agreed=False, steps=None):
    return json.dumps({
        "plan_steps": steps or ["list /", "write /out/1.json"],
        "expected_outcome": "file written",
        "required_tools": ["list", "write"],
        "open_questions": [],
        "agreed": agreed,
    })


def _make_evaluator_json(agreed=False, objections=None, blocking_objections=None):
    return json.dumps({
        "success_criteria": ["file /out/1.json written"],
        "failure_conditions": ["no file written"],
        "required_evidence": ["/out/1.json"],
        "objections": objections or [],
        "blocking_objections": blocking_objections or [],
        "counter_proposal": None,
        "agreed": agreed,
    })


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_on_round_1(mock_llm):
    """Both agents agree on round 1 → contract finalized, is_default=False."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
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
        _make_planner_json(),
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["missing read step"]),
        _make_executor_json(agreed=True, steps=["list /", "read /f.json", "write /out/1.json"]),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
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
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_invalid_json(mock_llm):
    """LLM returns malformed JSON → falls back to default contract."""
    mock_llm.return_value = "not json at all"
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_token_counting(mock_llm):
    """in_tok and out_tok are populated from LLM calls."""
    call_count = 0

    def side_effect(_system, _user_msg, _model, _cfg, max_tokens=800, token_out=None, **_kwargs):
        nonlocal call_count
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 50
        call_count += 1
        if call_count == 1:  # Round 0 planner
            return _make_planner_json()
        if call_count % 2 == 0:  # call 2 = executor (even)
            return _make_executor_json(agreed=True)
        return _make_evaluator_json(agreed=True)  # call 3 = evaluator (odd)

    mock_llm.side_effect = side_effect
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok, _ = negotiate_contract(
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
        _make_planner_json(),
        f"```json\n{executor_json}\n```",
        f"```json\n{evaluator_json}\n```",
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
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
        _make_planner_json(),
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

    assert mock_llm.call_count == 3
    executor_call_cfg = mock_llm.call_args_list[1][0][3]   # positional arg index 3 (call 2)
    evaluator_call_cfg = mock_llm.call_args_list[2][0][3]  # call 3

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

    contract, in_tok, out_tok, _ = negotiate_contract(
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
        _make_planner_json(),
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
    _, _, _, rounds = result
    assert len(rounds) == 1
    assert rounds[0]["round_num"] == 1
    assert "plan_steps" in rounds[0]["executor_proposal"]
    assert "success_criteria" in rounds[0]["evaluator_response"]


@patch("agent.contract_phase.call_llm_raw")
def test_default_fallback_returns_empty_rounds(_mock_llm):
    """CC-tier model path returns empty rounds list."""
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
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
        _make_planner_json(),
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
    # Skip call 0 (planner) — check executor and evaluator calls for vault_tree
    for call_args in mock_llm.call_args_list[1:]:
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
        _make_planner_json(),
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
        _make_planner_json(),
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
        _make_planner_json(),
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


@patch("agent.contract_phase.call_llm_raw")
def test_evaluator_only_consensus_sets_flag(mock_llm):
    """Evaluator-only consensus (executor.agreed=False) → contract.evaluator_only=True."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=False, steps=["read /inbox/msg.txt", "report"]),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="Review inbox",
        task_type="inbox",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    assert contract.evaluator_only is True


@patch("agent.contract_phase.call_llm_raw")
def test_full_consensus_evaluator_only_false(mock_llm):
    """Full consensus (both agreed=True) → evaluator_only=False."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="Write email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    assert contract.evaluator_only is False


@patch("agent.contract_phase.call_llm_raw")
def test_constraint_checklist_in_evaluator_prompt(mock_llm):
    """Constraint checklist appears in the evaluator's user prompt when wiki has constraints."""
    captured_calls = []

    def capture(_system, user_msg, _model, _cfg, **kwargs):
        captured_calls.append(user_msg)
        # Call 1 = planner, call 2 = executor, call 3 = evaluator
        if len(captured_calls) == 1:
            return _make_planner_json()
        if len(captured_calls) == 2:
            return _make_executor_json(agreed=True)
        return _make_evaluator_json(agreed=True)

    mock_llm.side_effect = capture

    with patch("agent.contract_phase._load_contract_constraints") as mock_constraints:
        mock_constraints.return_value = [
            {"id": "no_vault_docs_write", "rule": "Plan MUST NOT write result.txt."},
        ]
        from agent.contract_phase import negotiate_contract
        negotiate_contract(
            task_text="Process queue",
            task_type="queue",
            agents_md="",
            wiki_context="some wiki",
            graph_context="",
            model="test-model",
            cfg={},
            max_rounds=1,
        )

    assert len(captured_calls) >= 3, "Expected at least planner + executor + evaluator calls"
    evaluator_prompt = captured_calls[2]
    assert "no_vault_docs_write" in evaluator_prompt
    assert "result.txt" in evaluator_prompt


@patch("agent.contract_phase.call_llm_raw")
def test_evaluator_only_mutation_scope_empty_when_forbidden_path(mock_llm):
    """Evaluator-only consensus with planned_mutations containing result.txt → mutation_scope=[]."""
    executor_json = json.dumps({
        "plan_steps": ["read /docs/task-completion.md", "write /result.txt"],
        "expected_outcome": "done",
        "required_tools": ["read", "write"],
        "planned_mutations": ["/result.txt"],
        "open_questions": [],
        "agreed": False,
    })
    mock_llm.side_effect = [_make_planner_json(), executor_json, _make_evaluator_json(agreed=True)]

    with patch("agent.contract_phase._load_contract_constraints") as mock_constraints:
        mock_constraints.return_value = [
            {"id": "no_vault_docs_write", "rule": "Plan MUST NOT write result.txt."},
        ]
        from agent.contract_phase import negotiate_contract
        contract, _, _, _ = negotiate_contract(
            task_text="Do task",
            task_type="queue",
            agents_md="",
            wiki_context="",
            graph_context="",
            model="test-model",
            cfg={},
            max_rounds=1,
        )

    assert contract.evaluator_only is True
    assert contract.mutation_scope == []


def test_executor_proposal_json5_trailing_comma():
    """Contract negotiation survives trailing comma in executor JSON."""
    from unittest.mock import patch
    import agent.contract_phase as cp

    executor_response = '{"plan_steps": ["discover", "execute"], "expected_outcome": "done", "required_tools": ["read"], "open_questions": [], "agreed": true,}'
    evaluator_response = '{"success_criteria": ["task done"], "failure_conditions": ["no action"], "required_evidence": [], "objections": [], "counter_proposal": null, "agreed": true}'

    call_count = 0
    def fake_llm(_system, _user, _model, _cfg, **kwargs):
        nonlocal call_count
        call_count += 1
        tok = kwargs.get("token_out", {})
        if tok is not None:
            tok["input"] = 10
            tok["output"] = 10
        if call_count == 1:  # Round 0 planner
            return _make_planner_json()
        return executor_response if call_count % 2 == 0 else evaluator_response

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


@patch("agent.contract_phase.call_llm_raw")
def test_caveat_notes_do_not_block_consensus(mock_llm):
    """agreed=True + objections with confirmations + blocking_objections=[]
    → consensus reached in round 1, not max_rounds."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=True),
        json.dumps({
            "success_criteria": ["article found"],
            "failure_conditions": [],
            "required_evidence": ["/01_capture/influential/"],
            "objections": [
                "Date math verified: 14 days before 2026-03-23 = 2026-03-09 ✓",
                "Plan correctly anchors to VAULT_DATE_LOWER_BOUND ✓",
            ],
            "blocking_objections": [],
            "counter_proposal": None,
            "agreed": True,
        }),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
        task_text="What article did I capture 14 days ago?",
        task_type="lookup",
        agents_md="", wiki_context="", graph_context="",
        model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is False
    assert contract.rounds_taken == 1
    assert len(rounds) == 1


@patch("agent.contract_phase.call_llm_raw")
def test_blocking_objections_require_extra_round(mock_llm):
    """blocking_objections non-empty → round 1 not accepted, round 2 is."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=True),
        json.dumps({
            "success_criteria": ["article found"],
            "failure_conditions": [],
            "required_evidence": [],
            "objections": [],
            "blocking_objections": ["Missing explicit date calculation step before search"],
            "counter_proposal": None,
            "agreed": True,
        }),
        _make_executor_json(agreed=True, steps=[
            "compute target date: 14 days before 2026-03-23 = 2026-03-09",
            "list /01_capture/influential",
            "filter by date prefix 2026-03-09",
            "report_completion with found article",
        ]),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, rounds = negotiate_contract(
        task_text="What article did I capture 14 days ago?",
        task_type="lookup",
        agents_md="", wiki_context="", graph_context="",
        model="m", cfg={}, max_rounds=3,
    )
    assert contract.rounds_taken == 2
    assert contract.is_default is False


@patch("agent.contract_phase.call_llm_raw")
def test_round_0_planner_runs_before_negotiation(mock_llm):
    """FIX-426: Round 0 PlannerStrategize fires before executor/evaluator; contract.planner_strategy != ''."""
    planner_json = json.dumps({"strategy": "discover then write", "priorities": ["check inbox"]})
    mock_llm.side_effect = [
        planner_json,                          # Round 0: planner
        _make_executor_json(agreed=True),      # Round 1: executor
        _make_evaluator_json(agreed=True),     # Round 1: evaluator
    ]
    with patch("agent.contract_phase._load_prompt") as mock_load_prompt:
        mock_load_prompt.side_effect = lambda role, _tt: "system prompt" if role != "planner" else "planner system"
        from agent.contract_phase import negotiate_contract
        contract, _, _, _ = negotiate_contract(
            task_text="Process inbox",
            task_type="inbox",
            agents_md="",
            wiki_context="",
            graph_context="",
            model="test-model",
            cfg={},
            max_rounds=3,
        )
    assert mock_llm.call_count == 3
    assert contract.planner_strategy != ""


@patch("agent.contract_phase.call_llm_raw")
def test_round_0_fail_open_on_planner_error(mock_llm):
    """FIX-426: If planner LLM returns None, negotiation still succeeds with planner_strategy=''."""
    mock_llm.side_effect = [
        None,                                  # Round 0: planner fails
        _make_executor_json(agreed=True),      # Round 1: executor
        _make_evaluator_json(agreed=True),     # Round 1: evaluator
    ]
    with patch("agent.contract_phase._load_prompt") as mock_load_prompt:
        mock_load_prompt.side_effect = lambda role, _tt: "system prompt" if role != "planner" else "planner system"
        from agent.contract_phase import negotiate_contract
        contract, _, _, _ = negotiate_contract(
            task_text="Process inbox",
            task_type="inbox",
            agents_md="",
            wiki_context="",
            graph_context="",
            model="test-model",
            cfg={},
            max_rounds=3,
        )
    assert contract.is_default is False
    assert contract.planner_strategy == ""


@patch("agent.contract_phase.call_llm_raw")
@patch("agent.contract_phase._load_refusal_hints")
def test_refusal_hints_injected_into_context(mock_hints, mock_llm):
    """FIX-419: refusal hints from wiki appear in the executor prompt."""
    mock_hints.return_value = "## Verified refusal: t43\nOutcome: OUTCOME_NONE_CLARIFICATION\nWhy refuse: no article on that date."
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    negotiate_contract(
        task_text="which article captured 37 days ago?",
        task_type="lookup",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=1,
    )
    first_call_user = mock_llm.call_args_list[1][0][1]  # call 1 = executor (call 0 = planner)
    assert "OUTCOME_NONE_CLARIFICATION" in first_call_user
    assert "Verified refusal" in first_call_user
