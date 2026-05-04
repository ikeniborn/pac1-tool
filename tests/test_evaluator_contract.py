# tests/test_evaluator_contract.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.contract_models import Contract

_ROOT = Path(__file__).parents[1]


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


def test_contract_required_evidence_descriptive_string_matches_ref_path():
    """FIX-423: evidence like 'Final listing of /path/ showing empty' must
    match grounding_ref '/path/' — path is substring of description."""
    from agent.evaluator import evaluate_completion

    contract = Contract(
        plan_steps=["list /02_distill/cards/", "delete files"],
        success_criteria=["cards deleted"],
        required_evidence=[
            "Final listing of /02_distill/cards/ showing empty",
            "Listing of /02_distill/threads/ showing empty",
        ],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
    )
    report = MagicMock()
    report.outcome = "OUTCOME_OK"
    report.message = "done"
    report.grounding_refs = ["/02_distill/cards/", "/02_distill/threads/"]
    report.done_operations = ["DELETED: /02_distill/cards/card1.md"]
    report.completed_steps_laconic = ["listed /02_distill/cards/", "deleted files"]

    with patch("agent.evaluator.dspy") as mock_dspy, \
         patch("agent.evaluator._load_reference_patterns", return_value="(none)"), \
         patch("agent.evaluator._load_graph_insights", return_value="(none)"):
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

        verdict = evaluate_completion(
            task_text="Remove all captured cards and threads",
            task_type="default",
            report=report,
            done_ops=["DELETED: /02_distill/cards/card1.md"],
            digest_str="",
            model="test-model",
            cfg={},
            contract=contract,
        )

    assert verdict.approved is True, f"Contract gate blocked: {verdict.issues}"


def test_contract_required_evidence_rejects_when_path_not_in_refs():
    """FIX-423: evidence path not referenced by agent → still rejected."""
    from agent.evaluator import evaluate_completion

    contract = Contract(
        plan_steps=["read account"],
        success_criteria=["account read"],
        required_evidence=[
            "Read of /accounts/acct_001.json showing primary_contact_id",
        ],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
    )
    report = MagicMock()
    report.outcome = "OUTCOME_OK"
    report.message = "done"
    report.grounding_refs = ["/contacts/cont_001.json"]
    report.done_operations = []
    report.completed_steps_laconic = ["read contact"]

    with patch("agent.evaluator.dspy"), \
         patch("agent.evaluator._load_reference_patterns", return_value="(none)"), \
         patch("agent.evaluator._load_graph_insights", return_value="(none)"):
        verdict = evaluate_completion(
            task_text="lookup account for contact",
            task_type="lookup",
            report=report,
            done_ops=[],
            digest_str="",
            model="test-model",
            cfg={},
            contract=contract,
        )

    assert verdict.approved is False
    assert "/accounts/acct_001.json" in " ".join(verdict.issues)


def test_rejection_message_is_actionable():
    """FIX-432: Rejection message must not say 'Contract required_evidence';
    must guide the agent to add paths to grounding_refs."""
    source = (_ROOT / "agent/evaluator.py").read_text()
    assert "Contract required_evidence" not in source
    assert "grounding_refs" in source
    # Must contain an actionable phrase telling the agent what to do
    assert (
        "add these paths to grounding_refs" in source
        or "Before re-submitting, add" in source
    )


def test_evaluator_contract_md_bare_paths_instruction():
    """FIX-432: All evaluator_contract.md files must instruct that
    required_evidence values must be bare vault paths."""
    prompts_dir = _ROOT / "data/prompts"
    contract_files = list(prompts_dir.glob("*/evaluator_contract.md"))
    assert contract_files, "No evaluator_contract.md files found"

    missing = []
    for f in sorted(contract_files):
        content = f.read_text()
        if "bare vault path" not in content:
            missing.append(str(f))

    assert not missing, (
        f"These evaluator_contract.md files lack bare-paths instruction:\n"
        + "\n".join(missing)
    )
