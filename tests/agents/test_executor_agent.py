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
