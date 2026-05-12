# tests/test_pipeline_models.py
from pydantic import ValidationError
import pytest
from agent.models import SqlPlanOutput, LearnOutput, AnswerOutput, PipelineEvalOutput


def test_sql_plan_output_valid():
    obj = SqlPlanOutput(
        reasoning="products table has type column",
        queries=["SELECT COUNT(*) FROM products WHERE type='Lawn Mower'"],
    )
    assert obj.reasoning == "products table has type column"
    assert len(obj.queries) == 1


def test_sql_plan_output_requires_reasoning():
    with pytest.raises(ValidationError):
        SqlPlanOutput(queries=["SELECT 1"])


def test_sql_plan_output_requires_queries():
    with pytest.raises(ValidationError):
        SqlPlanOutput(reasoning="ok")


def test_learn_output_valid():
    obj = LearnOutput(
        reasoning="column name mismatch",
        conclusion="Use 'model' not 'series' for product line",
        rule_content="Never filter on 'series' column for product line names — use 'model'.",
    )
    assert obj.conclusion.startswith("Use")


def test_answer_output_valid():
    obj = AnswerOutput(
        reasoning="SQL returned 3 rows",
        message="<YES> Product found",
        outcome="OUTCOME_OK",
        grounding_refs=["/proc/catalog/ABC-123.json"],
        completed_steps=["ran SQL", "found product"],
    )
    assert obj.outcome == "OUTCOME_OK"


def test_answer_output_invalid_outcome():
    with pytest.raises(ValidationError):
        AnswerOutput(
            reasoning="x",
            message="x",
            outcome="OUTCOME_UNKNOWN",
            grounding_refs=[],
            completed_steps=[],
        )


def test_pipeline_eval_output_valid():
    obj = PipelineEvalOutput(
        reasoning="trace looks good",
        score=0.85,
        comment="solid",
        prompt_optimization=["add example SQL to sql_plan.md"],
        rule_optimization=["add rule for brand filtering"],
    )
    assert 0.0 <= obj.score <= 1.0
