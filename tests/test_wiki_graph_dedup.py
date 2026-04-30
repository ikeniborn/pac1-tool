"""Tests for FIX-421: dedup before antipattern node insertion."""
from agent.wiki_graph import Graph, _token_overlap, _find_near_duplicate, merge_updates


def test_token_overlap_identical():
    assert _token_overlap("relative date queries fail", "relative date queries fail") == 1.0


def test_token_overlap_partial():
    score = _token_overlap("relative date queries fail on lookup", "date queries fail vault")
    assert 0.4 < score < 1.0


def test_token_overlap_disjoint():
    assert _token_overlap("write file to outbox", "search contact by name") < 0.2


def test_find_near_duplicate_finds_match():
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Relative date queries fail because file naming lacks parseable capture dates",
        "tags": ["lookup"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-30",
    }
    dup = _find_near_duplicate(g, "antipattern", "Relative date queries fail; file naming lacks parseable dates")
    assert dup == "a_existing"


def test_find_near_duplicate_no_match():
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Write files only to outbox, never to inbox",
        "tags": ["email"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-30",
    }
    dup = _find_near_duplicate(g, "antipattern", "Relative date queries fail on lookup tasks")
    assert dup is None


def test_find_near_duplicate_ignores_different_type():
    g = Graph()
    g.nodes["n_existing"] = {
        "type": "insight",
        "text": "Relative date queries fail because file naming lacks parseable capture dates",
        "tags": ["lookup"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-30",
    }
    dup = _find_near_duplicate(g, "antipattern", "Relative date queries fail; file naming lacks parseable dates")
    assert dup is None


def test_merge_updates_dedup_antipattern():
    """FIX-421: near-duplicate antipattern bumps uses instead of creating new node."""
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Relative date queries fail because file naming lacks parseable capture dates",
        "tags": ["lookup"],
        "confidence": 0.6,
        "uses": 2,
        "last_seen": "2026-04-29",
    }
    before_count = len(g.nodes)

    merge_updates(g, {
        "antipatterns": [{
            "text": "Relative date queries fail; file naming lacks parseable dates in captures",
            "tags": ["lookup"],
        }]
    })

    assert len(g.nodes) == before_count, "near-duplicate should not create a new node"
    assert g.nodes["a_existing"]["uses"] == 3, "uses should be bumped"


def test_merge_updates_no_dedup_for_distinct_antipattern():
    """FIX-421: distinct antipattern creates a new node as usual."""
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Write files only to outbox, never to inbox",
        "tags": ["email"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-29",
    }
    before_count = len(g.nodes)

    merge_updates(g, {
        "antipatterns": [{
            "text": "Relative date queries fail on lookup tasks",
            "tags": ["lookup"],
        }]
    })

    assert len(g.nodes) == before_count + 1, "distinct antipattern should create a new node"
