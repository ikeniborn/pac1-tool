import json
from unittest.mock import MagicMock, patch
import pytest
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult


def _make_pre():
    return PrephaseResult(
        agents_md_content="AGENTS",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(id INT, sku TEXT)",
    )


def _test_gen_json():
    return json.dumps({
        "reasoning": "task expects products",
        "sql_tests": "def test_sql(results):\n    assert results\n",
        "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })


def test_test_gen_parse_failure_hard_stop(tmp_path):
    """TEST_GEN returns garbage → vm.answer(OUTCOME_NONE_CLARIFICATION), SQL never runs."""
    vm = MagicMock()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    with patch("agent.pipeline.call_llm_raw", return_value="not json at all"), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._TDD_ENABLED", True):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "find laptops", pre, {})

    vm.answer.assert_called_once()
    req = vm.answer.call_args[0][0]
    assert "CLARIFICATION" in str(req.outcome)
    assert "Test generation failed" in req.message
    vm.exec.assert_not_called()
