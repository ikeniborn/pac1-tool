import pytest
from unittest.mock import MagicMock, patch
import json
from agent.resolve import _security_check, _all_values, run_resolve
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


def test_all_values_first_row_compat():
    assert _all_values("brand\nHeco\nMaker") == ["Heco", "Maker"]


def test_all_values_strips_quotes_first_row():
    assert _all_values('brand\n"Heco GmbH"') == ["Heco GmbH"]


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


def test_all_values_returns_all_rows():
    csv_text = "value_text\n3XL\nL\nXL\nXXL\n"
    assert _all_values(csv_text) == ["3XL", "L", "XL", "XXL"]


def test_all_values_returns_empty_for_header_only():
    assert _all_values("brand\n") == []


def test_all_values_returns_empty_for_empty_string():
    assert _all_values("") == []


def test_all_values_strips_quotes():
    csv_text = 'brand\n"Heco GmbH"\n"Maker Inc"'
    assert _all_values(csv_text) == ["Heco GmbH", "Maker Inc"]


def test_run_resolve_stores_all_matching_values():
    """When discovery returns 3XL, L, XL, XXL — all four must be in confirmed_values."""
    vm = MagicMock()
    exec_r = MagicMock()
    exec_r.stdout = "value_text\n3XL\nL\nXL\nXXL\n"
    vm.exec.return_value = exec_r

    raw = json.dumps({
        "reasoning": "size values",
        "candidates": [{"term": "L", "field": "attr_value",
                         "discovery_query": "SELECT DISTINCT value_text FROM product_properties WHERE key = 'size' AND value_text LIKE '%L%' LIMIT 10"}]
    })
    with patch("agent.resolve.call_llm_raw", return_value=raw):
        result = run_resolve(vm, "model", "find size L product", _make_pre(), {})

    assert "attr_value" in result
    assert "L" in result["attr_value"]
    assert "3XL" in result["attr_value"]


def test_resolve_system_includes_schema_digest():
    from agent.resolve import _build_resolve_system
    from agent.prephase import PrephaseResult
    pre = PrephaseResult(
        agents_md_index={"PRODUCTS": ["intro"]},
        schema_digest={
            "tables": {
                "product_kinds": {
                    "columns": [{"name": "id", "type": "INTEGER"}, {"name": "category_id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}],
                    "role": "kinds",
                }
            },
            "top_keys": ["voltage"],
            "value_type_map": {"voltage": "text"},
        },
    )
    system = _build_resolve_system(pre)
    assert "SCHEMA DIGEST" in system
    assert "product_kinds" in system
    assert "role=kinds" in system
