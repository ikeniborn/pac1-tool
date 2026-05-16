# tests/test_evaluator.py
import json
from unittest.mock import patch
from agent.evaluator import EvalInput, run_evaluator
import agent.evaluator as ev
import agent.knowledge_loader as kl


def _make_eval_input():
    return EvalInput(
        task_text="How many Lawn Mowers?",
        prephase={"agents_md": "vault rules here", "schema_digest": {}},
        sgr_trace=[
            {"phase": "SqlPlanOutput", "guide_prompt": "...", "reasoning": "products.type", "output": {}},
            {"phase": "AnswerOutput", "guide_prompt": "...", "reasoning": "3 found", "output": {}},
        ],
        cycles=1,
        final_outcome="OUTCOME_OK",
    )


def test_run_evaluator_writes_to_log(tmp_path):
    eval_json = json.dumps({
        "reasoning": "trace is good",
        "score": 9,
        "comment": "solid",
        "prompt_optimization": [],
        "rule_optimization": [],
        "security_optimization": ["Add gate for UNION SELECT injection"],
    })
    log_path = tmp_path / "eval_log.jsonl"
    with patch("agent.evaluator.call_llm_raw", return_value=eval_json), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        result = run_evaluator(_make_eval_input(), model="test-model", cfg={})

    assert result is not None
    assert result.score == 9
    assert result.security_optimization == ["Add gate for UNION SELECT injection"]
    line = json.loads(log_path.read_text().strip())
    assert line["score"] == 9
    assert line["task_text"] == "How many Lawn Mowers?"
    assert line["final_outcome"] == "OUTCOME_OK"
    assert line["security_optimization"] == ["Add gate for UNION SELECT injection"]


def test_run_evaluator_llm_failure_returns_none(tmp_path):
    """LLM failure → returns None, no crash."""
    log_path = tmp_path / "eval_log.jsonl"
    with patch("agent.evaluator.call_llm_raw", return_value=None), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        result = run_evaluator(_make_eval_input(), model="test-model", cfg={})
    assert result is None
    assert not log_path.exists()


def test_run_evaluator_parse_failure_returns_none(tmp_path):
    """Unparseable LLM response → returns None, no crash."""
    log_path = tmp_path / "eval_log.jsonl"
    with patch("agent.evaluator.call_llm_raw", return_value="not json at all"), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        result = run_evaluator(_make_eval_input(), model="test-model", cfg={})
    assert result is None


def test_run_evaluator_exception_returns_none(tmp_path):
    """Any exception in evaluator → returns None (fail-open)."""
    log_path = tmp_path / "eval_log.jsonl"
    with patch("agent.evaluator.call_llm_raw", side_effect=RuntimeError("network")), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        result = run_evaluator(_make_eval_input(), model="test-model", cfg={})
    assert result is None


def test_build_eval_system_injects_existing_blocks():
    system = ev._build_eval_system(
        agents_md="# VAULT\nDo X.",
        rules_md="- sql-001: Never SELECT star.",
        security_md="- sec-001: DDL prohibited.",
        prompts_md="=== answer.md ===\n# Answer\n",
    )
    assert "EXISTING RULES" in system
    assert "sql-001: Never SELECT star." in system
    assert "EXISTING SECURITY GATES" in system
    assert "sec-001: DDL prohibited." in system
    assert "EXISTING PROMPT CONTENT" in system
    assert "answer.md" in system


def test_run_evaluator_loads_knowledge_into_system_prompt():
    """run_evaluator must pass existing content from knowledge_loader into the system prompt."""
    inp = EvalInput(
        task_text="How many products?",
        prephase={"agents_md": "# Rules\nDo X.", "schema_digest": {}},
        sgr_trace=[],
        cycles=1,
        final_outcome="OUTCOME_SUCCESS",
    )
    captured_system = []

    def fake_call_llm_raw(system, *_args, **_kwargs):
        captured_system.append(system)
        return None  # fail-open → run_evaluator returns None

    with patch.object(kl, "existing_rules_text", return_value="- sql-001: Never X."), \
         patch.object(kl, "existing_security_text", return_value="- sec-001: Block DDL."), \
         patch.object(kl, "existing_prompts_text", return_value="=== answer.md ===\nDo Y.\n"), \
         patch.object(ev, "call_llm_raw", side_effect=fake_call_llm_raw):
        result = ev.run_evaluator(inp, "test-model", {})

    assert result is None  # fail-open
    assert len(captured_system) == 1
    assert "sql-001: Never X." in captured_system[0]
    assert "sec-001: Block DDL." in captured_system[0]
    assert "answer.md" in captured_system[0]


def test_task_id_written_to_log(tmp_path):
    eval_json = json.dumps({
        "reasoning": "ok", "score": 8, "comment": "fine",
        "prompt_optimization": [], "rule_optimization": [], "security_optimization": [],
    })
    log_path = tmp_path / "eval_log.jsonl"
    inp = EvalInput(
        task_id="t07",
        task_text="How many products?",
        prephase={"agents_md": "rules", "schema_digest": {}},
        sgr_trace=[],
        cycles=1,
        final_outcome="OUTCOME_OK",
    )
    with patch("agent.evaluator.call_llm_raw", return_value=eval_json), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        run_evaluator(inp, model="test-model", cfg={})
    line = json.loads(log_path.read_text().strip())
    assert line["task_id"] == "t07"


def _make_eval_input_v2(**kwargs):
    """Helper for new EvalInput schema with task_type, prephase, learn_ctx."""
    defaults = dict(
        task_id="t01",
        task_text="find laptops",
        task_type="sql",
        prephase={"agents_md": "AGENTS", "schema_digest": {}},
        learn_ctx=["rule: always use LIKE for discovery"],
        sgr_trace=[],
        cycles=3,
        final_outcome="OUTCOME_NONE_CLARIFICATION",
    )
    defaults.update(kwargs)
    return EvalInput(**defaults)


def test_eval_input_has_task_type():
    ei = _make_eval_input_v2()
    assert ei.task_type == "sql"


def test_eval_input_has_learn_ctx():
    ei = _make_eval_input_v2(learn_ctx=["rule_A", "rule_B"])
    assert len(ei.learn_ctx) == 2


def test_eval_input_has_prephase():
    ei = _make_eval_input_v2(prephase={"agents_md": "X", "schema_digest": {"tables": {}}})
    assert ei.prephase["agents_md"] == "X"


def test_run_evaluator_returns_none_on_llm_fail():
    ei = _make_eval_input_v2()
    with patch("agent.evaluator.call_llm_raw", return_value=None):
        result = run_evaluator(ei, model="anthropic/claude-haiku-4-5-20251001", cfg={})
    assert result is None
