# Active Eval Validation Design

**Date:** 2026-05-14  
**Status:** Approved

## Problem

Current eval is passive: scores pipeline trace, writes recommendations to `eval_log.jsonl`, recommendations applied offline via `propose_optimizations.py` without testing whether they actually improve results.

Goal: `propose_optimizations.py` validates each recommendation by re-running the original task with the recommendation injected, then decides to write the rule/prompt/security file only if score does not regress.

## Architecture

### Eval (unchanged)

`evaluator.py` remains passive. One addition: `EvalInput` gets a `task_id: str` field, written to `eval_log.jsonl` as `"task_id"`. Original score is read from `logs/{task_id}.jsonl` (trace file, `task_result.score` event) — not stored in eval_log.

### Injection Parameters

Three new optional params added to `run_agent` and `run_pipeline`:

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

`injected_security_gates` merged in `run_pipeline` before `_get_security_gates()` result is used:

```python
security_gates = _get_security_gates() + (injected_security_gates or [])
```

### Re-run Mechanism (Embedded)

`propose_optimizations.py` validates each recommendation via a new `validate_recommendation()` function:

```
original_score = read_original_score(task_id)  # scans logs/*/{task_id}.jsonl, picks latest by mtime, reads task_result.score event

client = HarnessServiceClientSync(BITGN_URL)
run = client.start_run(
    name=f"validate-{timestamp}",
    benchmark_id=BENCHMARK_ID,
    api_key=BITGN_API_KEY,
)

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

client.submit_run(run_id=run.run_id, force=True)
```

Validation runs use `BITGN_RUN_NAME = f"validate-{timestamp}"` — separate from main leaderboard runs.

### Scoring Decision

```
if validation_score >= original_score:
    write rule/security/prompt file (verified: false, human review still required)
    log ACCEPTED: score {original} → {validation}
else:
    log REJECTED: score {original} → {validation}
    do not write file
```

Threshold: `>=` (no regression). Files still written as `verified: false` — human must set `verified: true` to activate.

### --dry-run flag

Preserved. With `--dry-run`: skip validation, write files as before (current behavior).

### Recommendation Types → Injection Mapping

| eval field | injection param | file written |
|---|---|---|
| `rule_optimization` | `injected_session_rules` | `data/rules/sql-NNN.yaml` |
| `prompt_optimization` | `injected_prompt_addendum` | `data/prompts/optimized/YYYY-MM-DD-NN-<block>.md` |
| `security_optimization` | `injected_security_gates` | `data/security/sec-NNN.yaml` |

### Files Changed

| File | Change |
|---|---|
| `agent/evaluator.py` | Add `task_id: str` to `EvalInput`; write to eval_log |
| `agent/pipeline.py` | `run_pipeline` gets 3 injection params; `_build_static_system` gets `injected_prompt_addendum`; security gates merge; `task_id` added to `_run_evaluator_safe` kwargs |
| `agent/orchestrator.py` | `run_agent` gets 3 injection params, passes to `run_pipeline` |
| `scripts/propose_optimizations.py` | Add `validate_recommendation()`, `read_original_score()`; gate file writes on validation result; preserve `--dry-run` |

### Out of Scope

- Eval thread does not wait for validation (remains async, passive)
- `eval` does not auto-apply recommendations — propose_optimizations still requires manual run
- No change to `verified: false` default — human review gate preserved
- Parallel validation of multiple tasks: not implemented (sequential per recommendation)
