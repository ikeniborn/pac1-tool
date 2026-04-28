"""Tests for FIX-410: dead-end blocks in error fragments and injection at startup."""
from unittest.mock import patch


def _make_step_facts(with_error=False):
    from agent.log_compaction import _StepFact
    facts = [
        _StepFact("search", "/contacts", "search done"),
        _StepFact("read", "/contacts/alice.md", "alice content"),
    ]
    if with_error:
        facts.append(_StepFact("write", "/outbox/t1.md", "WRITTEN:", error="ERROR: file not found"))
    return facts


def test_format_fragment_failure_adds_dead_end_block():
    """score=0.5 → error fragment contains ## Dead end: block."""
    from agent.wiki import format_fragment
    step_facts = _make_step_facts(with_error=True)
    results = format_fragment(
        outcome="OUTCOME_ERR_STALL",
        task_type="email",
        task_id="t42",
        task_text="send email to alice",
        step_facts=step_facts,
        done_ops=[],
        stall_hints=[],
        eval_last_call=None,
        score=0.5,
    )
    assert len(results) == 1
    content, category = results[0]
    assert category == "errors/email"
    assert "## Dead end: t42" in content
    assert "Outcome: OUTCOME_ERR_STALL" in content
    assert "What failed:" in content


def test_format_fragment_success_no_dead_end_block():
    """score=1.0 → fragment has NO dead end block."""
    from agent.wiki import format_fragment
    step_facts = _make_step_facts()
    results = format_fragment(
        outcome="OUTCOME_OK",
        task_type="email",
        task_id="t43",
        task_text="send email",
        step_facts=step_facts,
        done_ops=["WRITTEN: /outbox/t43.md"],
        stall_hints=[],
        eval_last_call=None,
        score=1.0,
    )
    content = results[0][0]
    assert "## Dead end:" not in content


def test_load_dead_ends_empty_dir(tmp_path):
    """No error fragments → returns empty string."""
    from agent import wiki
    with patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"):
        result = wiki._load_dead_ends("email")
    assert result == ""


def test_load_dead_ends_basic(tmp_path):
    """One fragment with dead-end block → KNOWN DEAD ENDS section returned."""
    from agent import wiki
    frag_dir = tmp_path / "fragments" / "errors" / "email"
    frag_dir.mkdir(parents=True)
    (frag_dir / "t42_20260101T000000Z.md").write_text(
        "---\ntask_id: t42\noutcome: OUTCOME_ERR_STALL\n---\n\n"
        "## Dead end: t42\nOutcome: OUTCOME_ERR_STALL\nWhat failed:\n- write(/outbox/t42.md): ERROR\n"
    )
    with patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"):
        result = wiki._load_dead_ends("email")
    assert "## KNOWN DEAD ENDS (email)" in result
    assert "t42" in result
    assert "OUTCOME_ERR_STALL" in result


def test_load_dead_ends_max_5_fragments(tmp_path):
    """Only last 5 fragments are used even if more exist."""
    from agent import wiki
    frag_dir = tmp_path / "fragments" / "errors" / "email"
    frag_dir.mkdir(parents=True)
    for i in range(8):
        p = frag_dir / f"t{i:02d}_2026010{i}T000000Z.md"
        p.write_text(
            f"---\ntask_id: t{i:02d}\noutcome: OUTCOME_ERR_STALL\n---\n\n"
            f"## Dead end: t{i:02d}\nOutcome: OUTCOME_ERR_STALL\nWhat failed:\n- (unknown)\n"
        )
    with patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"):
        result = wiki._load_dead_ends("email")
    entry_count = result.count("\n- ")
    assert entry_count <= 5


def test_load_dead_ends_char_limit(tmp_path):
    """Total block is capped at WIKI_NEGATIVES_MAX_CHARS."""
    from agent import wiki
    frag_dir = tmp_path / "fragments" / "errors" / "email"
    frag_dir.mkdir(parents=True)
    for i in range(5):
        (frag_dir / f"t{i}_20260101T000{i}00Z.md").write_text(
            f"---\ntask_id: t{i}\noutcome: OUTCOME_ERR_STALL\n---\n\n"
            f"## Dead end: t{i}\nOutcome: OUTCOME_ERR_STALL\nWhat failed:\n"
            + "- " + "x" * 200 + "\n"
        )
    with patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"):
        with patch.object(wiki, "_WIKI_NEGATIVES_MAX_CHARS", 200):
            result = wiki._load_dead_ends("email")
    assert len(result) <= 200 or result == ""


def test_load_wiki_patterns_includes_negatives(tmp_path):
    """load_wiki_patterns returns success patterns + dead ends combined."""
    from agent import wiki
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "email.md").write_text("## Success pattern\nStep 1: do thing\n")
    frag_dir = tmp_path / "fragments" / "errors" / "email"
    frag_dir.mkdir(parents=True)
    (frag_dir / "t99_20260101T000000Z.md").write_text(
        "---\ntask_id: t99\noutcome: OUTCOME_ERR_STALL\n---\n\n"
        "## Dead end: t99\nOutcome: OUTCOME_ERR_STALL\nWhat failed:\n- write failed\n"
    )
    with patch.object(wiki, "_PAGES_DIR", pages_dir), \
         patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"), \
         patch.object(wiki, "_WIKI_NEGATIVES_ENABLED", True):
        result = wiki.load_wiki_patterns("email", include_negatives=True)
    assert "## Wiki: email Patterns" in result
    assert "## KNOWN DEAD ENDS (email)" in result
    assert "t99" in result
