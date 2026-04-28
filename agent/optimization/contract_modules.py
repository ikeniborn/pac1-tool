"""DSPy Signatures for contract negotiation optimization."""
from __future__ import annotations

import dspy


class ExecutorPropose(dspy.Signature):
    """Plan execution steps for a personal knowledge vault task.
    Propose concrete tool calls and paths. Be specific."""

    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
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
