"""Fixtures for tests/regression/.

Builds on top of `tests/conftest.py` which already stubs heavy externals
(protobuf, anthropic, connectrpc, bitgn). Do NOT re-stub those here.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture
def fake_connect_error():
    """Factory: build an exception compatible with `connectrpc.errors.ConnectError`.

    Reuses the stub class registered in `tests/conftest.py` so `isinstance()`
    checks against `connectrpc.errors.ConnectError` keep working.
    """
    ConnectError = sys.modules["connectrpc.errors"].ConnectError

    def _make(code: str, message: str = ""):
        err = ConnectError(message)
        err.code = code
        err.message = message
        return err

    return _make


@pytest.fixture
def fake_reflection():
    """Factory: build an `agent.reflector.Reflection` with sensible defaults."""
    from agent.reflector import Reflection

    def _make(
        outcome: str = "stuck",
        what_failed: list | None = None,
        graph_deltas: dict | None = None,
        hypothesis: str = "",
        goal_shape: str = "",
        final_answer: str = "",
        what_worked: list | None = None,
    ) -> Reflection:
        return Reflection(
            outcome=outcome,
            goal_shape=goal_shape,
            final_answer=final_answer,
            what_worked=list(what_worked) if what_worked else [],
            what_failed=list(what_failed) if what_failed else [],
            hypothesis_for_next=hypothesis,
            graph_deltas=dict(graph_deltas) if graph_deltas else {},
        )

    return _make


@pytest.fixture
def fake_step_fact():
    """Factory: build an `agent.log_compaction._StepFact`."""
    from agent.log_compaction import _StepFact

    def _make(kind: str, path: str, summary: str = "", error: str = "") -> _StepFact:
        return _StepFact(kind=kind, path=path, summary=summary, error=error)

    return _make


@pytest.fixture
def fake_graph():
    """Factory: build a synthetic `agent.wiki_graph.Graph`."""
    from agent.wiki_graph import Graph

    def _make(nodes_dict: dict | None = None) -> Graph:
        return Graph(nodes=dict(nodes_dict) if nodes_dict else {}, edges=[])

    return _make


@pytest.fixture
def fake_cycle_stats():
    """Factory: build a researcher cycle_stats dict.

    Mirrors the shape produced by `agent.loop._st_to_result`.
    """
    def _make(outcome: str, **kw) -> dict:
        base = {
            "outcome": outcome,
            "step_facts": [],
            "done_ops": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "llm_elapsed_ms": 0,
            "ollama_eval_count": 0,
            "ollama_eval_ms": 0,
            "step_count": 0,
            "llm_call_count": 0,
            "evaluator_calls": 0,
            "evaluator_rejections": 0,
            "evaluator_ms": 0,
            "stall_hints": [],
            "report": None,
        }
        base.update(kw)
        return base

    return _make
