"""StallAgent — detects and reports stalls in task execution.

Stall detection logic adapted from agent.stall._check_stall() which checks for:
- Repeated tool calls with same arguments (3× → detected)
- Repeated path errors (2× → detected)
- Exploration stalls without writes (6+ steps → detected)
- Escalation hints at 12+ and 18+ steps

Public API:
  StallAgent.check(StallRequest) -> StallResult
"""

from __future__ import annotations

from collections import Counter, deque

from agent.contracts import StallRequest, StallResult
from agent.log_compaction import _StepFact
from agent.stall import _check_stall


class StallAgent:
    """Independent agent for stall detection in task execution."""

    def check(self, request: StallRequest) -> StallResult:
        """Check if execution has stalled and return escalation level.

        Args:
            request: StallRequest with fingerprints, steps_without_write, etc.

        Returns:
            StallResult with detected=True/False, hint string, escalation_level.
        """
        # Convert flat request data to structured inputs for _check_stall
        fp = deque(request.fingerprints, maxlen=10)
        ec: Counter = Counter(request.error_counts)
        facts = [
            _StepFact(
                kind=d.get("kind", ""),
                path=d.get("path", ""),
                summary=d.get("summary", ""),
                error=d.get("error", ""),
            )
            for d in request.step_facts_dicts
        ]

        # Delegate stall detection to _check_stall
        hint = _check_stall(
            fp,
            request.steps_without_write,
            ec,
            facts or None,
            request.contract_plan_steps,
        )

        # If no hint, stall not detected
        if hint is None:
            return StallResult(detected=False)

        # Compute escalation level based on steps_without_write
        escalation = 1
        if request.steps_without_write >= 12:
            escalation = 2
        if request.steps_without_write >= 18:
            escalation = 3

        return StallResult(detected=True, hint=hint, escalation_level=escalation)
