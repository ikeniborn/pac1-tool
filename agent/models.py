from typing import Literal

from pydantic import BaseModel


class SqlPlanOutput(BaseModel):
    reasoning: str
    queries: list[str]


class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str


class AnswerOutput(BaseModel):
    reasoning: str
    message: str
    outcome: Literal[
        "OUTCOME_OK",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_UNSUPPORTED",
        "OUTCOME_DENIED_SECURITY",
    ]
    grounding_refs: list[str]
    completed_steps: list[str]


class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    prompt_optimization: list[str]
    rule_optimization: list[str]
