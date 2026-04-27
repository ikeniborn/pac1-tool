"""Tests for wiki_graph retrieval scoring formula."""
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
        "n1": {"type": "rule", "text": "x", "tags": [], "confidence": 1.0, "uses": 1},
        "n2": {"type": "rule", "text": "x", "tags": [], "confidence": 1.0, "uses": 2},
    })
    results = _score_candidates(g, "other", "", 0.0, None, False)
    scores = {nid: s for s, nid, _ in results}
    # base(uses=1) = log(2) ≈ 0.693, base(uses=2) = log(3) ≈ 1.099
    assert abs(scores["n1"] - math.log(2)) < 0.01
    assert abs(scores["n2"] - math.log(3)) < 0.01


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
