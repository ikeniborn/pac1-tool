"""Tests for ExecutorAgent (Task 9)."""
from __future__ import annotations

import pytest


def test_executor_agent_imports():
    from agent.agents.executor_agent import ExecutorAgent
    from agent.agents.security_agent import SecurityAgent
    from agent.agents.stall_agent import StallAgent
    from agent.agents.compaction_agent import CompactionAgent
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.agents.verifier_agent import VerifierAgent
    agent = ExecutorAgent(
        security=SecurityAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        step_guard=StepGuardAgent(),
        verifier=VerifierAgent(enabled=False),
    )
    assert agent is not None


def test_executor_input_has_model_fields():
    from agent.contracts import ExecutorInput, ExecutionPlan, WikiContext, TaskInput
    from agent.prephase import PrephaseResult
    pre = PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[{"role": "system", "content": "sys"}],
    )
    inp = ExecutorInput(
        task_input=TaskInput(
            task_text="test",
            harness_url="http://localhost",
            trial_id="t01",
        ),
        plan=ExecutionPlan(
            base_prompt="sys",
            addendum="",
            contract=None,
            route="EXECUTE",
            in_tokens=0,
            out_tokens=0,
        ),
        wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
        prephase=pre,
        harness_url="http://localhost",
        task_type="default",
        model="claude-3-5-haiku-20241022",
        model_cfg={"max_completion_tokens": 4096},
        evaluator_model="",
        evaluator_cfg={},
    )
    assert inp.model == "claude-3-5-haiku-20241022"
    assert inp.plan.route == "EXECUTE"


def test_run_loop_accepts_di_params():
    """run_loop must accept _security_agent etc. as optional kwargs without error."""
    import inspect
    from agent.loop import run_loop
    sig = inspect.signature(run_loop)
    params = set(sig.parameters.keys())
    assert "_security_agent" in params
    assert "_stall_agent" in params
    assert "_compaction_agent" in params
    assert "_step_guard_agent" in params
    assert "_verifier_agent" in params


def test_executor_agent_converts_step_facts_to_dicts():
    """ExecutorAgent.run must convert _StepFact dataclasses to dicts before passing to ExecutionResult."""
    from unittest.mock import patch, MagicMock
    from agent.agents.executor_agent import ExecutorAgent
    from agent.agents.security_agent import SecurityAgent
    from agent.agents.stall_agent import StallAgent
    from agent.agents.compaction_agent import CompactionAgent
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import ExecutorInput, ExecutionPlan, WikiContext, TaskInput
    from agent.prephase import PrephaseResult
    from agent.log_compaction import _StepFact

    sf = _StepFact(kind="read", path="/contacts/alice.json", summary="read ok")

    pre = PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[{"role": "system", "content": "sys"}],
    )
    inp = ExecutorInput(
        task_input=TaskInput(task_text="test", harness_url="http://localhost", trial_id=""),
        plan=ExecutionPlan(base_prompt="sys", addendum="", contract=None, route="EXECUTE", in_tokens=0, out_tokens=0),
        wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
        prephase=pre,
        harness_url="http://localhost",
        task_type="default",
        model="test-model",
        model_cfg={},
        evaluator_model="",
        evaluator_cfg={},
    )
    agent = ExecutorAgent(
        security=SecurityAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        step_guard=StepGuardAgent(),
        verifier=VerifierAgent(enabled=False),
    )

    with patch("agent.loop.run_loop") as mock_loop, \
         patch("bitgn.vm.pcm_connect.PcmRuntimeClientSync"):
        mock_loop.return_value = {
            "outcome": "OUTCOME_OK",
            "step_facts": [sf],
            "graph_injected_node_ids": [],
            "evaluator_rejections": 0,
        }
        result = agent.run(inp)  # must NOT raise pydantic ValidationError

    assert result.step_facts == [
        {"kind": "read", "path": "/contacts/alice.json", "summary": "read ok", "error": ""}
    ]
