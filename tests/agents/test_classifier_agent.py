"""Tests for ClassifierAgent."""
import json
from pathlib import Path

import pytest


def _make_router():
    """Build a minimal ModelRouter using data/task_types.json."""
    from agent.classifier import ModelRouter

    # Load models.json or construct a minimal config
    task_types_path = Path("data/task_types.json")
    if task_types_path.exists():
        # If models.json exists (post-refactor), use it
        models_path = Path("data/models.json")
        if models_path.exists():
            configs = json.loads(models_path.read_text())
        else:
            # Fallback: minimal config for testing
            configs = {"claude-3-5-sonnet": {}}
    else:
        # Minimal config for testing
        configs = {"claude-3-5-sonnet": {}}

    default = next(iter(configs))
    return ModelRouter(
        default=default,
        classifier=default,
        configs=configs,
    )


def test_returns_classification_result_type():
    """Test that run() returns a ClassificationResult with expected fields."""
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import ClassificationResult, TaskInput

    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="Send an email to alice@example.com about the meeting",
        harness_url="http://localhost:50051",
        trial_id="t01",
    )
    result = agent.run(task)

    assert isinstance(result, ClassificationResult)
    assert isinstance(result.task_type, str)
    assert result.task_type in ("email", "default")
    assert result.model
    assert isinstance(result.model_cfg, dict)
    assert isinstance(result.confidence, (int, float))


def test_preject_task_classified():
    """Test that empty task_text is classified as a valid type."""
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import TaskInput

    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="",
        harness_url="http://localhost:50051",
        trial_id="t01",
    )
    result = agent.run(task)

    assert isinstance(result.task_type, str)
    assert len(result.task_type) > 0


def test_classification_without_prephase():
    """Test classification using regex fast-path (no prephase)."""
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import TaskInput

    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="Please send an email",
        harness_url="http://localhost:50051",
        trial_id="t02",
    )
    result = agent.run(task, prephase=None)

    # Without prephase, should have lower confidence
    assert result.confidence == 0.8


def test_classification_with_prephase():
    """Test classification with prephase (higher confidence path)."""
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import TaskInput
    from agent.prephase import PrephaseResult

    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="Please send an email",
        harness_url="http://localhost:50051",
        trial_id="t03",
    )

    # Create minimal PrephaseResult for testing
    prephase = PrephaseResult(
        log=[],
        preserve_prefix=[],
        agents_md_content="",
    )
    result = agent.run(task, prephase=prephase)

    # With prephase, should have higher confidence
    assert result.confidence == 0.95
    assert isinstance(result.task_type, str)
