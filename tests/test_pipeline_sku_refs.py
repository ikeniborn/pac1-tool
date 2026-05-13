from agent.pipeline import _extract_sku_refs, _build_answer_user_msg


def test_extract_sku_refs_single_result():
    queries = ["SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"]
    results = ["sku,brand\nHCO-AAA111,Heco\nHCO-BBB222,Heco\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == ["/proc/catalog/HCO-AAA111.json", "/proc/catalog/HCO-BBB222.json"]


def test_extract_sku_refs_no_sku_column():
    queries = ["SELECT p.brand FROM products p"]
    results = ["brand\nHeco\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == []


def test_extract_sku_refs_empty_result():
    queries = ["SELECT p.sku FROM products p WHERE p.brand = 'X'"]
    results = ["sku\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == []


def test_extract_sku_refs_multiple_queries():
    queries = [
        "SELECT DISTINCT brand FROM products WHERE brand LIKE '%Heco%'",
        "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'",
    ]
    results = [
        "brand\nHeco\n",
        "sku,brand\nHCO-AAA111,Heco\n",
    ]
    refs = _extract_sku_refs(queries, results)
    assert refs == ["/proc/catalog/HCO-AAA111.json"]


def test_build_answer_user_msg_with_refs():
    msg = _build_answer_user_msg("find Heco", ["sku,brand\nHCO-AAA111,Heco\n"], ["/proc/catalog/HCO-AAA111.json"])
    assert "AUTO_REFS" in msg
    assert "/proc/catalog/HCO-AAA111.json" in msg


def test_build_answer_user_msg_no_refs():
    msg = _build_answer_user_msg("find Heco", ["brand\nHeco\n"], [])
    assert "AUTO_REFS" not in msg
