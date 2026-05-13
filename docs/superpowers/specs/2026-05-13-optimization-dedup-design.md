# Optimization Pipeline Deduplication — Design

**Date:** 2026-05-13  
**Status:** Approved

## Problem

Three compounding issues cause 76+ duplicate/contradictory rules and 87 prompt patches:

1. **Evaluator is blind** — `pipeline_evaluator.md` generates recommendations without seeing existing rules/security/prompts → same topics recommended on every failure (grounding_refs: 48×, reasoning: 35×, DROP/DDL: 15×).
2. **Synthesizer static snapshot** — `_existing_*_text()` loaded once before the loop; files written in iteration N are invisible to iterations N+1..K within the same run.
3. **No pre-deduplication** — 160 rule / 122 security / 238 prompt raw recommendations processed individually; semantically identical entries each trigger a separate LLM synthesis call and potentially a separate output file.
4. **No contradiction detection** — new rules/gates/prompts written without checking conflict with existing content, confusing the LLM at task execution time.

## Solution: Approach A — Layered Dedup

### Component 1: `agent/knowledge_loader.py` (new)

Shared module exposing three functions previously duplicated across `scripts/propose_optimizations.py` and (after this change) `agent/evaluator.py`:

```python
def existing_rules_text() -> str: ...      # reads data/rules/*.yaml
def existing_security_text() -> str: ...   # reads data/security/*.yaml
def existing_prompts_text() -> str: ...    # reads data/prompts/*.md
```

Both evaluator and synthesizer import from here.

### Component 2: Evaluator context injection

**Files:** `agent/evaluator.py`, `data/prompts/pipeline_evaluator.md`

`_build_eval_system(agents_md)` → `_build_eval_system(agents_md, rules_md, security_md, prompts_md)`

Three new blocks injected into system prompt:
```
# EXISTING RULES
{rules_md}

# EXISTING SECURITY GATES
{security_md}

# EXISTING PROMPT CONTENT
{prompts_md}
```

`pipeline_evaluator.md` gains instruction in `## Assess`:
> "7. Before generating any suggestion, check EXISTING RULES / EXISTING SECURITY GATES / EXISTING PROMPT CONTENT above. Skip topics already covered."

`run_evaluator()` calls `knowledge_loader.*` to load content before passing to `_run()`.

### Component 3: Synthesizer — live existing_* refresh

**File:** `scripts/propose_optimizations.py`

After every `_write_*()` call, reload the relevant `existing_*` string:

```python
dest = _write_rule(num, content, entry, raw_rec)
rules_md = knowledge_loader.existing_rules_text()   # refresh
```

Same for `security_md` after `_write_security()` and `prompts_md` after `_write_prompt()`.

### Component 4: Pre-cluster raw_recs

**File:** `scripts/propose_optimizations.py`

New function `_cluster_recs(recs, existing_md, model, cfg) -> list[str]`:
- Single LLM call per channel before the main loop
- Input: all unprocessed raw_recs for the channel + existing_md
- Output: deduplicated representative list (semantically merged, covered items removed)
- Hash tracking: cluster representative maps to all original hashes → all mapped hashes marked processed immediately upon successful write of the representative; on failure, none are marked
- Fallback: if `_cluster_recs` LLM call fails, fall back to original unflattened raw_recs (fail-open, no crash)

Prompt instruction:
> "Return a JSON array of unique, non-redundant recommendations. Merge semantically equivalent items. Drop items already covered by existing content. Keep the most specific/actionable wording."

### Component 5: Contradiction detection

**File:** `scripts/propose_optimizations.py`

New function `_check_contradiction(new_content, existing_md, model, cfg) -> str | None`:
- Returns `None` if no conflict, or `"CONFLICT: <id> — <reason>"` string
- Applied to **all three channels** (rule, security, prompt) before write, using channel-appropriate `existing_md`

Prompt:
> "Check if the new content contradicts any existing item. A contradiction means opposite instructions for the same scenario. If found: CONFLICT: <id> — <reason>. If not: OK"

Flow per channel:
```
synthesize → contradiction check → (skip if conflict) → write → refresh existing_*
```

## Data Flow

```
eval_log.jsonl
    │
    ├─ [pre-cluster per channel] ──────────────── 1 LLM call/channel
    │       ↓ deduplicated raw_recs
    │
    ├─ synthesize(raw_rec, existing_md)
    │       ↓ content or null
    ├─ check_contradiction(content, existing_md)
    │       ↓ ok or skip
    ├─ write file
    └─ refresh existing_md from disk
```

## Files Changed

| File | Change |
|------|--------|
| `agent/knowledge_loader.py` | New — shared loader for rules/security/prompts text |
| `agent/evaluator.py` | `_build_eval_system` + `run_evaluator` accept existing content |
| `data/prompts/pipeline_evaluator.md` | Add rule 7: check existing before suggesting |
| `scripts/propose_optimizations.py` | Pre-cluster, live refresh, contradiction check; import knowledge_loader |

## Out of Scope

- Retroactive cleanup of existing 76 rules / 76 security gates (separate task)
- Embedding-based similarity (LLM-only approach chosen)
- Contradiction detection for already-written `verified: false` files (separate pass)
