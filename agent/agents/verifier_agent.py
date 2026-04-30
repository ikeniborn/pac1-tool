"""VerifierAgent — evaluation of task completion before submission.

Wraps the existing evaluate_completion() function from agent.evaluator into a
contract-based interface for the multi-agent architecture.

Isolation rule: imports only from agent.contracts. Lazy import of agent.evaluator
inside the verify() method avoids loading the full DSPy stack unless the verifier
is actually enabled and called.
"""
from __future__ import annotations

import os

from agent.contracts import CompletionRequest, VerificationResult

_EVALUATOR_ENABLED = os.getenv("EVALUATOR_ENABLED", "1") == "1"
_EVAL_SKEPTICISM = os.getenv("EVAL_SKEPTICISM", "mid")
_EVAL_EFFICIENCY = os.getenv("EVAL_EFFICIENCY", "mid")


class VerifierAgent:
    """Independent agent for verification of task completion.

    Uses the evaluator LLM to review whether the reported task completion
    meets quality standards before submission to the harness.

    When disabled (enabled=False), auto-approves all completions (fail-open).
    """

    def __init__(
        self,
        enabled: bool | None = None,
        model: str = "",
        cfg: dict | None = None,
    ) -> None:
        """Initialize the VerifierAgent.

        Args:
            enabled: Whether the evaluator is enabled. Defaults to EVALUATOR_ENABLED env var.
            model: Model name for the evaluator (e.g., "claude-3-5-sonnet").
            cfg: Model configuration dict (provider settings, etc.).
        """
        self._enabled = _EVALUATOR_ENABLED if enabled is None else enabled
        self._model = model
        self._cfg = cfg or {}

    def verify(self, request: CompletionRequest) -> VerificationResult:
        """Verify a task completion report.

        If the verifier is disabled, automatically approves the report.
        Otherwise, calls the evaluator LLM to review the completion.

        Args:
            request: CompletionRequest with task info, report, and evaluator config.

        Returns:
            VerificationResult with approval decision and optional feedback.
        """
        if not self._enabled:
            # Disabled → auto-approve
            return VerificationResult(approved=True, rejection_count=request.rejection_count)

        # Use evaluator model/cfg from request if provided, else use instance defaults
        model = request.evaluator_model or self._model
        cfg = request.evaluator_cfg or self._cfg
        if not model:
            # No model configured → auto-approve
            return VerificationResult(approved=True, rejection_count=request.rejection_count)

        try:
            from agent.evaluator import evaluate_completion

            verdict = evaluate_completion(
                task_text=request.task_text,
                task_type=request.task_type,
                report=request.report,
                done_ops=request.done_ops,
                digest_str=request.digest_str,
                model=model,
                cfg=cfg,
                skepticism=_EVAL_SKEPTICISM,
                efficiency=_EVAL_EFFICIENCY,
                contract=request.contract,
            )
            # Track rejection count: increment if verdict denies, else keep same
            new_count = (
                request.rejection_count + 1
                if not verdict.approved
                else request.rejection_count
            )
            return VerificationResult(
                approved=verdict.approved,
                feedback=verdict.correction_hint if not verdict.approved else None,
                rejection_count=new_count,
            )
        except Exception as exc:
            # Fail-open: on evaluator error, auto-approve
            print(f"[verifier] evaluate_completion failed ({exc}) — auto-approving")
            return VerificationResult(approved=True, rejection_count=request.rejection_count)
