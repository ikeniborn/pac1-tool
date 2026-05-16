from agent.evaluator import _compute_eval_metrics
from agent.models import SddOutput


def test_agents_md_coverage_full():
    # "heco" matches "heco = Heco" content; "screw" matches "screw = bolt" content
    index = {"brand_aliases": ["heco = Heco"], "kind_synonyms": ["screw = bolt"]}
    plans = [
        SddOutput(reasoning="r", spec="s", plan=[], agents_md_refs=["brand_aliases", "kind_synonyms"])
    ]
    metrics = _compute_eval_metrics("find heco screw products", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 1.0


def test_agents_md_coverage_zero():
    # "heco" matches "heco = Heco" content, plan refs nothing
    index = {"brand_aliases": ["heco = Heco"]}
    plans = [SddOutput(reasoning="r", spec="s", plan=[], agents_md_refs=[])]
    metrics = _compute_eval_metrics("find heco products", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 0.0


def test_agents_md_coverage_no_relevant_terms():
    index = {"brand_aliases": ["heco = Heco"]}
    plans = [SddOutput(reasoning="r", spec="s", plan=[], agents_md_refs=[])]
    # "show", "shelf", "count" — none appear in "heco = heco brand_aliases"
    metrics = _compute_eval_metrics("show shelf count", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 1.0  # 0/0 → 1.0 (no relevant terms)


def test_schema_grounding_full():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku"}, {"name": "brand"}]},
        }
    }
    queries = ["SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    assert metrics["schema_grounding"] == 1.0


def test_schema_grounding_partial():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku"}]},
        }
    }
    # p.sku is known, p.color is not
    queries = ["SELECT p.sku, p.color FROM products p WHERE p.sku = 'x'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    assert 0.0 < metrics["schema_grounding"] < 1.0


def test_schema_grounding_no_table_col_refs():
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    queries = ["SELECT COUNT(*) FROM products WHERE brand = 'x'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    # No table.col refs → grounding defaults to 1.0
    assert metrics["schema_grounding"] == 1.0


def test_schema_grounding_empty_digest():
    metrics = _compute_eval_metrics("task", {}, ["SELECT p.sku FROM products p WHERE p.sku = 'x'"], {}, [])
    assert metrics["schema_grounding"] == 1.0
