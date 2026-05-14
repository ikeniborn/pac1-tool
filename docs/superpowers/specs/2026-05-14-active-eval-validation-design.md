# Active Eval Validation Design

**Date:** 2026-05-14  
**Status:** Approved

## Problem

Current eval is passive: scores pipeline trace, writes recommendations to `eval_log.jsonl`, recommendations applied offline via `propose_optimizations.py` without testing whether they actually improve results.

Goal: `propose_optimizations.py` validates each recommendation by re-running the original task with the recommendation injected, then decides to write the rule/prompt/security file only if score does not regress.

## Architecture

### Eval (unchanged)

`evaluator.py` remains passive. One addition: `EvalInput` gets a `task_id: str` field, written to `eval_log.jsonl` as `"task_id"`. Original score is read from trace files (see `read_original_score` below) — not stored in eval_log.

### Injection Parameters

Three new optional params added to `run_agent`, `run_pipeline`, and `_build_static_system`:

```python
injected_session_rules: list[str] = []       # → prepopulates session_rules
injected_prompt_addendum: str = ""            # → appended to guide block in _build_static_system
injected_security_gates: list[dict] = []     # → merged into security gates at pipeline start
```

`injected_prompt_addendum` appends to the guide block for phases that use `_build_static_system` (`sql_plan`, `learn`, `answer`). `resolve` uses a plain string and is not affected.

```python
guide_text = guide or f"# PHASE: {phase}"
if injected_prompt_addendum:
    guide_text += f"\n\n# INJECTED OPTIMIZATION\n{injected_prompt_addendum}"
```

`injected_security_gates` format: each dict must match the structure used by `load_security_gates()`:
`{"id": str, "pattern": str, "message": str, "verified": true}` (or `"check_name"` instead of `"pattern"` for named checks).

`injected_security_gates` merged in `run_pipeline` before `_get_security_gates()` result is used:

```python
security_gates = _get_security_gates() + (injected_security_gates or [])
```

### prompt_optimization list→str conversion

`PipelineEvalOutput.prompt_optimization` is `list[str]`. Each element is validated separately — one `validate_recommendation()` call per element. When injecting into `_build_static_system`, a single element is passed as `injected_prompt_addendum`. Multiple elements are never concatenated into one run; each gets its own validation run and its own output file if accepted.

### Re-run Mechanism (Embedded)

`propose_optimizations.py` validates each recommendation via a new `validate_recommendation()` function.

**Disabling eval during validation:** `validate_recommendation()` sets `EVAL_ENABLED=0` in the subprocess environment before calling `run_agent()`. Since `_EVAL_ENABLED` is read at module import time in `pipeline.py`, validation calls `run_agent()` in a fresh subprocess (or patches the env before import). Implementation: set `os.environ["EVAL_ENABLED"] = "0"` at the top of `validate_recommendation()`, restore after. This prevents recursive eval threads during validation runs.

**read_original_score:** scans `logs/*/` dirs, excludes dirs whose name starts with `"validate-"`, picks the latest by mtime, reads `{task_id}.jsonl`, extracts `task_result.score` event. Returns `None` if not found (validation skipped, file written unconditionally with warning).

**Deduplication of eval_log entries:** for a given `task_id`, group all eval_log entries by `task_id`. Per recommendation type (`rule_optimization`, `prompt_optimization`, `security_optimization`), deduplicate by content hash before validation — identical recommendations from multiple runs are validated only once. The existing `.eval_optimizations_processed` hash store continues to track processed entries.

```
original_score = read_original_score(task_id)

client = HarnessServiceClientSync(BITGN_URL)
run = client.start_run(
    name=f"validate-{timestamp}",
    benchmark_id=BENCHMARK_ID,
    api_key=BITGN_API_KEY,
)

os.environ["EVAL_ENABLED"] = "0"
try:
    for trial_id in run.trial_ids:
        trial = client.start_trial(trial_id)
        if trial.task_id != task_id:
            client.end_trial(trial.trial_id)   # no answer, score=0, irrelevant
            continue
        run_agent(
            model_configs={},
            harness_url=trial.harness_url,
            task_text=trial.instruction,
            task_id=trial.task_id,
            injected_session_rules=rules,
            injected_prompt_addendum=prompt_addon,
            injected_security_gates=gates,
        )
        result = client.end_trial(trial.trial_id)
        validation_score = result.score
        break
finally:
    os.environ["EVAL_ENABLED"] = original_eval_enabled  # restore

client.submit_run(run_id=run.run_id, force=True)
```

Validation runs use `name=f"validate-{timestamp}"` — excluded from `read_original_score` lookups and separate from main leaderboard runs.

### Scoring Decision

```
if original_score is None:
    write file (verified: false), log WARNING: no baseline score found

elif validation_score >= original_score:
    write file (verified: false)
    log ACCEPTED: score {original} → {validation}

else:
    log REJECTED: score {original} → {validation}
    do not write file
```

Threshold: `>=` (no regression). Files still written as `verified: false` — human must set `verified: true` to activate.

### Default behavior

Validation is **on by default**. `--dry-run` skips validation and writes files unconditionally (current behavior). No separate `--validate` flag needed.

### --dry-run flag

Preserved. With `--dry-run`: skip validation, write files as before.

### Recommendation Types → Injection Mapping

| eval field | injection param | file written | notes |
|---|---|---|---|
| `rule_optimization` | `injected_session_rules` | `data/rules/sql-NNN.yaml` | list joined as multiple rules, each validated separately |
| `prompt_optimization` | `injected_prompt_addendum` | `data/prompts/optimized/YYYY-MM-DD-NN-<block>.md` | each list element validated separately, one file per accepted element |
| `security_optimization` | `injected_security_gates` | `data/security/sec-NNN.yaml` | each element validated separately |

### Files Changed

| File | Change |
|---|---|
| `agent/evaluator.py` | Add `task_id: str` to `EvalInput`; write `task_id` to eval_log entry |
| `agent/pipeline.py` | `run_pipeline` signature gets `task_id: str = ""` + 3 injection params; `_build_static_system` gets `injected_prompt_addendum: str = ""`; security gates merge; `task_id` forwarded to `_run_evaluator_safe` kwargs |
| `agent/orchestrator.py` | `run_agent` gets `task_id` (already exists) + 3 injection params, passes all to `run_pipeline` |
| `scripts/propose_optimizations.py` | Add `validate_recommendation()`, `read_original_score()`; deduplicate by content hash; gate file writes on validation result; set/restore `EVAL_ENABLED=0` during validation; preserve `--dry-run` |

### Out of Scope

- Eval thread does not wait for validation (remains async, passive)
- `eval` does not auto-apply recommendations — propose_optimizations still requires manual run
- No change to `verified: false` default — human review gate preserved
- Parallel validation of multiple tasks: not implemented (sequential per recommendation)
