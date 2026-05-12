# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Preview what would be written (no files changed)
uv run python scripts/propose_optimizations.py --dry-run

# Write candidate files to data/
uv run python scripts/propose_optimizations.py

# Run tests for this script
uv run pytest tests/test_propose_optimizations.py -v
```

Requires `MODEL_EVALUATOR` env var (e.g. `anthropic/claude-haiku-4-5-20251001`). Script reads `.env` via `dotenv`.

## What This Script Does

`propose_optimizations.py` reads `data/eval_log.jsonl` and synthesizes raw LLM recommendations into ready-to-review candidate files. Three output channels:

| Channel key | Output path | Activation |
|------------|------------|-----------|
| `rule_optimization` | `data/rules/sql-NNN.yaml` | Set `verified: true` |
| `security_optimization` | `data/security/sec-NNN.yaml` | Set `verified: true` |
| `prompt_optimization` | `data/prompts/optimized/YYYY-MM-DD-NN-<file>.md` | Manually copy section into `data/prompts/<file>.md` |

All candidates written with `verified: false`. Nothing activates automatically.

## Deduplication

Processed entries tracked by SHA-256 hash of `(channel|task_text|raw_rec)` in `data/.eval_optimizations_processed`. Subsequent runs skip already-processed hashes regardless of `--dry-run`.

In `--dry-run` mode, skipped entries are **not** added to the processed set — preview is truly non-destructive.

## Synthesizer Behavior

Each channel calls `agent.llm.call_llm_raw` with:
- Existing content injected into system prompt to prevent duplicates (`_existing_rules_text`, `_existing_security_text`, `_existing_prompts_text`)
- LLM returns `null` (string) if recommendation is already covered → entry marked processed, no file written
- `_next_num()` scans the target directory to compute the next sequential ID

**Do not remove the `_existing_*` helpers or omit them from synthesizer prompts** — without them the LLM will generate duplicate rules.

## Adding a New Channel

1. Add a synthesizer function `_synthesize_<channel>(raw_rec, existing_md, model, cfg) -> <type> | None`
2. Add a writer function `_write_<channel>(...)  -> Path`
3. Add a loop block in `main()` matching the pattern of the existing three channels
4. Add dedup hash with a unique channel string (must differ from `"rule"`, `"security"`, `"prompt"`)
