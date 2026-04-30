"""CompactionAgent for log compaction in multi-agent architecture.

Wraps agent.log_compaction functions to provide a clean contract-based API.
"""

from __future__ import annotations

from agent.contracts import CompactedLog, CompactionRequest
from agent.log_compaction import _StepFact, _compact_log, _estimate_tokens


class CompactionAgent:
    """Agent responsible for compacting message logs while preserving critical context."""

    def compact(self, request: CompactionRequest) -> CompactedLog:
        """Compact a message log to fit within a token budget.

        Args:
            request: CompactionRequest with messages, preserve_prefix, step_facts_dicts,
                    and token_limit.

        Returns:
            CompactedLog with the compacted messages and tokens_saved.
        """
        # Convert step_facts_dicts to _StepFact objects
        facts = [
            _StepFact(
                kind=d.get("kind", ""),
                path=d.get("path", ""),
                summary=d.get("summary", ""),
                error=d.get("error", ""),
            )
            for d in request.step_facts_dicts
        ]

        # Estimate tokens before compaction
        before_tokens = _estimate_tokens(request.messages)

        # Compact the log
        compacted = _compact_log(
            request.messages,
            preserve_prefix=request.preserve_prefix,
            step_facts=facts or None,
            token_limit=request.token_limit,
        )

        # Estimate tokens after compaction
        after_tokens = _estimate_tokens(compacted)
        tokens_saved = max(0, before_tokens - after_tokens)

        return CompactedLog(messages=compacted, tokens_saved=tokens_saved)
