# tests/test_pipeline_models.py
from pydantic import ValidationError
import pytest
from agent.models import (
    SddOutput, PlanStep, LearnOutput, AnswerOutput, PipelineEvalOutput,
    ResolveCandidate, ResolveOutput,
)


def test_sql_plan_output_valid():
    obj = SddOutput(
        reasoning="products table has type column",
        spec="return count of Lawn Mowers",
        plan=[PlanStep(type="sql", description="count", query="SELECT COUNT(*) FROM products WHERE type='Lawn Mower'")],
    )
    assert obj.reasoning == "products table has type column"
    assert len(obj.plan) == 1


def test_sql_plan_output_requires_reasoning():
    with pytest.raises(ValidationError):
        SddOutput(spec="s", plan=[])


def test_sql_plan_output_requires_queries():
    with pytest.raises(ValidationError):
        SddOutput(reasoning="ok")


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
        score=8.5,
        comment="solid",
        prompt_optimization=["add example SQL to sql_plan.md"],
        rule_optimization=["add rule for brand filtering"],
    )
    assert 0.0 <= obj.score <= 10.0


def test_sql_plan_output_agents_md_refs_defaults_empty():
    obj = SddOutput(reasoning="r", spec="s", plan=[])
    assert obj.agents_md_refs == []


def test_sql_plan_output_agents_md_refs_set():
    obj = SddOutput(reasoning="r", spec="s", plan=[], agents_md_refs=["brand_aliases"])
    assert obj.agents_md_refs == ["brand_aliases"]


def test_learn_output_agents_md_anchor_defaults_none():
    obj = LearnOutput(reasoning="r", conclusion="c", rule_content="Always use X")
    assert obj.agents_md_anchor is None


def test_learn_output_agents_md_anchor_set():
    obj = LearnOutput(reasoning="r", conclusion="c", rule_content="r", agents_md_anchor="brand_aliases > Heco")
    assert obj.agents_md_anchor == "brand_aliases > Heco"


def test_pipeline_eval_output_new_metrics_default():
    obj = PipelineEvalOutput(
        reasoning="r", score=8, comment="c",
        prompt_optimization=[], rule_optimization=[],
    )
    assert obj.agents_md_coverage == 0.0
    assert obj.schema_grounding == 0.0


def test_pipeline_eval_output_new_metrics_set():
    obj = PipelineEvalOutput(
        reasoning="r", score=8, comment="c",
        prompt_optimization=[], rule_optimization=[],
        agents_md_coverage=0.75, schema_grounding=1.0,
    )
    assert obj.agents_md_coverage == 0.75
    assert obj.schema_grounding == 1.0


def test_resolve_candidate_minimal():
    c = ResolveCandidate(
        term="Heco",
        field="brand",
        discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%Heco%' LIMIT 10",
    )
    assert c.confirmed_value is None


def test_resolve_candidate_with_value():
    c = ResolveCandidate(
        term="heco", field="brand",
        discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10",
        confirmed_value="Heco",
    )
    assert c.confirmed_value == "Heco"


def test_resolve_output_validate():
    obj = ResolveOutput(
        reasoning="found brand",
        candidates=[
            ResolveCandidate(
                term="heco", field="brand",
                discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10",
            )
        ],
    )
    assert len(obj.candidates) == 1
