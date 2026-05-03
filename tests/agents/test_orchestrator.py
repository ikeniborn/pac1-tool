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


def test_orchestrator_uses_executor_agent(monkeypatch):
    """orchestrator.run_agent must call ExecutorAgent.run, not run_loop directly."""
    import agent.orchestrator as orch
    calls = []

    class FakeExecutorAgent:
        def __init__(self, **kwargs): pass
        def run(self, inp):
            calls.append(inp)
            from agent.contracts import ExecutionResult
            return ExecutionResult(
                status="completed", outcome="OUTCOME_OK",
                token_stats={}, step_facts=[], injected_node_ids=[], rejection_count=0,
            )

    monkeypatch.setattr(orch, "ExecutorAgent", FakeExecutorAgent)
    monkeypatch.setattr(orch, "run_prephase", lambda *a, **kw: _fake_prephase())
    monkeypatch.setattr(orch, "ClassifierAgent", _FakeClassifier)
    monkeypatch.setattr(orch, "WikiGraphAgent", _FakeWikiAgent)
    monkeypatch.setattr(orch, "PlannerAgent", _FakePlanner)

    from agent.classifier import ModelRouter
    router = ModelRouter.__new__(ModelRouter)
    router.configs = {}
    router.default = "test-model"
    router.evaluator = "test-model"
    router.prompt_builder = ""
    router.classifier = ""

    orch.run_agent(router, "http://localhost", "test task")
    assert len(calls) == 1
    from agent.contracts import ExecutorInput
    assert isinstance(calls[0], ExecutorInput)


def _fake_prephase():
    from agent.prephase import PrephaseResult
    return PrephaseResult(
        log=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
        preserve_prefix=[{"role": "system", "content": "s"}],
    )

class _FakeClassifier:
    def __init__(self, **kwargs): pass
    def run(self, *a, **kw):
        from agent.contracts import ClassificationResult
        return ClassificationResult(task_type="default", model="test-model", model_cfg={}, confidence=0.0)

class _FakeWikiAgent:
    def read(self, *a, **kw):
        from agent.contracts import WikiContext
        return WikiContext(patterns_text="", graph_section="", injected_node_ids=[])

class _FakePlanner:
    def __init__(self, **kwargs): pass
    def run(self, *a, **kw):
        from agent.contracts import ExecutionPlan
        return ExecutionPlan(base_prompt="s", addendum="", contract=None,
                             route="EXECUTE", in_tokens=0, out_tokens=0)
