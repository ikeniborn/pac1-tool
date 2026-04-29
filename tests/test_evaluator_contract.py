# tests/test_evaluator_contract.py
from unittest.mock import patch, MagicMock
from agent.contract_models import Contract


def _make_contract(failure_conditions=None):
    return Contract(
        plan_steps=["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=failure_conditions or ["unauthorized write detected"],
        is_default=False,
        rounds_taken=1,
    )


def _make_report(outcome="OUTCOME_OK", grounding_refs=None):
    report = MagicMock()
    report.outcome = outcome
    report.message = "done"
    report.grounding_refs = grounding_refs or ["/outbox/1.json"]
    report.done_operations = []
    report.completed_steps_laconic = []
    return report


@patch("agent.evaluator.dspy")
def test_contract_context_passed_to_predictor(mock_dspy):
    """failure_conditions from contract appear in the predictor call."""
    mock_predictor = MagicMock()
    mock_dspy.ChainOfThought.return_value = mock_predictor
    mock_dspy.context.return_value.__enter__ = lambda s: s
    mock_dspy.context.return_value.__exit__ = MagicMock(return_value=False)
    mock_dspy.JSONAdapter.return_value = MagicMock()
    result = MagicMock()
    result.approved_str = "yes"
    result.issues_str = ""
    result.correction_hint = ""
    mock_predictor.return_value = result

    from agent.evaluator import evaluate_completion
    contract = _make_contract(failure_conditions=["do not write to /secrets/"])
    evaluate_completion(
        task_text="write email",
        task_type="email",
        report=_make_report(),
        done_ops=["/outbox/1.json"],
        digest_str="",
        model="test-model",
        cfg={},
        contract=contract,
    )
    # The predictor must have been called with contract_context containing the failure condition
    call_kwargs = mock_predictor.call_args[1]
    assert "contract_context" in call_kwargs
    assert "do not write to /secrets/" in call_kwargs["contract_context"]
