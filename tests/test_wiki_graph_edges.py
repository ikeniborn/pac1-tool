"""Tests for FIX-411: deterministic and text-reference edges in merge_updates."""
from agent.wiki_graph import Graph, merge_updates


def test_deterministic_edge_antipattern_conflicts_with_rule():
    """antipattern and rule with overlapping tags in same batch → conflicts_with edge."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
    }
    merge_updates(g, updates)
    rels = [(e["from"], e["rel"], e["to"]) for e in g.edges]
    conflicts = [r for r in rels if r[1] == "conflicts_with"]
    assert len(conflicts) == 1, f"expected 1 conflicts_with edge, got: {rels}"
    apt_nid, _, rule_nid = conflicts[0]
    assert g.nodes[apt_nid]["type"] == "antipattern"
    assert g.nodes[rule_nid]["type"] == "rule"


def test_deterministic_edge_not_built_when_tags_disjoint():
    """No edge when antipattern and rule have no tag overlap."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["lookup"]}],
    }
    merge_updates(g, updates)
    assert g.edges == [], f"unexpected edges: {g.edges}"


def test_no_duplicate_deterministic_edges():
    """Calling merge_updates twice does not duplicate the edge."""
    g = Graph()
    updates = {
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
    }
    merge_updates(g, updates)
    merge_updates(g, updates)
    conflicts = [e for e in g.edges if e["rel"] == "conflicts_with"]
    assert len(conflicts) == 1, f"duplicate edges: {g.edges}"


def test_text_reference_edge_resolved():
    """LLM may emit edges with text refs instead of node IDs — must resolve."""
    g = Graph()
    updates = {
        "new_rules":    [{"text": "read before write", "tags": ["email"]}],
        "antipatterns": [{"text": "avoid reading twice", "tags": ["email"]}],
        "edges": [
            {
                "from": "avoid reading twice",
                "rel": "conflicts_with",
                "to": "read before write",
            }
        ],
    }
    merge_updates(g, updates)
    assert len(g.edges) >= 1
    rels = {e["rel"] for e in g.edges}
    assert "conflicts_with" in rels


def test_invalid_text_reference_edge_silently_dropped():
    """Edge referencing non-existent text is silently ignored (fail-open)."""
    g = Graph()
    updates = {
        "new_rules": [{"text": "read before write", "tags": ["email"]}],
        "edges": [
            {"from": "this node does not exist", "rel": "requires", "to": "read before write"}
        ],
    }
    merge_updates(g, updates)
    assert len(g.nodes) == 1
    assert g.edges == []
