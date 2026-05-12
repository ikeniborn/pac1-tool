import inspect
import sys
import importlib
import pytest


def test_pipeline_models_present():
    """Test that the 4 pipeline models are present in models.py"""
    m = importlib.import_module("agent.models")
    assert hasattr(m, "SqlPlanOutput")
    assert hasattr(m, "LearnOutput")
    assert hasattr(m, "AnswerOutput")
    assert hasattr(m, "PipelineEvalOutput")


def test_vault_models_removed():
    """Test that all vault classes have been removed from models.py"""
    m = importlib.import_module("agent.models")
    vault_names = [
        "TaskRoute", "NextStep", "ReportTaskCompletion",
        "Req_Write", "Req_Delete", "Req_Tree", "Req_Find",
        "Req_Search", "Req_List", "Req_Read", "Req_Stat",
        "Req_Exec", "Req_Context", "EmailOutbox",
    ]
    for name in vault_names:
        assert not hasattr(m, name), f"Vault model still present: {name}"


def test_models_has_exactly_four_classes():
    """Test that models.py contains exactly 4 BaseModel classes"""
    m = importlib.import_module("agent.models")
    from pydantic import BaseModel
    classes = [
        name for name, obj in inspect.getmembers(m, inspect.isclass)
        if issubclass(obj, BaseModel) and obj is not BaseModel
        and obj.__module__ == "agent.models"
    ]
    assert len(classes) == 4, f"Expected 4 pipeline classes, got {len(classes)}: {classes}"
