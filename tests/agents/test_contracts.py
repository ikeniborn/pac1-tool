import pytest


def test_imports():
    from agent.contracts import (
        TaskInput, ClassificationResult,
        WikiReadRequest, WikiContext,
        PlannerInput, ExecutionPlan,
        SecurityRequest, SecurityCheck,
        StepGuardRequest, StepValidation,
        StallRequest, StallResult,
        CompactionRequest, CompactedLog,
        CompletionRequest, VerificationResult,
        ExecutorInput, ExecutionResult,
        WikiFeedbackRequest,
    )


def test_task_input_fields():
    from agent.contracts import TaskInput
    t = TaskInput(task_text="do X", harness_url="http://localhost", trial_id="t01")
    assert t.task_text == "do X"
    assert t.trial_id == "t01"


def test_security_check_passed():
    from agent.contracts import SecurityCheck
    c = SecurityCheck(passed=True)
    assert c.passed is True
    assert c.violation_type is None


def test_security_check_violation():
    from agent.contracts import SecurityCheck
    c = SecurityCheck(passed=False, violation_type="write_scope", detail="blocked /docs/")
    assert c.passed is False
    assert c.violation_type == "write_scope"


def test_execution_result_status_literal():
    from agent.contracts import ExecutionResult
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ExecutionResult(status="unknown", outcome="x", token_stats={},
                        step_facts=[], injected_node_ids=[], rejection_count=0)
