# agent/contract_monitor.py
"""Rule-based contract compliance monitor for the agent loop.

check_step() fires after each mutation (WRITTEN/DELETED) in _run_step().
Returns a warning string if the operation is unexpected per the contract,
or None if everything looks fine.

No LLM calls — purely structural path matching against contract.plan_steps.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from .contract_models import Contract


def check_step(
    contract: Contract,
    done_operations: list[str],
    step_num: int,
) -> str | None:
    """Check the most recent operation against the contract plan.

    Returns a warning string if unexpected, None otherwise.
    Only the last entry in done_operations is checked (the current step's op).
    """
    if not done_operations:
        return None

    last_op = done_operations[-1]
    plan_text = " ".join(contract.plan_steps).lower()

    if last_op.startswith("DELETED:"):
        path = last_op[len("DELETED:"):].strip()
        parent = str(PurePosixPath(path).parent).strip("/")
        name = PurePosixPath(path).name
        if (path.lower() not in plan_text
                and parent.lower() not in plan_text
                and name.lower() not in plan_text):
            return (
                f"[CONTRACT MONITOR] Unexpected delete: '{path}' not mentioned in contract plan. "
                "Verify this deletion is required before proceeding."
            )

    if step_num >= 3 and last_op.startswith("WRITTEN:"):
        path = last_op[len("WRITTEN:"):].strip()
        parent = str(PurePosixPath(path).parent).strip("/")
        if path.lower() not in plan_text and parent.lower() not in plan_text:
            return (
                f"[CONTRACT MONITOR] Unexpected write to '{path}': "
                f"parent directory '{parent}' not mentioned in contract plan. "
                "Verify this is the correct target."
            )

    return None
