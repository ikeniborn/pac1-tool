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
