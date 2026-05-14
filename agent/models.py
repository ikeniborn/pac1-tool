from typing import Literal

from pydantic import BaseModel


class SqlPlanOutput(BaseModel):
    reasoning: str
    queries: list[str]
    agents_md_refs: list[str] = []


class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str
    agents_md_anchor: str | None = None


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
    security_optimization: list[str] = []
    agents_md_coverage: float = 0.0
    schema_grounding: float = 0.0


class ResolveCandidate(BaseModel):
    term: str
    field: str
    discovery_query: str
    confirmed_value: str | None = None


class ResolveOutput(BaseModel):
    reasoning: str
    candidates: list[ResolveCandidate]


class TestGenOutput(BaseModel):
    reasoning: str
    sql_tests: str
    answer_tests: str
