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
