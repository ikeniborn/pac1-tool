# tests/test_evaluator.py
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from agent.evaluator import EvalInput, run_evaluator


def _make_eval_input():
    return EvalInput(
        task_text="How many Lawn Mowers?",
        agents_md="vault rules here",
        db_schema="CREATE TABLE products(...)",
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
        "score": 0.9,
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
    assert result.score == 0.9
    assert result.security_optimization == ["Add gate for UNION SELECT injection"]
    line = json.loads(log_path.read_text().strip())
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
