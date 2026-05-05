# tests/test_postrun_outcome_gate.py
"""Block A: pattern-node ingest must be gated by outcome=OUTCOME_OK."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def _write_queue(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "graph_feedback_queue.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return p


def test_pattern_node_skipped_for_clarification_outcome(tmp_path, monkeypatch):
    """score=1.0 + outcome=OUTCOME_NONE_CLARIFICATION → no add_pattern_node call."""
    queue = _write_queue(tmp_path, [{
        "task_id": "t42",
        "task_type": "lookup",
        "score": 1.0,
        "outcome": "OUTCOME_NONE_CLARIFICATION",
        "injected": ["n_abc"],
        "trajectory": [{"tool": "find", "path": "/01_capture/"}],
    }])
    monkeypatch.setenv("WIKI_GRAPH_FEEDBACK", "1")
    monkeypatch.setattr("agent.postrun._GRAPH_FEEDBACK_QUEUE", queue)

    fake_g = MagicMock()
    with patch("agent.wiki_graph.load_graph", return_value=fake_g), \
         patch("agent.wiki_graph.bump_uses") as bump, \
         patch("agent.wiki_graph.add_pattern_node") as add_p, \
         patch("agent.wiki_graph.degrade_confidence"), \
         patch("agent.wiki_graph.save_graph"):
        from agent.postrun import _do_graph_feedback
        _do_graph_feedback()

    bump.assert_called_once()  # bump_uses still happens (positive feedback)
    add_p.assert_not_called()  # but pattern-node MUST NOT be created


def test_pattern_node_created_for_outcome_ok(tmp_path, monkeypatch):
    """score=1.0 + outcome=OUTCOME_OK → add_pattern_node IS called."""
    queue = _write_queue(tmp_path, [{
        "task_id": "t11",
        "task_type": "queue",
        "score": 1.0,
        "outcome": "OUTCOME_OK",
        "injected": ["n_def"],
        "trajectory": [{"tool": "write", "path": "/outbox/1.json"}],
    }])
    monkeypatch.setenv("WIKI_GRAPH_FEEDBACK", "1")
    monkeypatch.setattr("agent.postrun._GRAPH_FEEDBACK_QUEUE", queue)

    fake_g = MagicMock()
    with patch("agent.wiki_graph.load_graph", return_value=fake_g), \
         patch("agent.wiki_graph.bump_uses"), \
         patch("agent.wiki_graph.add_pattern_node") as add_p, \
         patch("agent.wiki_graph.hash_trajectory", return_value="h123"), \
         patch("agent.wiki_graph.degrade_confidence"), \
         patch("agent.wiki_graph.save_graph"):
        from agent.postrun import _do_graph_feedback
        _do_graph_feedback()

    add_p.assert_called_once()
