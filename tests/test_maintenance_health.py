import json
import pytest
from pathlib import Path
from agent.maintenance.health import run_health_check, HealthResult


def _write_graph(path: Path, nodes: dict, edges: list = None) -> None:
    path.write_text(json.dumps({"nodes": nodes, "edges": edges or []}), encoding="utf-8")


def test_missing_file_returns_ok(tmp_path):
    result = run_health_check(graph_path=tmp_path / "missing.json")
    assert isinstance(result, HealthResult)
    assert result.exit_code == 0


def test_empty_graph_ok(tmp_path):
    gp = tmp_path / "graph.json"
    _write_graph(gp, {})
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 0
    assert result.contaminated_ids == []
    assert result.orphan_count == 0


def test_contamination_above_ratio_is_fail(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {
        "bad": {
            "type": "antipattern", "tags": [],
            "text": "INVALID_ARGUMENT error from harness",
            "confidence": 0.9, "uses": 1, "last_seen": "2026-05-03",
        }
    }
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp, keywords=["invalid_argument"], fail_ratio=0.0)
    assert result.exit_code == 2
    assert "bad" in result.contaminated_ids


def test_contamination_below_ratio_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    good = {f"g{i}": {"type": "rule", "tags": [], "text": f"tip {i}", "confidence": 0.9,
                       "uses": 1, "last_seen": "2026"} for i in range(99)}
    good["bad"] = {"type": "antipattern", "tags": [], "text": "invalid_argument",
                   "confidence": 0.9, "uses": 1, "last_seen": "2026"}
    _write_graph(gp, good)
    result = run_health_check(graph_path=gp, keywords=["invalid_argument"], fail_ratio=0.05)
    assert result.exit_code == 1  # 1/100 = 1% <= 5%, WARN not FAIL


def test_orphan_edge_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {"n1": {"type": "rule", "tags": [], "text": "tip", "confidence": 0.9, "uses": 1, "last_seen": "2026"}}
    edges = [{"from": "n1", "rel": "requires", "to": "MISSING"}]
    _write_graph(gp, nodes, edges)
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 1
    assert result.orphan_count == 1


def test_low_confidence_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {"n1": {"type": "rule", "tags": [], "text": "tip", "confidence": 0.05,
                    "uses": 1, "last_seen": "2026"}}
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp, conf_threshold=0.2)
    assert result.exit_code == 1
    assert result.low_conf_count == 1


def test_invalid_json_is_fail(tmp_path):
    gp = tmp_path / "graph.json"
    gp.write_text("{not valid json}", encoding="utf-8")
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 2


def test_duplicate_text_is_warn(tmp_path):
    gp = tmp_path / "graph.json"
    nodes = {
        "n1": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.9, "uses": 1, "last_seen": "2026"},
        "n2": {"type": "rule", "tags": [], "text": "same text", "confidence": 0.8, "uses": 1, "last_seen": "2026"},
    }
    _write_graph(gp, nodes)
    result = run_health_check(graph_path=gp)
    assert result.exit_code == 1
    assert len(result.duplicate_pairs) == 1
