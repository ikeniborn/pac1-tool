"""Tests for FIX-409: token-aware compaction and digest deduplication."""


def test_estimate_tokens_empty():
    from agent.log_compaction import _estimate_tokens
    assert _estimate_tokens([]) == 0


def test_estimate_tokens_basic():
    from agent.log_compaction import _estimate_tokens
    # 300 chars / 3 = 100 tokens
    log = [{"role": "user", "content": "a" * 300}]
    assert _estimate_tokens(log) == 100


def test_estimate_tokens_multi_message():
    from agent.log_compaction import _estimate_tokens
    log = [
        {"role": "user", "content": "a" * 150},
        {"role": "assistant", "content": "b" * 150},
    ]
    assert _estimate_tokens(log) == 100


def test_build_digest_read_dedup_keeps_latest():
    from agent.log_compaction import build_digest, _StepFact
    facts = [
        _StepFact("read", "/contacts/alice.md", "first read content"),
        _StepFact("read", "/contacts/alice.md", "second read content"),
    ]
    digest = build_digest(facts)
    assert digest.count("/contacts/alice.md") == 1
    assert "second read content" not in digest
    assert "first read content" not in digest


def test_build_digest_read_shows_metadata():
    from agent.log_compaction import build_digest, _StepFact
    content = "x" * 500
    facts = [_StepFact("read", "/inbox/t1.md", content)]
    digest = build_digest(facts)
    assert "/inbox/t1.md" in digest
    assert "(read, 500 chars)" in digest
    assert content not in digest


def test_build_digest_write_preserved_in_full():
    from agent.log_compaction import build_digest, _StepFact
    facts = [_StepFact("write", "/outbox/t1.md", "WRITTEN: /outbox/t1.md")]
    digest = build_digest(facts)
    assert "WRITTEN: /outbox/t1.md" in digest


def test_build_digest_read_different_paths_both_present():
    from agent.log_compaction import build_digest, _StepFact
    facts = [
        _StepFact("read", "/contacts/alice.md", "alice content"),
        _StepFact("read", "/contacts/bob.md", "bob content"),
    ]
    digest = build_digest(facts)
    assert "/contacts/alice.md" in digest
    assert "/contacts/bob.md" in digest


def _make_log(n_pairs: int, msg_size: int = 10) -> list:
    """Build a log with n assistant+user message pairs of given size."""
    msgs = []
    for _ in range(n_pairs):
        msgs.append({"role": "assistant", "content": "a" * msg_size})
        msgs.append({"role": "user", "content": "b" * msg_size})
    return msgs


def test_compact_log_no_trigger_below_threshold():
    """Below 70% fill → log returned unchanged."""
    from agent.log_compaction import _compact_log
    # 20 pairs * 2 msgs * 75 chars = 3000 chars → ~1000 tokens = 10% of 10000 → no compaction
    log = _make_log(n_pairs=20, msg_size=75)
    result = _compact_log(log, token_limit=10_000, compact_threshold_pct=0.70)
    assert result is log  # same object, not compacted


def test_compact_log_triggers_at_threshold():
    """At or above 70% fill → compaction happens."""
    from agent.log_compaction import _compact_log
    # 20 pairs * 2 * 120 = 4800 chars → 1600 tokens >> 70% of 1000
    log = _make_log(n_pairs=20, msg_size=120)
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    assert result is not log
    assert len(result) < len(log)


def test_compact_log_soft_fill_keeps_6_pairs():
    """70–85% fill → 6 pairs (12 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # 14 pairs * 2 * 82 = 2296 chars → ~765 tokens = 76.5% of 1000
    log = _make_log(n_pairs=14, msg_size=82)
    fill = _estimate_tokens(log) / 1_000
    assert 0.70 <= fill <= 0.85, f"fill={fill:.2f} not in 70-85% range"
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    # 1 summary msg + 12 tail msgs (6 pairs)
    assert len(result) == 13


def test_compact_log_medium_fill_keeps_4_pairs():
    """85–95% fill → 4 pairs (8 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # 17 pairs * 2 * 80 = 2720 chars → ~906 tokens = 90.6% of 1000
    log = _make_log(n_pairs=17, msg_size=80)
    fill = _estimate_tokens(log) / 1_000
    assert 0.85 <= fill <= 0.95, f"fill={fill:.2f} not in 85-95% range"
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    # 1 summary + 8 tail (4 pairs)
    assert len(result) == 9


def test_compact_log_aggressive_fill_keeps_3_pairs():
    """95%+ fill → 3 pairs (6 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # 18 pairs * 2 * 83 = 2988 chars → ~996 tokens = 99.6% of 1000
    log = _make_log(n_pairs=18, msg_size=83)
    fill = _estimate_tokens(log) / 1_000
    assert fill >= 0.95, f"fill={fill:.2f} not >= 0.95"
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    # 1 summary + 6 tail (3 pairs)
    assert len(result) == 7


def test_compact_log_preserves_prefix():
    """preserve_prefix messages are never compacted."""
    from agent.log_compaction import _compact_log
    prefix = [{"role": "system", "content": "system prompt"}]
    tail = _make_log(n_pairs=20, msg_size=200)
    log = prefix + tail
    result = _compact_log(log, preserve_prefix=prefix, token_limit=100, compact_threshold_pct=0.0)
    assert result[0] == prefix[0]


def test_compact_log_confirmed_ops_in_summary():
    """WRITTEN:/DELETED: lines from old messages appear in summary."""
    from agent.log_compaction import _compact_log
    old_msgs = [
        {"role": "user", "content": "WRITTEN: /outbox/t1.md"},
        {"role": "assistant", "content": "a" * 100},
    ] * 10
    tail_msgs = _make_log(n_pairs=3, msg_size=10)
    log = old_msgs + tail_msgs
    result = _compact_log(log, token_limit=100, compact_threshold_pct=0.0)
    summary_content = result[0]["content"]
    assert "WRITTEN: /outbox/t1.md" in summary_content
    assert "do NOT redo" in summary_content
