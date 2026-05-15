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
    assert "CLARIFICATION" in str(req)
    assert "Test generation failed" in req.message
    vm.exec.assert_not_called()


def _sql_plan_json(queries=None):
    return json.dumps({
        "reasoning": "ok",
        "queries": queries or ["SELECT sku, path FROM products WHERE type='Laptop'"],
    })


def _answer_json():
    return json.dumps({
        "reasoning": "found it",
        "message": "<YES> 1 laptop found",
        "outcome": "OUTCOME_OK",
        "grounding_refs": ["/proc/catalog/LAP-001.json"],
        "completed_steps": ["ran SQL", "found product"],
    })


def _make_exec_result(stdout="sku,path\nLAP-001,/proc/catalog/LAP-001.json"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_tdd_disabled_no_regression(tmp_path):
    """TDD_ENABLED=0 → pipeline identical to current; run_tests never called."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", False), \
         patch("agent.pipeline.run_tests") as mock_run_tests:
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    mock_run_tests.assert_not_called()


def test_tdd_happy_path(tmp_path):
    """TDD_ENABLED=1 + all tests pass → OUTCOME_OK, vm.answer called once."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_test_gen_json(), _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", return_value=(True, "", [])):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    vm.answer.assert_called_once()


def test_tdd_sql_test_failure_triggers_learn_and_retry(tmp_path):
    """sql_tests fail → LEARN + SQL_PLAN retry (_skip_sql=False) → sql_tests pass → ANSWER → ok."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "bad query",
        "conclusion": "add WHERE",
        "rule_content": "Always filter by type.",
    })
    # TEST_GEN, cycle1: sql_plan, cycle1: sql_test_fail → learn, cycle2: sql_plan, cycle2: answer
    call_seq = [_test_gen_json(), _sql_plan_json(), learn_json, _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    # run_tests calls: cycle1 sql_test → fail; cycle2 sql_test → pass; cycle2 answer_test → pass
    run_tests_results = iter([
        (False, "AssertionError: results empty", []),
        (True, "", []),
        (True, "", []),
    ])

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", side_effect=lambda *a, **kw: next(run_tests_results)):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    assert stats["cycles_used"] == 2


def test_tdd_answer_test_failure_skips_sql_retry(tmp_path):
    """answer_tests fail → LEARN + _skip_sql=True → next cycle skips SQL, retries ANSWER only."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result()
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "bad answer",
        "conclusion": "fix message",
        "rule_content": "Include product name in message.",
    })
    # TEST_GEN, cycle1: sql_plan, cycle1: answer → answer_test_fail → learn, cycle2: answer
    call_seq = [_test_gen_json(), _sql_plan_json(), _answer_json(), learn_json, _answer_json()]
    call_iter = iter(call_seq)

    # cycle1: sql_test → pass; cycle1: answer_test → fail; cycle2: answer_test → pass
    run_tests_results = iter([
        (True, "", []),
        (False, "AssertionError: message empty", []),
        (True, "", []),
    ])

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline._TDD_ENABLED", True), \
         patch("agent.pipeline.run_tests", side_effect=lambda *a, **kw: next(run_tests_results)):
        stats, _ = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "Find laptops", pre, {})

    # EXECUTE called only once (one SQL cycle), SQL skipped on cycle 2
    assert stats["outcome"] == "OUTCOME_OK"
    # vm.exec call count: 1 EXPLAIN + 1 EXECUTE = 2 (not 4 which would mean 2 SQL cycles)
    assert vm.exec.call_count == 2
