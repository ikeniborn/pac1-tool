"""DSPy Signatures for contract negotiation optimization."""
from __future__ import annotations

import dspy


class PlannerStrategize(dspy.Signature):
    """Analyze vault structure and define search strategy before execution."""

    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    vault_tree: str = dspy.InputField(desc="Output of tree -L 2 / showing vault structure")
    agents_md: str = dspy.InputField(desc="AGENTS.MD content describing folder roles")

    search_scope: list[str] = dspy.OutputField(
        desc="Folders to search in priority order"
    )
    interpretation: str = dspy.OutputField(
        desc="One sentence: what the task is asking for"
    )
    critical_paths: list[str] = dspy.OutputField(
        desc="Specific file paths or patterns the agent must visit"
    )
    ambiguities: list[str] = dspy.OutputField(
        desc="Genuine open questions about the task; [] if clear"
    )


class ExecutorPropose(dspy.Signature):
    """Plan execution steps for a personal knowledge vault task.
    Propose concrete tool calls and paths. Be specific."""

    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    planner_strategy: str = dspy.InputField(
        desc="Strategy from PlannerStrategize round 0 (search_scope, interpretation, critical_paths)",
        default="",
    )
    evaluator_feedback: str = dspy.InputField(
        desc="Evaluator's previous response (empty on round 1)", default=""
    )
    plan_steps: list[str] = dspy.OutputField(desc="2-7 concrete steps: tool + path")
    expected_outcome: str = dspy.OutputField(desc="One sentence: what success looks like")
    required_tools: list[str] = dspy.OutputField(
        desc="Tools from [list,read,write,delete,find,search,move,mkdir]"
    )
    open_questions: list[str] = dspy.OutputField(
        desc="Genuine ambiguities; [] if clear"
    )
    agreed: bool = dspy.OutputField(
        desc="True only after evaluator agrees with no objections"
    )


class EvaluatorReview(dspy.Signature):
    """Review an executor's plan and define verifiable success criteria."""

    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    planner_strategy: str = dspy.InputField(
        desc="Strategy from PlannerStrategize round 0; use to verify executor covered required scope",
        default="",
    )
    executor_proposal: str = dspy.InputField(desc="Executor's plan as JSON string")
    success_criteria: list[str] = dspy.OutputField(desc="2-5 verifiable conditions")
    failure_conditions: list[str] = dspy.OutputField(
        desc="Explicit failure scenarios"
    )
    required_evidence: list[str] = dspy.OutputField(
        desc="Vault paths that MUST appear in grounding_refs"
    )
    objections: list[str] = dspy.OutputField(
        desc="Concerns about the plan; [] if acceptable"
    )
    agreed: bool = dspy.OutputField(desc="True when plan satisfies all criteria")
