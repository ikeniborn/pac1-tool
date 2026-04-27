# agent/contract_models.py
from __future__ import annotations
from pydantic import BaseModel


class ExecutorProposal(BaseModel):
    plan_steps: list[str]
    expected_outcome: str
    required_tools: list[str]
    open_questions: list[str]
    agreed: bool


class EvaluatorResponse(BaseModel):
    success_criteria: list[str]
    failure_conditions: list[str]
    required_evidence: list[str]
    objections: list[str]
    counter_proposal: str | None = None
    agreed: bool


class Contract(BaseModel):
    plan_steps: list[str]
    success_criteria: list[str]
    required_evidence: list[str]
    failure_conditions: list[str]
    is_default: bool
    rounds_taken: int
