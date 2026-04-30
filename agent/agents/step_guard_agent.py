"""StepGuardAgent validates tool invocations against contract plans.

This agent checks whether each step (tool invocation) aligns with the contract
plan negotiated by PlannerAgent. It detects unexpected operations like:
- Deletes not mentioned in the plan
- Writes to unexpected directories at step >= 3
"""

from __future__ import annotations

from agent.contract_models import Contract
from agent.contract_monitor import check_step
from agent.contracts import StepGuardRequest, StepValidation


class StepGuardAgent:
    """Validates tool invocations against contract constraints."""

    def check(self, request: StepGuardRequest) -> StepValidation:
        """Validate a tool invocation against the contract plan.

        Args:
            request: StepGuardRequest with step_index, tool_name, tool_args, and contract.

        Returns:
            StepValidation with valid=True if no deviation, or valid=False with
            deviation details if the operation violates the contract plan.
        """
        # Reconstruct done_operations from tool_args for the monitor
        path = request.tool_args.get("path", request.tool_args.get("from_name", ""))
        if request.tool_name == "Req_Delete":
            done_ops = [f"DELETED: {path}"]
        elif request.tool_name in ("Req_Write", "Req_MkDir"):
            done_ops = [f"WRITTEN: {path}"]
        else:
            done_ops = []

        warning = check_step(request.contract, done_ops, step_num=request.step_index)
        if warning:
            return StepValidation(
                valid=False,
                deviation=warning,
                suggestion="Verify this operation matches your contract plan.",
            )
        return StepValidation(valid=True)

    def check_optional(
        self,
        step_index: int,
        tool_name: str,
        tool_args: dict,
        done_operations: list[str],
        contract: Contract | None,
    ) -> StepValidation:
        """Validate a tool invocation against an optional contract.

        If contract is None, always returns valid=True (no constraint).

        Args:
            step_index: The current step number in execution.
            tool_name: Name of the tool being invoked.
            tool_args: Arguments passed to the tool.
            done_operations: Pre-formatted list of operation strings (e.g., ["WRITTEN: /path"]).
            contract: Contract to validate against, or None.

        Returns:
            StepValidation with valid=True if no contract or no deviation,
            or valid=False with deviation details if constraint is violated.
        """
        if contract is None:
            return StepValidation(valid=True)

        warning = check_step(contract, done_operations, step_num=step_index)
        if warning:
            return StepValidation(valid=False, deviation=warning)
        return StepValidation(valid=True)
