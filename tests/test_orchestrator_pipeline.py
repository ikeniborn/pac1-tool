# tests/test_orchestrator_pipeline.py
import importlib
import pytest
from unittest.mock import MagicMock, patch
from agent.orchestrator import run_agent


def _make_vm_mock():
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products(...)"
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    return vm


def test_lookup_routes_to_pipeline():
    """run_agent calls run_pipeline for all tasks."""
    with patch("agent.orchestrator.EcomRuntimeClientSync", return_value=_make_vm_mock()), \
         patch("agent.orchestrator.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {
            "outcome": "OUTCOME_OK",
            "step_facts": [],
            "done_ops": [],
            "input_tokens": 10,
            "output_tokens": 5,
            "total_elapsed_ms": 100,
        }
        result = run_agent({}, "http://localhost:9001", "How many Lawn Mowers?", "t01")

    mock_pipeline.assert_called_once()
    assert result["outcome"] == "OUTCOME_OK"
    assert result["task_type"] == "lookup"


def test_loop_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agent.loop")
