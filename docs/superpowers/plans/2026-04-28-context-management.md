# Context Management Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two independent context degradation problems: (1) compaction triggers unconditionally every step instead of lazily by token fill, (2) failure knowledge (error fragments) is never fed back to the agent at next run.

**Architecture:** FIX-409 — replace the fixed `max_tool_pairs=5` trigger in `_compact_log` with token-aware lazy compaction driven by `ctx_window` from `models.json`; deduplicate read facts and emit metadata-only entries in digest. FIX-410 — append a `## Dead end:` block to error fragments and inject last-5 dead ends into `load_wiki_patterns`.

**Tech Stack:** Python 3.11, pytest, `agent/log_compaction.py`, `agent/loop.py`, `agent/wiki.py`, `models.json`

---

## Task 1: Add `ctx_window` to models.json

**Files:**
- Modify: `models.json`

Add `ctx_window` to `_fields` documentation and every model entry. No tests needed — pure data change.

- [ ] **Step 1: Add field documentation to `_fields`**

In `models.json`, add after the `"cc_options"` entry in `_fields`:
```json
"ctx_window": "Context window size in tokens (input limit). Used by _compact_log for token-aware compaction threshold."
```

- [ ] **Step 2: Add `ctx_window` to Anthropic models**

Add `"ctx_window": 200000` to each of:
- `anthropic/claude-haiku-4.5`
- `anthropic/claude-sonnet-4.6`
- `anthropic/claude-opus-4.6`
- `anthropic/claude-opus-4.7`

- [ ] **Step 3: Add `ctx_window` to Claude Code models**

Add `"ctx_window": 200000` to each of:
- `claude-code/haiku-4.5`
- `claude-code/sonnet-4.6`
- `claude-code/opus-4.7`

- [ ] **Step 4: Add `ctx_window` to Ollama models**

All Ollama models use default profile (`num_ctx: 16384`). Add `"ctx_window": 16384` to every Ollama model entry.

- [ ] **Step 5: Add `ctx_window` to OpenRouter models**

```json
"qwen/qwen3.5-9b":                    "ctx_window": 131072
"meta-llama/llama-3.3-70b-instruct":  "ctx_window": 131072
```

- [ ] **Step 6: Verify JSON is valid**

```bash
python3 -c "import json; json.load(open('models.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add models.json
git commit -m "feat(models): add ctx_window field to all model entries (FIX-409)"
```

---

## Task 2: Tests for `_estimate_tokens` and updated `build_digest`

**Files:**
- Create: `tests/test_log_compaction.py`

Write failing tests for the two new behaviours in `log_compaction.py`.

- [ ] **Step 1: Create test file with `_estimate_tokens` tests**

```python
# tests/test_log_compaction.py
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
    # (150 + 150) / 3 = 100
    assert _estimate_tokens(log) == 100
```

- [ ] **Step 2: Add tests for read deduplication in `build_digest`**

Append to `tests/test_log_compaction.py`:

```python
def test_build_digest_read_dedup_keeps_latest():
    from agent.log_compaction import build_digest, _StepFact
    facts = [
        _StepFact("read", "/contacts/alice.md", "first read content"),
        _StepFact("read", "/contacts/alice.md", "second read content"),
    ]
    digest = build_digest(facts)
    # Only one entry for this path
    assert digest.count("/contacts/alice.md") == 1
    # Content is NOT in digest (metadata only)
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run python -m pytest tests/test_log_compaction.py -v 2>&1 | head -40
```
Expected: `ImportError` or `AttributeError` on `_estimate_tokens` (function doesn't exist yet).

---

## Task 3: Implement `_estimate_tokens` and update `build_digest`

**Files:**
- Modify: `agent/log_compaction.py`

- [ ] **Step 1: Add `_estimate_tokens` after the module docstring imports**

In `agent/log_compaction.py`, after line 14 (`from dataclasses import ...`), add:

```python
def _estimate_tokens(log: list) -> int:
    """Estimate token count for a message log (3 chars/token, conservative for mixed languages)."""
    return sum(len(str(m.get("content", ""))) for m in log) // 3
```

- [ ] **Step 2: Update `build_digest` for read deduplication and metadata-only**

Replace the entire `build_digest` function (lines 133–159) with:

```python
def build_digest(facts: "list[_StepFact]") -> str:
    """Build compact state digest from accumulated step facts.

    Read facts are deduplicated by path (latest wins) and emitted as metadata
    only — no content. This keeps the digest compact regardless of file sizes.
    Agent re-reads if it needs the content again.
    """
    # Deduplicate reads: last read of each path wins
    latest_reads: dict[str, "_StepFact"] = {}
    for f in facts:
        if f.kind == "read":
            latest_reads[f.path] = f

    sections: dict[str, list[str]] = {
        "LISTED": [], "READ": [], "FOUND": [],
        "DONE": [],
        "ERRORS": [],
        "STALLS": [],
    }
    for f in facts:
        if f.kind == "list":
            sections["LISTED"].append(f"  {f.path}: {f.summary}")
        elif f.kind == "read":
            if latest_reads.get(f.path) is f:  # emit only the latest read per path
                char_count = len(f.summary)
                sections["READ"].append(f"  {f.path}: (read, {char_count} chars)")
        elif f.kind == "search":
            sections["FOUND"].append(f"  {f.summary}")
        elif f.kind in ("write", "delete", "move", "mkdir"):
            sections["DONE"].append(f"  {f.summary}")
        elif f.kind == "stall":
            sections["STALLS"].append(f"  {f.summary}")
        if f.error:
            sections["ERRORS"].append(f"  {f.kind}({f.path}): {f.error}")
    parts = [
        f"{label}:\n" + "\n".join(lines)
        for label, lines in sections.items()
        if lines
    ]
    return "State digest:\n" + ("\n".join(parts) if parts else "(no facts)")
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run python -m pytest tests/test_log_compaction.py::test_estimate_tokens_empty tests/test_log_compaction.py::test_estimate_tokens_basic tests/test_log_compaction.py::test_estimate_tokens_multi_message tests/test_log_compaction.py::test_build_digest_read_dedup_keeps_latest tests/test_log_compaction.py::test_build_digest_read_shows_metadata tests/test_log_compaction.py::test_build_digest_write_preserved_in_full tests/test_log_compaction.py::test_build_digest_read_different_paths_both_present -v
```
Expected: all 7 PASS.

---

## Task 4: Tests for `_compact_log` new lazy trigger behaviour

**Files:**
- Modify: `tests/test_log_compaction.py`

- [ ] **Step 1: Add tests for lazy trigger and dynamic pairs**

Append to `tests/test_log_compaction.py`:

```python
def _make_log(n_pairs: int, msg_size: int = 10) -> list:
    """Build a log with n assistant+user message pairs of given size."""
    msgs = []
    for i in range(n_pairs):
        msgs.append({"role": "assistant", "content": "a" * msg_size})
        msgs.append({"role": "user", "content": "b" * msg_size})
    return msgs


def test_compact_log_no_trigger_below_threshold():
    """Below 70% fill → log returned unchanged."""
    from agent.log_compaction import _compact_log
    # token_limit=10000, 3000 chars total → 1000 tokens = 10% fill → no compaction
    log = _make_log(n_pairs=20, msg_size=75)  # 20*2*75 = 3000 chars → ~1000 tokens
    result = _compact_log(log, token_limit=10_000, compact_threshold_pct=0.70)
    assert result is log  # same object, not compacted


def test_compact_log_triggers_at_threshold():
    """At or above 70% fill → compaction happens."""
    from agent.log_compaction import _compact_log
    # token_limit=1000, need >700 tokens → >2100 chars
    log = _make_log(n_pairs=20, msg_size=120)  # 20*2*120=4800 chars → 1600 tokens >> 700
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    assert result is not log
    assert len(result) < len(log)


def test_compact_log_soft_fill_keeps_6_pairs():
    """70–85% fill → 6 pairs (12 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # Build a log that hits ~75% fill when token_limit=1000
    # 75% of 1000 = 750 tokens = 2250 chars; 14 pairs * 2 * 82 ≈ 2296 chars → ~765 tokens
    log = _make_log(n_pairs=14, msg_size=82)
    assert 0.70 <= _estimate_tokens(log) / 1_000 <= 0.85
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    # 1 summary msg + 12 tail msgs (6 pairs)
    assert len(result) == 13


def test_compact_log_medium_fill_keeps_4_pairs():
    """85–95% fill → 4 pairs (8 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # ~90% of 1000 = 900 tokens = 2700 chars; 17 pairs * 2 * 80 = 2720 → ~906 tokens
    log = _make_log(n_pairs=17, msg_size=80)
    fill = _estimate_tokens(log) / 1_000
    assert 0.85 <= fill <= 0.95, f"fill={fill:.2f} not in range for this test"
    result = _compact_log(log, token_limit=1_000, compact_threshold_pct=0.70)
    # 1 summary + 8 tail (4 pairs)
    assert len(result) == 9


def test_compact_log_aggressive_fill_keeps_3_pairs():
    """95%+ fill → 3 pairs (6 messages) kept in tail."""
    from agent.log_compaction import _compact_log, _estimate_tokens
    # >95% of 1000 = >950 tokens = >2850 chars; 18 pairs * 2 * 83 = 2988 → ~996 tokens
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
    prefix = []
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
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run python -m pytest tests/test_log_compaction.py::test_compact_log_no_trigger_below_threshold -v 2>&1 | head -20
```
Expected: `TypeError: _compact_log() got an unexpected keyword argument 'token_limit'` (old signature).

---

## Task 5: Implement `_compact_log` new signature and lazy logic

**Files:**
- Modify: `agent/log_compaction.py`

- [ ] **Step 1: Replace `_compact_log` signature and body**

Replace the entire `_compact_log` function (lines 166–215) with:

```python
def _compact_log(
    log: list,
    preserve_prefix: list | None = None,
    step_facts: "list[_StepFact] | None" = None,
    *,
    token_limit: int,
    compact_threshold_pct: float = 0.70,
) -> list:
    """Lazy sliding-window log compaction.

    Triggers only when estimated token fill exceeds compact_threshold_pct of
    token_limit. Pairs kept are chosen dynamically by fill level:
      70–85% → 6 pairs, 85–95% → 4 pairs, 95%+ → 3 pairs.
    Read facts in digest are deduplicated and stored as metadata only.
    """
    prefix_len = len(preserve_prefix) if preserve_prefix else 0
    tail = log[prefix_len:]

    # Lazy trigger: skip compaction when there is plenty of room
    estimated = _estimate_tokens(log)
    threshold = int(token_limit * compact_threshold_pct)
    if estimated < threshold:
        return log

    # Dynamic pairs based on fill level
    fill = estimated / token_limit
    if fill >= 0.95:
        max_tool_pairs = 3
    elif fill >= 0.85:
        max_tool_pairs = 4
    else:
        max_tool_pairs = 6

    max_msgs = max_tool_pairs * 2

    if len(tail) <= max_msgs:
        return log

    old = tail[:-max_msgs]
    kept = tail[-max_msgs:]

    # Extract confirmed operations from compacted pairs (safety net for done_ops)
    confirmed_ops = []
    for msg in old:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and content:
            for line in content.splitlines():
                if line.startswith(("WRITTEN:", "DELETED:", "MOVED:", "CREATED DIR:")):
                    confirmed_ops.append(line)

    parts: list[str] = []
    if confirmed_ops:
        parts.append("Confirmed ops (already done, do NOT redo):\n" + "\n".join(f"  {op}" for op in confirmed_ops))

    if step_facts:
        parts.append(build_digest(step_facts))
        print(f"\x1B[33m[compact] Compacted {len(old)} msgs into digest ({len(step_facts)} facts, fill={fill:.0%})\x1B[0m")
    else:
        summary_parts = []
        for msg in old:
            if msg.get("role") == "assistant" and msg.get("content"):
                summary_parts.append(f"- {msg['content'][:120]}")
        if summary_parts:
            parts.append("Actions taken:\n" + "\n".join(summary_parts[-5:]))

    summary = "Previous steps summary:\n" + ("\n".join(parts) if parts else "(none)")

    base = preserve_prefix if preserve_prefix is not None else log[:prefix_len]
    return list(base) + [{"role": "user", "content": summary}] + kept
```

- [ ] **Step 2: Run all compaction tests**

```bash
uv run python -m pytest tests/test_log_compaction.py -v
```
Expected: all tests PASS.

- [ ] **Step 3: Run full test suite to check for regressions**

```bash
uv run python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: no failures unrelated to the old `_compact_log` signature.

- [ ] **Step 4: Commit**

```bash
git add agent/log_compaction.py tests/test_log_compaction.py
git commit -m "feat(compaction): token-aware lazy compaction + read dedup in digest (FIX-409)"
```

---

## Task 6: Update loop.py call site

**Files:**
- Modify: `agent/loop.py`

- [ ] **Step 1: Update the `_compact_log` call in `_run_step`**

Find line containing `st.log = _compact_log(st.log, max_tool_pairs=5, preserve_prefix=st.preserve_prefix,` (around line 1975).

Replace that block with:

```python
    # FIX-409: lazy token-aware compaction; ctx_window from model config
    _ctx_window = cfg.get("ctx_window")
    if _ctx_window is None:
        print(f"[warn] ctx_window missing for model {model!r} — defaulting to 180000")
        _ctx_window = 180_000
    _compact_pct = float(os.getenv("CTX_COMPACT_THRESHOLD_PCT", "0.70"))
    st.log = _compact_log(st.log, preserve_prefix=st.preserve_prefix,
                          step_facts=st.step_facts, token_limit=_ctx_window,
                          compact_threshold_pct=_compact_pct)
```

- [ ] **Step 2: Run full test suite**

```bash
uv run python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add agent/loop.py
git commit -m "feat(loop): pass ctx_window to _compact_log, drop hardcoded max_tool_pairs=5 (FIX-409)"
```

---

## Task 7: Tests for `format_fragment` dead-end block and `load_wiki_patterns` dead ends

**Files:**
- Create: `tests/test_wiki_negatives.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_wiki_negatives.py
"""Tests for FIX-410: dead-end blocks in error fragments and injection at startup."""
import os
from pathlib import Path
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


def test_format_fragment_failure_adds_dead_end_block(tmp_path):
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
    import time
    for i in range(8):
        p = frag_dir / f"t{i:02d}_2026010{i}T000000Z.md"
        p.write_text(
            f"---\ntask_id: t{i:02d}\noutcome: OUTCOME_ERR_STALL\n---\n\n"
            f"## Dead end: t{i:02d}\nOutcome: OUTCOME_ERR_STALL\nWhat failed:\n- (unknown)\n"
        )
        p.touch()  # ensure different mtime via creation order
    with patch.object(wiki, "_FRAGMENTS_DIR", tmp_path / "fragments"):
        result = wiki._load_dead_ends("email")
    # Count entries: should be at most 5
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run python -m pytest tests/test_wiki_negatives.py -v 2>&1 | head -40
```
Expected: failures on `_load_dead_ends` (function not found) and `format_fragment` (no dead end block yet).

---

## Task 8: Implement dead-end block in `wiki.py`

**Files:**
- Modify: `agent/wiki.py`

- [ ] **Step 1: Add module-level env vars after existing ones (around line 43)**

After the `_GRAPH_AUTOBUILD` line, add:

```python
_WIKI_NEGATIVES_ENABLED = os.environ.get("WIKI_NEGATIVES_ENABLED", "1") == "1"
try:
    _WIKI_NEGATIVES_MAX_CHARS = int(os.environ.get("WIKI_NEGATIVES_MAX_CHARS", "800"))
except ValueError:
    _WIKI_NEGATIVES_MAX_CHARS = 800
```

- [ ] **Step 2: Add `_build_dead_end_block` helper after `_build_entity_raw`**

After `_build_entity_raw` (around line 539), add:

```python
def _build_dead_end_block(task_id: str, outcome: str, step_facts: list) -> str:
    """FIX-410: structured dead-end block appended to error fragments."""
    error_facts = [f for f in step_facts if hasattr(f, "error") and f.error]
    what_failed_lines = [
        f"- {f.kind}({f.path}): {f.error[:100]}"
        for f in error_facts
    ] or ["- (see outcome above)"]
    return (
        f"\n## Dead end: {task_id}\n"
        f"Outcome: {outcome}\n"
        f"What failed:\n" + "\n".join(what_failed_lines) + "\n"
    )
```

- [ ] **Step 3: Update failure path in `format_fragment` to append dead-end block**

In `format_fragment`, find the `if 0.0 <= score < 1.0:` block (around line 594). Replace:

```python
    if 0.0 <= score < 1.0:
        # Failure path: domain-separated errors (not mixed into pages used at runtime)
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        domain = task_type if task_type in _TYPE_TO_PAGE else "default"
        results.append((raw, f"errors/{domain}"))
        return results
```

With:

```python
    if 0.0 <= score < 1.0:
        # Failure path: domain-separated errors (not mixed into pages used at runtime)
        raw = _build_raw_fragment(
            outcome, task_type, task_id, task_text, today,
            step_facts, done_ops, stall_hints, eval_last_call,
        )
        raw += _build_dead_end_block(task_id, outcome, step_facts)  # FIX-410
        domain = task_type if task_type in _TYPE_TO_PAGE else "default"
        results.append((raw, f"errors/{domain}"))
        return results
```

- [ ] **Step 4: Add `_load_dead_ends` function after `load_wiki_patterns`**

After the `load_wiki_patterns` function (around line 285), add:

```python
def _load_dead_ends(task_type: str) -> str:
    """FIX-410: load last 5 error fragments and format as KNOWN DEAD ENDS block.

    Parses ## Dead end: blocks written by _build_dead_end_block.
    Falls back to frontmatter task_id/outcome for legacy fragments.
    Returns '' if no error fragments exist for this task_type.
    """
    if not _WIKI_NEGATIVES_ENABLED:
        return ""
    domain = _TYPE_TO_PAGE.get(task_type, task_type)
    frag_dir = _FRAGMENTS_DIR / "errors" / domain
    if not frag_dir.exists():
        return ""

    frags = sorted(frag_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    if not frags:
        return ""

    entries: list[str] = []
    for frag_path in reversed(frags):  # chronological: oldest first
        try:
            text = frag_path.read_text(encoding="utf-8")
            m = re.search(
                r"^## Dead end: (\S+)\nOutcome: (\S+)\nWhat failed:\n(.*?)(?=\n## |\Z)",
                text, re.MULTILINE | re.DOTALL,
            )
            if m:
                tid, out, what = m.group(1), m.group(2), m.group(3).strip()
                first_fail = what.splitlines()[0] if what.splitlines() else "(unknown)"
                entries.append(f"- {tid} ({out}): {first_fail[:120]}")
            else:
                # Legacy fragment without dead-end block
                tid_m = re.search(r"^task_id: (\S+)", text, re.MULTILINE)
                out_m = re.search(r"^outcome: (\S+)", text, re.MULTILINE)
                if tid_m and out_m:
                    entries.append(f"- {tid_m.group(1)} ({out_m.group(1)}): (legacy fragment)")
        except Exception:
            continue

    if not entries:
        return ""

    header = f"## KNOWN DEAD ENDS ({task_type})"
    # Trim from oldest if over char limit
    while entries and len(header + "\n" + "\n".join(entries)) > _WIKI_NEGATIVES_MAX_CHARS:
        entries.pop(0)

    return (header + "\n" + "\n".join(entries)) if entries else ""
```

- [ ] **Step 5: Update `load_wiki_patterns` to accept and use `include_negatives`**

Replace:

```python
def load_wiki_patterns(task_type: str) -> str:
    """Load patterns page for the given task type.

    Fail-open: returns '' if page doesn't exist.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    if content:
        return f"## Wiki: {task_type} Patterns\n{content}"
    return ""
```

With:

```python
def load_wiki_patterns(task_type: str, include_negatives: bool = True) -> str:
    """Load patterns page for the given task type.

    include_negatives=True (default) appends a KNOWN DEAD ENDS block from the
    last 5 error fragments for this task_type (FIX-410). Fail-open.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    parts = []
    if content:
        parts.append(f"## Wiki: {task_type} Patterns\n{content}")
    if include_negatives:
        negatives = _load_dead_ends(task_type)
        if negatives:
            parts.append(negatives)
    return "\n\n".join(parts)
```

- [ ] **Step 6: Run wiki negatives tests**

```bash
uv run python -m pytest tests/test_wiki_negatives.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 7: Run full test suite**

```bash
uv run python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add agent/wiki.py tests/test_wiki_negatives.py
git commit -m "feat(wiki): inject dead-end blocks from error fragments at agent startup (FIX-410)"
```

---

## Task 9: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add new env vars to the Wiki toggles section**

Find the `# ─── Wiki toggles` section and append:

```
# WIKI_NEGATIVES_ENABLED=1            # 0 = не инжектировать dead ends в system prompt
# WIKI_NEGATIVES_MAX_CHARS=800        # макс символов для блока KNOWN DEAD ENDS
```

Find the `# ─── Benchmark` section and add to compaction config (new section after `PARALLEL_TASKS`):

```
# ─── Context compaction ──────────────────────────────────────────────────────
# CTX_COMPACT_THRESHOLD_PCT=0.70      # доля ctx_window при которой срабатывает компактинг
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs(env): document CTX_COMPACT_THRESHOLD_PCT and WIKI_NEGATIVES_* vars"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run complete test suite**

```bash
uv run python -m pytest tests/ -q 2>&1 | tail -20
```
Expected: all pass, no skips on affected tests.

- [ ] **Step 2: Smoke-check models.json reading in Python**

```bash
python3 -c "
import json
m = json.load(open('models.json'))
for k, v in m.items():
    if k.startswith('_'): continue
    assert 'ctx_window' in v, f'{k} missing ctx_window'
    print(k, v['ctx_window'])
"
```
Expected: all model entries print their `ctx_window` value.

- [ ] **Step 3: Smoke-check `_compact_log` is lazy for small logs**

```bash
python3 -c "
from agent.log_compaction import _compact_log
log = [{'role': 'user', 'content': 'hello'}] * 5
result = _compact_log(log, token_limit=200_000)
assert result is log, 'should not compact tiny log'
print('lazy compaction OK')
"
```
Expected: `lazy compaction OK`

- [ ] **Step 4: Smoke-check dead ends load gracefully when no fragments exist**

```bash
python3 -c "
from agent.wiki import _load_dead_ends
result = _load_dead_ends('email')
print('dead ends result:', repr(result[:80]) if result else '(empty, OK)')
"
```
Expected: either `(empty, OK)` or a `## KNOWN DEAD ENDS` block if fragments exist.
