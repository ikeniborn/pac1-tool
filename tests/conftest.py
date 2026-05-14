"""Reset module-level caches between tests."""
import pytest
import agent.pipeline


@pytest.fixture(autouse=True)
def reset_pipeline_caches():
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None
    agent.pipeline._TDD_ENABLED = False
    yield
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None
    agent.pipeline._TDD_ENABLED = False
