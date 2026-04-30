from agent.contracts import (
    ClassificationResult, ExecutionPlan, PlannerInput, TaskInput, WikiContext
)
from agent.prephase import PrephaseResult


def _make_planner_input(task_type="email"):
    pre = PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[{"role": "system", "content": "sys"}],
    )
    return PlannerInput(
        task_input=TaskInput(
            task_text="Send email to alice@example.com about meeting",
            harness_url="http://localhost",
            trial_id="t01",
        ),
        classification=ClassificationResult(
            task_type=task_type,
            model="claude-haiku-4-5",
            model_cfg={},
            confidence=1.0,
        ),
        wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
        prephase=pre,
    )


def _load_model_configs():
    import json
    from pathlib import Path
    for candidate in (Path("data/models.json"), Path("models.json")):
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {"claude-3-5-sonnet": {}}


def test_returns_execution_plan_type():
    from agent.agents.planner_agent import PlannerAgent
    configs = _load_model_configs()
    default = next(iter(configs))

    agent = PlannerAgent(
        model=default,
        cfg=configs[default],
        prompt_builder_enabled=False,
        contract_enabled=False,
    )
    result = agent.run(_make_planner_input())
    assert isinstance(result, ExecutionPlan)
    assert result.base_prompt
    assert result.route in ("EXECUTE", "DENY_SECURITY", "CLARIFY", "UNSUPPORTED")
    assert result.contract is None  # contract_enabled=False


def test_plan_contains_base_prompt():
    from agent.agents.planner_agent import PlannerAgent
    configs = _load_model_configs()
    default = next(iter(configs))
    agent = PlannerAgent(
        model=default,
        cfg=configs[default],
        prompt_builder_enabled=False,
        contract_enabled=False,
    )
    result = agent.run(_make_planner_input(task_type="email"))
    assert "email" in result.base_prompt.lower() or len(result.base_prompt) > 100
