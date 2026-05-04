"""Tests for wiki_graph retrieval scoring formula and task-type hard filtering."""
import math

from agent.wiki_graph import Graph, _score_candidates


def _make_graph(nodes: dict) -> Graph:
    return Graph(nodes=nodes, edges=[])


def test_new_node_uses1_has_nonzero_base():
    """uses=1 node must produce positive base score (not zero-killed by log)."""
    g = _make_graph({
        "n1": {"type": "insight", "text": "foo bar", "tags": ["email"], "confidence": 0.5, "uses": 1}
    })
    results = _score_candidates(g, "email", "foo bar task", 0.0, None, False)
    assert len(results) == 1
    score, nid, _ = results[0]
    # base = 0.5 * log(1+1) = 0.5 * log(2) ≈ 0.347
    # tag_score = 2.0, overlap ≥ 1.0 (foo, bar match)
    assert score > 2.0 + 0.3   # conservatively above tag+base only


def test_high_uses_node_scores_higher_than_new():
    """uses=40 node should rank above uses=1 node with same tag and text."""
    g = _make_graph({
        "hot": {"type": "insight", "text": "send email contact", "tags": ["email"],
                "confidence": 0.8, "uses": 40},
        "new": {"type": "insight", "text": "send email contact", "tags": ["email"],
                "confidence": 0.8, "uses": 1},
    })
    results = _score_candidates(g, "email", "send email contact", 0.0, None, False)
    scores = {nid: s for s, nid, _ in results}
    assert scores["hot"] > scores["new"]


def test_log_formula_smoothing():
    """Verify the exact formula: base = conf * log(uses + 1)."""
    g = _make_graph({
        "n1": {"type": "rule", "text": "x", "tags": ["other"], "confidence": 1.0, "uses": 1},
        "n2": {"type": "rule", "text": "x", "tags": ["other"], "confidence": 1.0, "uses": 2},
    })
    results = _score_candidates(g, "other", "", 0.0, None, False)
    scores = {nid: s for s, nid, _ in results}
    # base(uses=1) = log(2) ≈ 0.693, base(uses=2) = log(3) ≈ 1.099
    # tag_score = 2.0 for both (tag matches task_type)
    assert abs(scores["n1"] - (2.0 + math.log(2))) < 0.01
    assert abs(scores["n2"] - (2.0 + math.log(3))) < 0.01


# ---------------------------------------------------------------------------
# Hard-filter tests (FIX-433)
# ---------------------------------------------------------------------------

SAMPLE_NODES = {
    "n1": {
        "text": "Temporal triangulation: add N days to VAULT_DATE to find today",
        "type": "rule",
        "tags": ["temporal"],
        "confidence": 0.9,
        "uses": 5,
    },
    "n2": {
        "text": "For account lookup, list accounts/ directory first",
        "type": "rule",
        "tags": ["lookup"],
        "confidence": 0.9,
        "uses": 5,
    },
    "n3": {
        "text": "Always verify file existence before reading",
        "type": "rule",
        "tags": ["general"],
        "confidence": 0.9,
        "uses": 5,
    },
    "n4": {
        "text": "all_types node: applies everywhere",
        "type": "insight",
        "tags": ["all_types"],
        "confidence": 0.8,
        "uses": 3,
    },
}


def _scored_texts(task_type: str, task_text: str = "do something") -> list[str]:
    g = _make_graph(SAMPLE_NODES)
    results = _score_candidates(g, task_type, task_text, 0.0, None, False)
    return [node["text"] for _, _, node in results]


def test_temporal_node_excluded_from_lookup_task():
    """Temporal nodes must NOT appear when task_type='lookup'."""
    texts = _scored_texts("lookup", "find account for manager")
    assert not any("VAULT_DATE" in t or "triangulation" in t for t in texts), \
        "Temporal node leaked into lookup task results"


def test_lookup_node_included_in_lookup_task():
    """Lookup-tagged nodes MUST appear for task_type='lookup'."""
    texts = _scored_texts("lookup", "find account for manager")
    assert any("accounts/" in t for t in texts), \
        "Lookup node missing from lookup task results"


def test_general_node_included_in_any_task():
    """'general'-tagged nodes must appear for any task_type."""
    for task_type in ["lookup", "temporal", "crm", "capture"]:
        texts = _scored_texts(task_type)
        assert any("verify file existence" in t for t in texts), \
            f"'general' node missing for task_type={task_type}"


def test_all_types_node_included_in_any_task():
    """'all_types'-tagged nodes must appear for any task_type."""
    for task_type in ["lookup", "temporal", "crm"]:
        texts = _scored_texts(task_type)
        assert any("all_types node" in t for t in texts), \
            f"'all_types' node missing for task_type={task_type}"


def test_temporal_node_included_in_temporal_task():
    """Temporal nodes must appear for task_type='temporal'."""
    texts = _scored_texts("temporal", "what date is it in 5 days")
    assert any("VAULT_DATE" in t or "triangulation" in t for t in texts), \
        "Temporal node missing from temporal task results"


def test_unknown_task_type_returns_only_general_and_all_types():
    """For an unknown task_type, only 'general' and 'all_types' nodes must be returned."""
    g = _make_graph(SAMPLE_NODES)
    results = _score_candidates(g, "unknown_type", "do something", 0.0, None, False)
    for _, _, node in results:
        tags = set(node.get("tags", []))
        assert "general" in tags or "all_types" in tags, \
            f"Node with tags {tags} leaked into unknown_type results: {node['text']}"


def test_graph_feedback_lock_exists():
    """_graph_feedback_lock must be defined at module level in main.py."""
    import ast, pathlib
    src = pathlib.Path("main.py").read_text()
    tree = ast.parse(src)
    assigns = [n for n in ast.walk(tree)
               if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "_graph_feedback_lock"
                       for t in n.targets)]
    assert len(assigns) == 1, "_graph_feedback_lock not found at module level in main.py"
