# Design: Context-Aware Deduplication in propose_optimizations.py

**Date:** 2026-05-12  
**File:** `scripts/propose_optimizations.py`

## Problem

`_synthesize_rule` already passes existing rules to the LLM so it can skip duplicates. The other two synthesis functions do not:

- `_synthesize_security_gate` — LLM has no knowledge of existing security gates → may produce duplicate patterns/checks.
- `_synthesize_prompt_patch` — LLM has no knowledge of existing prompt content → may add sections that already exist.

## Solution

Add two helper functions and pass existing context into the LLM prompts for security and prompt synthesis.

## New Helper Functions

### `_existing_security_text() -> str`

Reads all `*.yaml` from `data/security/`. For each valid record returns `"- {id}: {message}"`. Returns joined lines.

### `_existing_prompts_text() -> str`

Reads all `*.md` from `data/prompts/` (excluding `optimized/` subdirectory). Returns full content of each file in format:

```
=== filename.md ===
<full file content>
```

## Modified Signatures

### `_synthesize_security_gate(raw_rec, existing_security_md, model, cfg) -> dict | None`

System prompt addition (before existing instructions):

```
If the recommendation is already fully covered by an existing gate, respond with exactly: null

Existing gates:
{existing_security_md}
```

### `_synthesize_prompt_patch(raw_rec, existing_prompts_md, model, cfg) -> dict | None`

System prompt addition (before existing instructions):

```
If the recommendation is already present in the existing prompt content, respond with exactly: null

Existing prompt files:
{existing_prompts_md}
```

## Changes in `main()`

Load context once before the entry loop:

```python
security_md = _existing_security_text()
prompts_md = _existing_prompts_text()
```

Pass to respective synthesize calls inside the loop.

## Scope

- No new dependencies.
- No changes to output format or file structure.
- No changes to `_synthesize_rule` (already correct).
- ~30 lines added/modified total.
