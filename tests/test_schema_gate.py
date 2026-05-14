import pytest
from agent.schema_gate import check_schema_compliance

_DIGEST = {
    "tables": {
        "products": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "brand", "type": "TEXT", "notnull": "0"},
                {"name": "model", "type": "TEXT", "notnull": "0"},
                {"name": "name", "type": "TEXT", "notnull": "0"},
            ]
        },
        "product_properties": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "key", "type": "TEXT", "notnull": "1"},
                {"name": "value_text", "type": "TEXT", "notnull": "0"},
                {"name": "value_number", "type": "REAL", "notnull": "0"},
            ]
        },
        "inventory": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "store_id", "type": "TEXT", "notnull": "1"},
                {"name": "available_today", "type": "INTEGER", "notnull": "0"},
            ]
        },
        "kinds": {
            "columns": [
                {"name": "id", "type": "INTEGER", "notnull": "1"},
                {"name": "name", "type": "TEXT", "notnull": "1"},
            ]
        },
    }
}


def test_valid_query_passes():
    q = "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products") is None


def test_unknown_column_detected():
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products")
    assert err is not None
    assert "unknown column" in err
    assert "color" in err


def test_known_columns_pass():
    q = "SELECT p.sku, p.brand, p.model FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco model") is None


def test_unverified_literal_detected():
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    # 'Heco' appears in task_text but is NOT in confirmed_values
    err = check_schema_compliance([q], _DIGEST, {}, "find Heco products")
    assert err is not None
    assert "unverified literal" in err
    assert "Heco" in err


def test_confirmed_literal_passes():
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    # 'Heco' is in confirmed_values
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products") is None


def test_literal_not_in_task_passes():
    # 'Heco' is in the query but NOT in task_text — not a user-supplied copy
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {}, "find screws") is None


def test_double_key_join_detected():
    q = (
        "SELECT p.sku FROM products p "
        "JOIN product_properties pp ON pp.sku = p.sku "
        "WHERE pp.key = 'diameter_mm' AND pp.key = 'screw_type'"
    )
    err = check_schema_compliance([q], _DIGEST, {}, "find screws")
    assert err is not None
    assert "double-key JOIN" in err


def test_separate_exists_passes():
    q = (
        "SELECT p.sku FROM products p "
        "WHERE EXISTS (SELECT 1 FROM product_properties pp WHERE pp.sku = p.sku AND pp.key = 'diameter_mm' AND pp.value_number = 3) "
        "AND EXISTS (SELECT 1 FROM product_properties pp2 WHERE pp2.sku = p.sku AND pp2.key = 'screw_type' AND pp2.value_text = 'wood screw')"
    )
    assert check_schema_compliance([q], _DIGEST, {"diameter_mm": ["3"], "screw_type": ["wood screw"]}, "find 3mm wood screws") is None


def test_empty_queries_passes():
    assert check_schema_compliance([], _DIGEST, {}, "task") is None


def test_empty_digest_skips_column_check():
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    # No tables in digest — unknown column check skipped
    assert check_schema_compliance([q], {}, {"brand": ["Heco"]}, "Heco") is None


def test_multiple_queries_first_error_returned():
    q_ok = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    q_bad = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q_ok, q_bad], _DIGEST, {"brand": ["Heco"]}, "Heco")
    assert err is not None
    assert "color" in err


def test_aliased_query_passes():
    """p.sku uses alias p → products, must not be blocked."""
    q = "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco") is None


def test_aliased_unknown_column_detected():
    """p.color uses alias p → products, color not in schema → blocked."""
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco")
    assert err is not None
    assert "unknown column" in err
    assert "color" in err


def test_like_literal_not_blocked():
    """'Festool' in LIKE context → discovery query → not blocked."""
    q = "SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'"
    err = check_schema_compliance([q], _DIGEST, {}, "find Festool products")
    assert err is None


def test_like_message_on_exact_literal():
    """Exact literal from task_text → error message mentions LIKE."""
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Festool'"
    err = check_schema_compliance([q], _DIGEST, {}, "find Festool products")
    assert err is not None
    assert "LIKE" in err
    assert "Festool" in err


def test_exists_subquery_aliases_pass():
    """pp.sku, pp.key, pp2.sku, pp2.key use aliases for product_properties → valid."""
    q = (
        "SELECT p.sku FROM products p "
        "WHERE EXISTS (SELECT 1 FROM product_properties pp WHERE pp.sku = p.sku AND pp.key = 'color') "
        "AND EXISTS (SELECT 1 FROM product_properties pp2 WHERE pp2.sku = p.sku AND pp2.key = 'weight')"
    )
    assert check_schema_compliance([q], _DIGEST, {"color": ["red"], "weight": ["1kg"]}, "find red 1kg") is None


def test_unknown_table_not_blocked():
    """Queries referencing tables absent from schema_digest are not blocked — EXPLAIN will catch them."""
    schema_digest = {
        "tables": {
            "products": {"columns": [{"name": "sku", "type": "TEXT"}, {"name": "path", "type": "TEXT"}]}
        }
    }
    q = "SELECT c.cart_id, ci.sku FROM carts c JOIN cart_items ci ON ci.cart_id = c.cart_id WHERE c.customer_id = 'x'"
    err = check_schema_compliance([q], schema_digest, {"customer_id": ["x"]}, "cart query")
    assert err is None, f"Unknown tables should not be blocked by schema gate, got: {err}"
