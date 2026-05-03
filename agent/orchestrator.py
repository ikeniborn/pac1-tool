"""Orchestrator: Hub-and-Spoke pipeline replacing the monolithic agent/__init__.py.

Coordinates agents via typed contracts. Agents are thin wrappers over existing
modules — no logic is rewritten here, only delegated.
"""
from __future__ import annotations

import os

from bitgn.vm.pcm_connect import PcmRuntimeClientSync

from agent.agents.classifier_agent import ClassifierAgent
from agent.agents.compaction_agent import CompactionAgent
from agent.agents.executor_agent import ExecutorAgent
from agent.agents.planner_agent import PlannerAgent
from agent.agents.security_agent import SecurityAgent
from agent.agents.stall_agent import StallAgent
from agent.agents.step_guard_agent import StepGuardAgent
from agent.agents.verifier_agent import VerifierAgent
from agent.agents.wiki_graph_agent import WikiGraphAgent
from agent.classifier import ModelRouter, TASK_PREJECT
from agent.contracts import ExecutorInput, ExecutionPlan, PlannerInput, TaskInput, WikiContext, WikiReadRequest
from agent.prephase import run_prephase
from agent.prompt import build_system_prompt
from agent.wiki import format_fragment, write_fragment


def run_agent(router: ModelRouter, harness_url: str, task_text: str) -> dict:
    """Execute a single PAC1 benchmark task. Drop-in replacement for agent.__init__.run_agent."""
    vm = PcmRuntimeClientSync(harness_url)

    pre = run_prephase(vm, task_text, "")

    task_input = TaskInput(task_text=task_text, harness_url=harness_url, trial_id="")
    classification = ClassifierAgent(router=router).run(task_input, prephase=pre)
    model = classification.model
    cfg = classification.model_cfg
    task_type = classification.task_type

    evaluator_model = router.evaluator or model
    evaluator_cfg = router._adapt_config(router.configs.get(evaluator_model, {}), "evaluator")

    if task_type == TASK_PREJECT:
        pre.log[0]["content"] = build_system_prompt(task_type)
        pre.preserve_prefix[0]["content"] = pre.log[0]["content"]
        preject_plan = ExecutionPlan(
            base_prompt=pre.log[0]["content"],
            addendum="",
            contract=None,
            route="EXECUTE",
            in_tokens=0,
            out_tokens=0,
        )
        executor = ExecutorAgent(
            security=SecurityAgent(),
            stall=StallAgent(),
            compaction=CompactionAgent(),
            step_guard=StepGuardAgent(),
            verifier=VerifierAgent(model=evaluator_model, cfg=evaluator_cfg),
        )
        result = executor.run(ExecutorInput(
            task_input=task_input,
            plan=preject_plan,
            wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
            prephase=pre,
            harness_url=harness_url,
            task_type=task_type,
            model=model,
            model_cfg=cfg,
            evaluator_model=evaluator_model,
            evaluator_cfg=evaluator_cfg,
        ))
        stats = {
            "outcome": result.outcome,
            "step_facts": result.step_facts,
            "graph_injected_node_ids": result.injected_node_ids,
            "eval_rejection_count": result.rejection_count,
            **result.token_stats,
        }
        stats["model_used"] = model
        stats["task_type"] = task_type
        stats["builder_used"] = False
        stats["builder_in_tok"] = 0
        stats["builder_out_tok"] = 0
        stats["builder_addendum"] = ""
        return stats

    wiki_agent = WikiGraphAgent()
    wiki_context = wiki_agent.read(WikiReadRequest(task_type=task_type, task_text=task_text))

    if wiki_context.patterns_text:
        for i in range(len(pre.preserve_prefix) - 1, -1, -1):
            if pre.preserve_prefix[i].get("role") == "user":
                pre.preserve_prefix[i]["content"] += f"\n\n{wiki_context.patterns_text}"
                pre.log[i]["content"] = pre.preserve_prefix[i]["content"]
                break

    builder_model = router.prompt_builder or router.classifier or model
    builder_cfg = router._adapt_config(router.configs.get(builder_model, {}), "classifier")

    # PlannerAgent mutates pre.log[0] and pre.preserve_prefix[0] in-place with the final prompt
    planner = PlannerAgent(model=builder_model, cfg=builder_cfg)
    plan = planner.run(PlannerInput(
        task_input=task_input,
        classification=classification,
        wiki_context=wiki_context,
        prephase=pre,
    ))

    executor = ExecutorAgent(
        security=SecurityAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        step_guard=StepGuardAgent(),
        verifier=VerifierAgent(model=evaluator_model, cfg=evaluator_cfg),
    )
    result = executor.run(ExecutorInput(
        task_input=task_input,
        plan=plan,
        wiki_context=wiki_context,
        prephase=pre,
        harness_url=harness_url,
        task_type=task_type,
        model=model,
        model_cfg=cfg,
        evaluator_model=evaluator_model,
        evaluator_cfg=evaluator_cfg,
    ))
    stats = {
        "outcome": result.outcome,
        "step_facts": result.step_facts,
        "graph_injected_node_ids": result.injected_node_ids,
        "eval_rejection_count": result.rejection_count,
        **result.token_stats,
    }
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = bool(plan.addendum)
    stats["builder_in_tok"] = plan.in_tokens
    stats["builder_out_tok"] = plan.out_tokens
    stats["builder_addendum"] = plan.addendum
    stats["graph_injected_node_ids"] = wiki_context.injected_node_ids
    stats["graph_context"] = wiki_context.graph_section
    # contract tokens are included in plan.in_tokens/out_tokens (PlannerAgent sums both)
    stats["contract_rounds_taken"] = getattr(plan.contract, "rounds_taken", 0) if plan.contract else 0
    stats["contract_is_default"] = getattr(plan.contract, "is_default", True) if plan.contract else True
    stats["contract_in_tok"] = 0
    stats["contract_out_tok"] = 0
    return stats


def write_wiki_fragment(
    task_text: str,
    task_type: str,
    stats: dict,
    task_id: str,
    score: float,
) -> None:
    """Write wiki fragments gated by benchmark score. Fail-open."""
    outcome = stats.get("outcome", "")
    try:
        task_id = task_id or task_text[:20].replace(" ", "_")
        fragments = format_fragment(
            outcome=outcome,
            task_type=task_type,
            task_id=task_id,
            task_text=task_text,
            step_facts=stats.get("step_facts", []),
            done_ops=stats.get("done_ops", []),
            stall_hints=stats.get("stall_hints", []),
            eval_last_call=stats.get("eval_last_call"),
            score=score,
        )
        for content, category in fragments:
            if content and category:
                write_fragment(task_id, category, content)
    except Exception as e:
        print(f"[wiki] fragment write failed: {e}")
