# agent/contract_models.py
from __future__ import annotations
from pydantic import BaseModel, Field


class ExecutorProposal(BaseModel):
    plan_steps: list[str]
    expected_outcome: str
    required_tools: list[str]
    planned_mutations: list[str] = Field(default_factory=list)  # FIX-415: explicit write/delete paths
    open_questions: list[str]
    agreed: bool


class EvaluatorResponse(BaseModel):
    success_criteria: list[str]
    failure_conditions: list[str]
    required_evidence: list[str]
    objections: list[str]                                          # non-blocking: notes, caveats, confirmations
    blocking_objections: list[str] = Field(default_factory=list)  # FIX-418: true plan-blockers only
    counter_proposal: str | None = None
    agreed: bool


class Contract(BaseModel):
    plan_steps: list[str]
    success_criteria: list[str]
    required_evidence: list[str]
    failure_conditions: list[str]
    mutation_scope: list[str] = Field(default_factory=list)       # FIX-415: validated allowed paths
    forbidden_mutations: list[str] = Field(default_factory=list)  # FIX-415: blocked paths from constraints
    evaluator_only: bool = False                                   # FIX-415: True when evaluator-only consensus
    planner_strategy: str = ""                                     # FIX-426: Round 0 PlannerStrategize output
    is_default: bool
    rounds_taken: int


class ContractRound(BaseModel):
    round_num: int
    executor_proposal: dict
    evaluator_response: dict
