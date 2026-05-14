# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Run from the repo root (`ecom1-agent/`):

```bash
# Preview what would be written (no files changed, processed set unchanged)
uv run python scripts/propose_optimizations.py --dry-run

# Write candidate files to data/ (validates each rec against harness before writing)
uv run python scripts/propose_optimizations.py

# Run tests for this script
uv run pytest tests/test_propose_optimizations.py -v
```

Requires `MODEL_EVALUATOR` env var (e.g. `anthropic/claude-haiku-4-5-20251001`). Script reads `.env` via `dotenv`.

For harness validation (`--no-dry-run` path): also needs `BITGN_API_KEY`, `BENCHMARK_HOST`, `BENCHMARK_ID`.

## What This Script Does

`propose_optimizations.py` reads `data/eval_log.jsonl` and synthesizes raw LLM recommendations into ready-to-review candidate files. Three output channels:

| Channel key | Output path | Activation |
|------------|------------|-----------|
| `rule_optimization` | `data/rules/sql-NNN.yaml` | Set `verified: true` |
| `security_optimization` | `data/security/sec-NNN.yaml` | Set `verified: true` |
| `prompt_optimization` | `data/prompts/optimized/YYYY-MM-DD-NN-<file>.md` | Manually copy section into `data/prompts/<file>.md` |

All candidates written with `verified: false`. Nothing activates automatically.

## Validation Gate (non-dry-run only)

Before writing any candidate, the script re-runs the originating task through the BitGN harness with the recommendation injected (`validate_recommendation`). A candidate is written **only if `validation_score >= original_score`**. If there is no baseline score in `logs/`, the candidate is written with a warning. If the task is not found in the trial set, the candidate is skipped entirely.

`read_original_score` reads from the latest non-`validate-*` directory under `logs/`.

## Processing Pipeline per Channel

1. **Flatten** — collect all unprocessed recs from `eval_log.jsonl` by channel key.
2. **Content-hash dedup** — `_dedup_by_content_per_task`: drop exact-duplicate recs within the same `task_id`; mark their hashes processed immediately.
3. **LLM cluster** — `_cluster_recs`: one LLM call merges semantically equivalent recs across tasks; returns representative recs.
4. **Synthesize** — `_synthesize_rule / _synthesize_security_gate / _synthesize_prompt_patch`: LLM call converts representative rec to structured form; returns `None` if already covered (LLM responds `null`).
5. **Contradiction check** — `_check_contradiction`: rejects the candidate if it directly contradicts an existing rule/gate.
6. **Validate** — harness re-run (step above); write only on score ≥ original.

## Deduplication

Processed entries tracked by SHA-256 hash of `(channel|task_text|raw_rec)` in `data/.eval_optimizations_processed`. Subsequent runs skip already-processed hashes regardless of `--dry-run`.

In `--dry-run` mode, skipped entries are **not** added to the processed set — preview is truly non-destructive.

## Synthesizer Behavior

Each channel calls `agent.llm.call_llm_raw` with existing content injected into the system prompt to prevent duplicates (`_existing_rules_text`, `_existing_security_text`, `_existing_prompts_text` via `agent.knowledge_loader`).

- LLM returns `null` (string) → entry marked processed, no file written.
- `_next_num()` scans the target directory to compute the next sequential ID.

**Do not remove the `_existing_*` helpers or omit them from synthesizer prompts** — without them the LLM will generate duplicate rules.

`call_llm_raw_cluster` is a module-level alias to `call_llm_raw` intentionally exposed for test patching without affecting the synthesizer calls.

## Adding a New Channel

1. Add a synthesizer function `_synthesize_<channel>(raw_rec, existing_md, model, cfg) -> <type> | None`
2. Add a writer function `_write_<channel>(...)  -> Path`
3. Add a loop block in `main()` matching the pattern of the existing three channels (flatten → dedup → cluster → synthesize → contradiction-check → validate → write)
4. Add dedup hash with a unique channel string (must differ from `"rule"`, `"security"`, `"prompt"`)
