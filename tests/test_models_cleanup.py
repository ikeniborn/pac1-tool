import inspect
import importlib
import pytest


def test_plan_step_sql():
    from agent.models import PlanStep
    step = PlanStep(
        type="sql",
        description="count products",
        query="SELECT COUNT(*) FROM products",
    )
    assert step.query == "SELECT COUNT(*) FROM products"
    assert step.operation is None
    assert step.args == []


def test_plan_step_read():
    from agent.models import PlanStep
    step = PlanStep(type="read", description="read file", operation="read", args=["/tmp/f"])
    assert step.query is None
    assert step.args == ["/tmp/f"]


def test_sdd_output_minimal():
    from agent.models import SddOutput, PlanStep
    out = SddOutput(
        reasoning="r",
        spec="return product count",
        plan=[PlanStep(type="sql", description="count", query="SELECT COUNT(*) FROM products")],
    )
    assert out.agents_md_refs == []
    assert len(out.plan) == 1


def test_test_output():
    from agent.models import TestOutput
    out = TestOutput(
        reasoning="r",
        sql_tests="def test_sql(results): pass",
        answer_tests="def test_answer(sql_results, answer): pass",
    )
    assert "test_sql" in out.sql_tests


