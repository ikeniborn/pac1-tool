import pytest

from agent.models import ReportTaskCompletion
from agent.contracts import WikiContext


def _make_report(outcome="OUTCOME_OK", message="Done", grounding_refs=None):
    return ReportTaskCompletion(
        tool="report_completion",
        completed_steps_laconic=["wrote /outbox/1.json"],
        message=message,
        grounding_refs=grounding_refs or ["/outbox/1.json"],
        outcome=outcome,
    )


def _make_wiki_ctx():
    return WikiContext(patterns_text="", graph_section="", injected_node_ids=[])


def test_returns_verification_result_type():
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest, VerificationResult

    agent = VerifierAgent(enabled=False)  # disabled → auto-approve
    req = CompletionRequest(
        report=_make_report(),
        task_type="email",
        task_text="send email",
        wiki_context=_make_wiki_ctx(),
        contract=None,
    )
    result = agent.verify(req)
    assert isinstance(result, VerificationResult)
    assert result.approved is True


def test_disabled_evaluator_auto_approves():
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest

    agent = VerifierAgent(enabled=False)
    req = CompletionRequest(
        report=_make_report(outcome="OUTCOME_DENIED_SECURITY"),
        task_type="email",
        task_text="x",
        wiki_context=_make_wiki_ctx(),
        contract=None,
    )
    result = agent.verify(req)
    assert result.approved is True


def test_verify_with_model_returns_result():
    """VerifierAgent with a real model must return VerificationResult without raising."""
    import json
    from pathlib import Path

    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest

    # Try both locations for models.json
    models_path = Path("data/models.json")
    if not models_path.exists():
        models_path = Path("models.json")

    if not models_path.exists():
        pytest.skip("models.json not found")

    configs = json.loads(models_path.read_text())
    # Skip metadata keys (those starting with _)
    default = next(k for k in configs if not k.startswith("_"))
    agent = VerifierAgent(
        enabled=True,
        model=default,
        cfg=configs[default],
    )
    req = CompletionRequest(
        report=_make_report(),
        task_type="email",
        task_text="send email to alice",
        wiki_context=_make_wiki_ctx(),
        contract=None,
        done_ops=["WRITTEN: /outbox/1.json"],
        digest_str="State digest:\nDONE:\n  WRITTEN: /outbox/1.json",
        evaluator_model=default,
        evaluator_cfg=configs[default],
    )
    result = agent.verify(req)
    assert isinstance(result.approved, bool)
