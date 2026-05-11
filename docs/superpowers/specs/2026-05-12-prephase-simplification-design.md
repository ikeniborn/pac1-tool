# Prephase Simplification + dry_run Analysis

**Date:** 2026-05-12

## Goal

Strip redundant reads from `run_prephase()`, leaving only AGENTS.MD + task. Add `dry_run_analysis.jsonl` logging when `dry_run=True`.

## What Gets Removed

| Step | Code | Removed |
|------|------|---------|
| 1 | `vm.tree(TreeRequest(root="/", level=2))` + `_render_tree_result()` | Yes |
| 2.5 | `_read_dir()` + auto-preload dirs from AGENTS.MD | Yes |
| 3 | VAULT_DATE estimation (all 5 strategies) | Yes |
| 4 | `vm.context(ContextRequest())` | Yes |

## What Stays

- System prompt injection
- Few-shot pair (JSON output format)
- `/AGENTS.MD` read (hardcoded path)
- `task_text` in prephase_parts

## PrephaseResult Changes

Remove fields:
- `vault_tree_text: str`
- `vault_date_est: str`
- `inbox_files: list`
- `sql_schema: str`

Keep fields:
- `log: list`
- `preserve_prefix: list`
- `agents_md_content: str`
- `agents_md_path: str`

## dry_run Behavior

### Signature change

```python
run_prephase(vm, task_text, system_prompt_text, task_id: str = "", dry_run: bool = False)
```

### Logic

When `dry_run=True`:
1. Read `/bin/sql` via `vm.read(ReadRequest(path="/bin/sql"))`
2. Append one JSON line to `dry_run_analysis.jsonl`:

```json
{"task_id": "...", "task": "...", "agents_md": "...", "bin_sql_content": "..."}
```

3. Do **not** inject `/bin/sql` content into LLM context.

`dry_run_analysis.jsonl` location: `data/dry_run_analysis.jsonl`.

## Orchestrator Changes

`agent/orchestrator.py` must pass `task_id` and `dry_run` to `run_prephase()`. These values must already be available in orchestrator scope (from config/CLI args).

## Files Changed

- `agent/prephase.py` — primary changes
- `agent/orchestrator.py` — pass new args
- `agent/loop.py` — remove references to dropped PrephaseResult fields (inbox_files, vault_tree_text, vault_date_est, sql_schema)

## Success Criteria

- `run_prephase()` makes exactly 1 `vm.read()` call in normal mode (AGENTS.MD)
- `run_prephase()` makes exactly 2 calls in dry_run mode (AGENTS.MD + /bin/sql)
- `dry_run_analysis.jsonl` gets one appended line per dry_run invocation
- No LLM context contains `/bin/sql` content
- All existing tests pass
