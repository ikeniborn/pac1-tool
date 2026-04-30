"""SecurityAgent — validation of tool invocations against security gates.

Wraps existing security functions from agent.security and agent.loop
into a contract-based interface for the multi-agent architecture.

Isolation rule: imports only from agent.contracts and agent.security
(plus agent.loop for _INJECTION_RE).
"""
from __future__ import annotations

import types

from agent.contracts import SecurityCheck, SecurityRequest
from agent.security import (
    _check_write_scope,
    _check_write_payload_injection,
    _normalize_for_injection,
)
from agent.loop import _INJECTION_RE


class SecurityAgent:
    """Validates tool invocations against security gates."""

    def check_write_scope(self, request: SecurityRequest) -> SecurityCheck:
        """Check if a write operation targets permitted paths.

        Email tasks can only write to /outbox/.
        All tasks are blocked from writing to /docs/ and AGENTS.MD.
        """
        # Build a namespace object that mimics the Pydantic tool model
        action = types.SimpleNamespace(**request.tool_args)
        error = _check_write_scope(action, request.tool_name, request.task_type)
        if error:
            return SecurityCheck(
                passed=False, violation_type="write_scope", detail=error
            )
        return SecurityCheck(passed=True)

    def check_injection(self, text: str) -> SecurityCheck:
        """Check for injection patterns in input text.

        Normalizes text (leet speak, zero-width chars, homoglyphs) before
        matching against injection regex.
        """
        norm = _normalize_for_injection(text)
        if _INJECTION_RE.search(norm):
            return SecurityCheck(
                passed=False,
                violation_type="injection",
                detail="injection pattern detected",
            )
        return SecurityCheck(passed=True)

    def check_write_payload(
        self, content: str, source_path: str | None = None
    ) -> SecurityCheck:
        """Check for embedded command injection in write payload.

        Detects embedded tool notes, conditional imperatives, and
        authority-claiming metadata typical of bridge/override injection.

        Exempts content from trusted policy paths (docs/channels/, etc.).
        """
        if _check_write_payload_injection(content, source_path):
            return SecurityCheck(
                passed=False,
                violation_type="injection",
                detail="write payload injection detected",
            )
        return SecurityCheck(passed=True)
