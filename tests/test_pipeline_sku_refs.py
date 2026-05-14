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


def test_extract_sku_refs_hierarchical_path_preserved():
    """Raw hierarchical paths stored verbatim in sku_refs."""
    results = ["path,sku\n/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json,HND-6D7TN1CT\n"]
    refs = _extract_sku_refs(["SELECT p.path, p.sku FROM products p"], results)
    assert refs == ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"]


def test_build_answer_user_msg_preserves_hierarchical_ref():
    """AUTO_REFS block must show full paths — LLM copies them verbatim to grounding_refs."""
    msg = _build_answer_user_msg(
        "find hand tool",
        ["sku\nHND-6D7TN1CT\n"],
        ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"],
    )
    assert "/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json" in msg


def test_clean_refs_stem_match_normalizes():
    """clean_refs accepts model output in any format, outputs short-form."""
    from pathlib import Path
    from agent.pipeline import _to_short_ref
    sku_refs = ["/proc/catalog/hand_tools/subcat/HND-6D7TN1CT.json"]
    result_skus = {Path(r).stem for r in sku_refs}
    grounding_refs = ["/proc/catalog/HND-6D7TN1CT.json"]  # model used short form
    clean = [_to_short_ref(r) for r in grounding_refs if Path(r).stem in result_skus]
    assert clean == ["/proc/catalog/HND-6D7TN1CT.json"]
