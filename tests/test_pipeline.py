import json
from unittest.mock import MagicMock, patch, call
import pytest
from agent.pipeline import run_pipeline, _extract_discovery_results, _format_confirmed_values, _format_schema_digest
from agent.prephase import PrephaseResult
from pathlib import Path


def _make_pre(agents_md="AGENTS", db_schema="CREATE TABLE products(id INT, type TEXT, brand TEXT, sku TEXT, model TEXT)"):
    return PrephaseResult(
        agents_md_content=agents_md,
        agents_md_path="/AGENTS.MD",
        db_schema=db_schema,
    )


def _sql_plan_json(queries=None):
    return json.dumps({
        "reasoning": "products table has type column",
        "queries": queries or ["SELECT COUNT(*) FROM products WHERE type='Lawn Mower'"],
    })


def _answer_json(outcome="OUTCOME_OK", message="<YES> 3 found"):
    return json.dumps({
        "reasoning": "SQL returned 3 rows",
        "message": message,
        "outcome": outcome,
        "grounding_refs": ["/proc/catalog/ABC-001.json"],
        "completed_steps": ["ran SQL", "found products"],
    })


def _make_exec_result(stdout="[{\"count\":3}]"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_happy_path(tmp_path):
    """SQL_PLAN → VALIDATE ok → EXECUTE ok → ANSWER ok."""
    vm = MagicMock()
    # VALIDATE (EXPLAIN) returns no error
    # EXECUTE returns rows
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many Lawn Mowers?", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    vm.answer.assert_called_once()
    answer_req = vm.answer.call_args[0][0]
    assert answer_req.message == "<YES> 3 found"


def test_validate_error_triggers_learn_and_retry(tmp_path):
    """EXPLAIN returns error → LEARN called → SQL_PLAN retried → success."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result("Error: no such table: produts"),
        _make_exec_result(""),
        _make_exec_result('[{"count": 1}]'),
    ]

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "typo in table name",
        "conclusion": "Table is 'products' not 'produts'",
        "rule_content": "Always spell table name as 'products'.",
    })

    call_seq = [_sql_plan_json(["SELECT COUNT(*) FROM produts WHERE type='X'"]),
                learn_json,
                _sql_plan_json(),
                _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many?", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"


def test_max_cycles_exhausted_returns_clarification(tmp_path):
    """3 cycles all fail → OUTCOME_NONE_CLARIFICATION without ANSWER LLM call."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "x", "conclusion": "y", "rule_content": "z",
    })
    call_seq = [_sql_plan_json(), learn_json] * 3
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "?", pre, {})

    assert stats["outcome"] == "OUTCOME_NONE_CLARIFICATION"
    vm.answer.assert_called_once()


def test_security_gate_ddl_triggers_learn(tmp_path):
    """DDL query → security gate blocks → LEARN → retry → success."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result(""),
        _make_exec_result('[{"id": 1}]'),
    ]

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    ddl_gate = [{"id": "sec-001", "pattern": "^\\s*(DROP|INSERT|UPDATE|DELETE|ALTER|CREATE)",
                 "action": "block", "message": "DDL/DML prohibited"}]

    learn_json = json.dumps({
        "reasoning": "used DROP", "conclusion": "only SELECT allowed",
        "rule_content": "Never use DDL statements.",
    })
    call_seq = [
        _sql_plan_json(["DROP TABLE products"]),
        learn_json,
        _sql_plan_json(),
        _answer_json(),
    ]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=ddl_gate), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "drop test", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"


def test_learn_does_not_persist_auto_rule(tmp_path):
    """LEARN updates session_rules but does not write rule files (append_rule removed)."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result("Error: syntax error"),
        _make_exec_result(""),
        _make_exec_result('[{"count": 1}]'),
    ]
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "x", "conclusion": "y", "rule_content": "Never do X.",
    })
    call_seq = [_sql_plan_json(), learn_json, _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "count X", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    # append_rule has been removed — no auto YAML files should be written
    assert not hasattr(__import__("agent.rules_loader", fromlist=["RulesLoader"]).RulesLoader, "append_rule")
    written_files = list(rules_dir.glob("*.yaml"))
    assert written_files == [], f"No rule files should be written, found: {written_files}"


def test_extract_discovery_results_basic():
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco\nMaker"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv.get("brand") == ["Heco", "Maker"]


def test_extract_discovery_results_skips_non_distinct():
    queries = ["SELECT sku FROM products WHERE brand = 'Heco'"]
    results = ["sku\nABC-001"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv == {}


def test_extract_discovery_results_accumulates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%maker%' LIMIT 10"]
    results = ["brand\nMaker"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco", "Maker"]


def test_extract_discovery_results_no_duplicates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco"]


def test_format_confirmed_values_single():
    cv = {"brand": ["Heco"]}
    text = _format_confirmed_values(cv)
    assert 'brand → confirmed: "Heco"' in text


def test_format_confirmed_values_multiple():
    cv = {"kind": ["wood screw", "self-tapping screw"]}
    text = _format_confirmed_values(cv)
    assert "wood screw" in text
    assert "self-tapping screw" in text


def test_format_schema_digest_lists_tables():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku", "type": "TEXT"}, {"name": "brand", "type": "TEXT"}]}
        },
        "top_keys": ["diameter_mm"],
    }
    text = _format_schema_digest(digest)
    assert "products" in text
    assert "sku" in text
    assert "diameter_mm" in text
