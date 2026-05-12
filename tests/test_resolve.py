import pytest
from unittest.mock import MagicMock, patch
from agent.resolve import _security_check, _first_value, run_resolve
from agent.prephase import PrephaseResult


def test_security_check_allows_ilike():
    assert _security_check("SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10") is None


def test_security_check_allows_distinct():
    assert _security_check("SELECT DISTINCT name FROM kinds WHERE name ILIKE '%screw%' LIMIT 10") is None


def test_security_check_blocks_drop():
    err = _security_check("DROP TABLE products")
    assert err is not None
    assert "DDL" in err or "not allowed" in err


def test_security_check_blocks_insert():
    err = _security_check("INSERT INTO products VALUES (1)")
    assert err is not None


def test_security_check_blocks_query_without_ilike_or_distinct():
    err = _security_check("SELECT brand FROM products WHERE brand = 'Heco'")
    assert err is not None
    assert "ILIKE" in err or "DISTINCT" in err


def test_first_value_returns_first_data_cell():
    csv_text = "brand\nHeco\nMaker"
    assert _first_value(csv_text) == "Heco"


def test_first_value_returns_none_for_header_only():
    assert _first_value("brand\n") is None


def test_first_value_returns_none_for_empty():
    assert _first_value("") is None


def test_first_value_strips_quotes():
    csv_text = 'brand\n"Heco GmbH"'
    assert _first_value(csv_text) == "Heco GmbH"


def _make_pre(agents_md_index=None, schema_digest=None):
    return PrephaseResult(
        agents_md_index=agents_md_index or {"brand_aliases": ["heco = Heco"]},
        schema_digest=schema_digest or {"top_keys": ["diameter_mm", "screw_type"]},
    )


def test_run_resolve_returns_confirmed_values():
    vm = MagicMock()
    exec_r = MagicMock(); exec_r.stdout = "brand\nHeco"
    vm.exec.return_value = exec_r

    raw_response = '{"reasoning": "found brand", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE \'%heco%\' LIMIT 10"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "test-model", "find Heco products", _make_pre(), {})

    assert "brand" in result
    assert "Heco" in result["brand"]


def test_run_resolve_blocks_unsafe_query():
    vm = MagicMock()

    raw_response = '{"reasoning": "x", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "DROP TABLE products"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "test-model", "task", _make_pre(), {})

    vm.exec.assert_not_called()
    assert result == {}


def test_run_resolve_returns_empty_on_llm_failure():
    with patch("agent.resolve.call_llm_raw", return_value=None):
        result = run_resolve(MagicMock(), "model", "task", _make_pre(), {})
    assert result == {}


def test_run_resolve_returns_empty_on_exception():
    with patch("agent.resolve.call_llm_raw", side_effect=Exception("network error")):
        result = run_resolve(MagicMock(), "model", "task", _make_pre(), {})
    assert result == {}


def test_run_resolve_accumulates_multiple_fields():
    vm = MagicMock()
    def _exec(req):
        r = MagicMock()
        if "brand" in req.args[0]:
            r.stdout = "brand\nHeco"
        else:
            r.stdout = "name\nwood screw"
        return r
    vm.exec.side_effect = _exec

    raw_response = '{"reasoning": "found two", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE \'%heco%\' LIMIT 10"}, {"term": "screw", "field": "kind", "discovery_query": "SELECT DISTINCT name FROM kinds WHERE name ILIKE \'%screw%\' LIMIT 10"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "model", "find Heco screws", _make_pre(), {})

    assert result.get("brand") == ["Heco"]
    assert result.get("kind") == ["wood screw"]
