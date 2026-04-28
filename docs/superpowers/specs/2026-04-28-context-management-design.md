# Context Management Redesign

**Date:** 2026-04-28
**Status:** Approved

## Problem Statement

Two independent classes of context degradation in normal mode (`run_loop`, up to 30 steps):

1. **Within-task context loss** — agent forgets earlier actions, repeats reads and searches. Correlates with large `read` responses. Root cause: compaction triggers on message COUNT every step, regardless of actual token fill level.

2. **Between-run knowledge loss** — agent restarts as if from scratch. Wiki/graph patterns aren't effectively reinforced by failure; only `score=1.0` updates `pages/<task_type>.md`.

## Design

### Problem 1: Token-Aware Compaction

#### Current Behaviour (broken)

`_compact_log(max_tool_pairs=5)` is called unconditionally before every LLM call (loop.py:1975). This:
- Drops context that fits comfortably within the model's 200K window
- Keeps only last 10 messages regardless of actual token usage
- Read content survives compaction as a flattened single-line in `step_facts`, which is harder for LLM to process
- Digest grows unbounded — all read facts accumulate including duplicate reads of the same file

#### New Behaviour

Compaction becomes **lazy**: triggers only when estimated token count exceeds a threshold derived from the model's context window.

**Token estimation** (fast, no API call):
```python
def _estimate_tokens(log: list) -> int:
    return sum(len(str(m.get("content", ""))) for m in log) // 3
```
Conservative ratio: 3 chars/token covers mixed-language content.

**Dynamic pairs selection** based on fill level:
- 70–85% of `ctx_window` → 6 pairs (soft)
- 85–95% → 4 pairs (medium)
- 95%+ → 3 pairs (aggressive)
- Below 70% → no compaction

**Read facts in digest** — metadata only, no content:
```
READ:
  /contacts/alice.md: (read, 1847 chars)
  /inbox/t42.md: (read, 312 chars)
```
Agent re-reads if needed. No truncation mid-content.

**Deduplication** — READ section keeps only the latest fact per path. Multiple reads of the same file collapse to one entry.

**Write/delete/move/mkdir/errors** — unchanged, preserved in full.

#### Interface Changes

`_compact_log()` new signature:
```python
def _compact_log(
    log: list,
    preserve_prefix: list | None = None,
    step_facts: list | None = None,
    token_limit: int,
    compact_threshold_pct: float = 0.70,
) -> list:
```
`max_tool_pairs` removed — calculated dynamically. `token_limit` is required — no default.

`run_loop()` reads env var and passes both to `_compact_log`:
```python
_ctx_window = cfg.get("ctx_window")
if _ctx_window is None:
    print(f"[warn] ctx_window missing for model {model!r} — defaulting to 180000")
    _ctx_window = 180_000
_compact_pct = float(os.getenv("CTX_COMPACT_THRESHOLD_PCT", "0.70"))
st.log = _compact_log(st.log, preserve_prefix=st.preserve_prefix,
                      step_facts=st.step_facts, token_limit=_ctx_window,
                      compact_threshold_pct=_compact_pct)
```

#### `models.json` Changes

New field `ctx_window` added to `_fields` documentation and every model entry:

| Provider | Value |
|---|---|
| `anthropic/*` | `200000` |
| `claude-code/*` | `200000` |
| Ollama models (default profile) | `16384` |
| Ollama models (long_ctx profile) | `32768` |
| `qwen/qwen3.5-9b` | `131072` |
| `meta-llama/llama-3.3-70b-instruct` | `131072` |

Fallback in code: `cfg.get("ctx_window", 180_000)` — only if a model entry is missing the field.

#### New Env Var

| Variable | Default | Description |
|---|---|---|
| `CTX_COMPACT_THRESHOLD_PCT` | `0.70` | Compaction trigger threshold as fraction of `ctx_window` |

---

### Problem 2: Wiki/Graph Knowledge Between Runs

#### Current Behaviour (incomplete)

- Wiki patterns from `pages/<task_type>.md` injected at startup (preserve_prefix)
- Pages updated only on `score=1.0`
- Failures write to `fragments/errors/<task_type>/` but **never read back** into the agent
- Graph degrades confidence on failure nodes but carries no explicit "don't try this" signal

#### New Behaviour

**Error fragments gain structure.** `format_fragment()` at `score < 1.0` appends:
```markdown
## Dead end: <task_id>
Outcome: <OUTCOME_*>
What failed: <list of errored step_facts>
```

**Dead ends injected at startup.** `load_wiki_patterns(task_type)` gains parameter `include_negatives=True` (default on). Reads last 5 error fragments for the task type (sorted by mtime), formats them as:
```
## KNOWN DEAD ENDS (email)
- t12: searched contact by name — not found; correct path: /contacts/
- t19: guessed file path without tree — file was in nested folder
```

Total dead ends block capped at `WIKI_NEGATIVES_MAX_CHARS` (default 800). Oldest fragments are dropped first if over limit.

**Injection point:** same `preserve_prefix` slot as wiki patterns (appended after success patterns). No new message slot.

#### New Env Vars

| Variable | Default | Description |
|---|---|---|
| `WIKI_NEGATIVES_ENABLED` | `1` | Inject dead ends into system prompt |
| `WIKI_NEGATIVES_MAX_CHARS` | `800` | Max chars for dead ends block |

---

## Files Changed

| File | Change |
|---|---|
| `agent/log_compaction.py` | `_estimate_tokens()`, `_compact_log()` new signature + lazy trigger + read dedup |
| `agent/loop.py` | Remove `max_tool_pairs=5`, pass `token_limit=_ctx_window` |
| `agent/wiki.py` | `load_wiki_patterns()` + `include_negatives`, `format_fragment()` dead end block |
| `models.json` | Add `ctx_window` field to all model entries |
| `.env.example` | Document `CTX_COMPACT_THRESHOLD_PCT`, `WIKI_NEGATIVES_ENABLED`, `WIKI_NEGATIVES_MAX_CHARS` |

## FIX Label

Next sequential label: `FIX-409` (token-aware compaction), `FIX-410` (dead ends injection).
