"""Tests for CompactionAgent."""

from agent.agents.compaction_agent import CompactionAgent
from agent.contracts import CompactionRequest, CompactedLog


def _make_messages(n=20):
    """Create a test message log with n messages (including system message)."""
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"msg {i} " + "x" * 100})
    return msgs


def test_returns_compacted_log_type():
    """Test that compact() returns a CompactedLog instance with valid structure."""
    agent = CompactionAgent()
    msgs = _make_messages(20)
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=300,
    )
    result = agent.compact(req)
    assert isinstance(result, CompactedLog)
    assert isinstance(result.messages, list)


def test_compaction_reduces_messages():
    """Test that compact() reduces message count when over token budget."""
    agent = CompactionAgent()
    msgs = _make_messages(30)
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=200,
    )
    result = agent.compact(req)
    assert len(result.messages) < len(msgs)


def test_no_compaction_when_within_budget():
    """Test that messages are not compacted when within token budget."""
    agent = CompactionAgent()
    msgs = [{"role": "user", "content": "hi"}]
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=100_000,
    )
    result = agent.compact(req)
    assert len(result.messages) == len(msgs)
    assert result.tokens_saved == 0
