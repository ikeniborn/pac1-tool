"""Tests for Orchestrator module (Task 10)."""
from __future__ import annotations

import inspect


def test_orchestrator_imports():
    from agent.orchestrator import run_agent
    assert callable(run_agent)


def test_orchestrator_signature():
    from agent.orchestrator import run_agent
    sig = inspect.signature(run_agent)
    params = list(sig.parameters)
    assert "router" in params
    assert "harness_url" in params
    assert "task_text" in params


def test_write_wiki_fragment_importable():
    from agent.orchestrator import write_wiki_fragment
    assert callable(write_wiki_fragment)


def test_agent_init_re_exports():
    """agent.__init__ must still export run_agent and write_wiki_fragment."""
    from agent import run_agent, write_wiki_fragment
    assert callable(run_agent)
    assert callable(write_wiki_fragment)
