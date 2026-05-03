"""Tests for scripts/visualize_graph.py API endpoints."""
import math
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="viz group not installed (uv sync --group viz)")
pytest.importorskip("uvicorn", reason="viz group not installed (uv sync --group viz)")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client with a fake graph of 4 nodes covering all types."""
    import visualize_graph as vg

    fake_graph = vg.Graph(
        nodes={
            "n_ins1": {"type": "insight", "tags": ["email"], "text": "Insight one",
                       "confidence": 0.9, "uses": 5, "last_seen": "2026-04-29"},
            "r_rule1": {"type": "rule", "tags": ["email", "workflow"], "text": "Rule one",
                        "confidence": 0.6, "uses": 1, "last_seen": "2026-04-29"},
            "a_anti1": {"type": "antipattern", "tags": ["crm"], "text": "Antipattern one",
                        "confidence": 0.4, "uses": 2, "last_seen": "2026-04-29"},
            "p_pat1": {"type": "pattern", "tags": ["email"], "text": "Pattern one",
                       "confidence": 0.8, "uses": 3, "last_seen": "2026-04-29"},
        },
        edges=[{"from": "p_pat1", "rel": "requires", "to": "n_ins1"}],
    )
    monkeypatch.setattr(vg, "load_graph", lambda: fake_graph)
    return TestClient(vg.app)


def test_get_graph_returns_all_nodes(client):
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 4
    assert len(data["edges"]) == 1


def test_filter_by_tag(client):
    resp = client.get("/api/graph?tag=email")
    data = resp.json()
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"n_ins1", "r_rule1", "p_pat1"}


def test_filter_by_type(client):
    resp = client.get("/api/graph?type=rule")
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "r_rule1"


def test_filter_by_min_confidence(client):
    resp = client.get("/api/graph?min_confidence=0.7")
    data = resp.json()
    ids = {n["id"] for n in data["nodes"]}
    assert ids == {"n_ins1", "p_pat1"}


def test_edges_filtered_to_visible_nodes(client):
    # только antipattern виден, но edge идёт от pattern к insight — оба скрыты
    resp = client.get("/api/graph?type=antipattern")
    data = resp.json()
    assert len(data["edges"]) == 0


def test_node_size_formula(client):
    resp = client.get("/api/graph?type=insight")
    data = resp.json()
    node = data["nodes"][0]
    expected = round(10 + math.log(5 + 1) * 8, 4)
    assert abs(node["size"] - expected) < 0.01


def test_node_opacity_formula(client):
    resp = client.get("/api/graph?type=insight")
    data = resp.json()
    node = data["nodes"][0]
    expected = round(0.4 + 0.9 * 0.6, 4)
    assert abs(node["opacity"] - expected) < 0.01


def test_node_color_by_type(client):
    resp = client.get("/api/graph")
    data = resp.json()
    colors = {n["id"]: n["color"]["background"] for n in data["nodes"]}
    assert colors["n_ins1"] == "#3b82f6"
    assert colors["r_rule1"] == "#22c55e"
    assert colors["a_anti1"] == "#ef4444"
    assert colors["p_pat1"] == "#f59e0b"


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "vis-network" in resp.text
