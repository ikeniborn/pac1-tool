"""DSPy Module for joint optimization of planner → executor → evaluator pipeline."""
from __future__ import annotations

import dspy

from agent.optimization.contract_modules import (
    EvaluatorReview,
    ExecutorPropose,
    PlannerStrategize,
)


class ContractNegotiationModule(dspy.Module):
    """Joint planner → executor → evaluator pipeline for contract negotiation."""

    def __init__(self) -> None:
        super().__init__()
        self.planner = dspy.Predict(PlannerStrategize)
        self.executor = dspy.Predict(ExecutorPropose)
        self.evaluator = dspy.Predict(EvaluatorReview)

    def forward(
        self,
        task_text: str,
        task_type: str,
        vault_tree: str = "",
        agents_md: str = "",
        evaluator_feedback: str = "",
    ):
        strategy = self.planner(
            task_text=task_text,
            task_type=task_type,
            vault_tree=vault_tree,
            agents_md=agents_md,
        )
        strategy_str = (
            f"search_scope={strategy.search_scope} "
            f"interpretation={strategy.interpretation} "
            f"critical_paths={strategy.critical_paths}"
        )
        proposal = self.executor(
            task_text=task_text,
            task_type=task_type,
            planner_strategy=strategy_str,
            evaluator_feedback=evaluator_feedback,
        )
        review = self.evaluator(
            task_text=task_text,
            task_type=task_type,
            planner_strategy=strategy_str,
            executor_proposal=str(proposal),
        )
        return review
