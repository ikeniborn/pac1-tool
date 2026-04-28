# Contract DSPy Optimization Design

**Date:** 2026-04-28  
**Goal:** Collect negotiated contract examples from live runs and use them to (A) optimize executor/evaluator negotiation prompts via DSPy, and (B) distill per-type default contracts from successful runs.

---

## Problem

`contract_phase.py` runs a multi-round LLM negotiation between an executor and evaluator agent. The negotiation prompts (`executor_contract.md`, `evaluator_contract.md`) are hand-written and never updated from real run data. Per-type default contracts don't exist — all task types fall back to the single `data/default_contracts/default.json`. DSPy optimization infrastructure exists for builder/evaluator/classifier but not for contracts.

---

## Architecture

Three independent components executed in order:

```
1. Data collection (online runs) → data/dspy_contract_examples.jsonl
2. Prompt optimization (A)       → data/contract_{executor,evaluator}_program.json
3. Default distillation (B)      → data/default_contracts/{task_type}.json
```

Each component is independently runnable. Components 2 and 3 both read from the same collection file.

---

## Component 1: Data Collection

### Model routing

New env variable `MODEL_CONTRACT` — routed in `contract_phase.py` instead of using the caller's model. Falls back to `MODEL_DEFAULT` if unset. CC tier models (`claude-code/*`) are still skipped via FIX-394 regardless of `MODEL_CONTRACT`.

Add to `models.json` under a `"contract"` key (same structure as existing task-type entries). Add to `.env.example`:
```
MODEL_CONTRACT=openrouter/anthropic/claude-3-5-haiku  # cheap model for negotiation
```

### Per-round transcript

`contract_phase.py` `negotiate_contract()` return type changes from:
```python
tuple[Contract, int, int]
```
to:
```python
tuple[Contract, int, int, list[ContractRound]]
```

`ContractRound` (added to `contract_models.py`):
```python
class ContractRound(BaseModel):
    round_num: int
    executor_proposal: dict   # raw ExecutorProposal dict
    evaluator_response: dict  # raw EvaluatorResponse dict
```

Default-fallback path returns `[]` for rounds (no transcript). Callers updated in `agent/__init__.py`.

### Example format

New file `data/dspy_contract_examples.jsonl`. Each line:
```json
{
  "task_text": "Send follow-up email to Alice about Q1 invoice",
  "task_type": "email",
  "rounds": [
    {
      "round_num": 1,
      "executor_proposal": {"plan_steps": [...], "agreed": false, ...},
      "evaluator_response": {"success_criteria": [...], "objections": [...], "agreed": false, ...}
    },
    {
      "round_num": 2,
      "executor_proposal": {"plan_steps": [...], "agreed": true, ...},
      "evaluator_response": {"success_criteria": [...], "objections": [], "agreed": true, ...}
    }
  ],
  "final_contract": {"plan_steps": [...], "success_criteria": [...], ...},
  "is_default": false,
  "rounds_taken": 2,
  "score": 1.0,
  "stall_detected": false,
  "write_scope_violations": false
}
```

Only negotiated contracts are recorded (`not is_default`). Default-fallback runs produce no example.

### Collection hook

In `main.py`, update the `CONTRACT_COLLECT_DSPY` block (currently lines 311–324) to call the new `record_contract_example()` instead of the existing stub. The `rounds_transcript` is passed through from `run_agent()` via `token_stats["contract_rounds"]`.

New function in `agent/dspy_examples.py`:
```python
def record_contract_example(
    task_text: str,
    task_type: str,
    rounds: list[dict],
    final_contract: dict,
    is_default: bool,
    rounds_taken: int,
    score: float,
    stall_detected: bool,
    write_scope_violations: bool,
) -> None: ...
```

Threshold hint (same pattern as `record_example`): print optimizer hint when count first reaches 30.

### Trainset loader

```python
def get_contract_trainset(
    min_score: float = 1.0,
    expand_rounds: bool = True,
    role: str = "executor",  # "executor" | "evaluator" | "all"
) -> list[dspy.Example]: ...
```

`role="executor"` returns examples built from executor turns (input: task + evaluator_feedback, output: executor_proposal). `role="evaluator"` returns examples from evaluator turns (input: task + executor_proposal, output: evaluator_response). Both carry the parent run's labels.

`expand_rounds=True`: each round in each negotiation becomes a separate training example — executor examples from executor turns, evaluator examples from evaluator turns. This multiplies 43 tasks × ~2 rounds into ~86+ examples. Each example carries the final `score`, `stall_detected`, `write_scope_violations`, `rounds_taken` from the parent run as the label.

---

## Component 2: Prompt Optimization (Goal A)

### DSPy Signatures

New file `agent/optimization/contract_modules.py`:

```python
class ExecutorPropose(dspy.Signature):
    """Plan execution steps for a personal knowledge vault task.
    Propose concrete tool calls and paths. Be specific."""
    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    evaluator_feedback: str = dspy.InputField(
        desc="Evaluator's previous response (empty on round 1)", default=""
    )
    plan_steps: list[str] = dspy.OutputField(desc="2-7 concrete steps: tool + path")
    expected_outcome: str = dspy.OutputField(desc="One sentence: what success looks like")
    required_tools: list[str] = dspy.OutputField(desc="Tools from [list,read,write,delete,find,search,move,mkdir]")
    open_questions: list[str] = dspy.OutputField(desc="Genuine ambiguities; [] if clear")
    agreed: bool = dspy.OutputField(desc="True only after evaluator agrees with no objections")


class EvaluatorReview(dspy.Signature):
    """Review an executor's plan and define verifiable success criteria."""
    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    executor_proposal: str = dspy.InputField(desc="Executor's plan as JSON string")
    success_criteria: list[str] = dspy.OutputField(desc="2-5 verifiable conditions")
    failure_conditions: list[str] = dspy.OutputField(desc="Explicit failure scenarios")
    required_evidence: list[str] = dspy.OutputField(desc="Vault paths that MUST appear in grounding_refs")
    objections: list[str] = dspy.OutputField(desc="Concerns about the plan; [] if acceptable")
    agreed: bool = dspy.OutputField(desc="True when plan satisfies all criteria")
```

Both use `dspy.Predict` (not ChainOfThought) to match the structured JSON output format required by `contract_phase.py`.

### Metric

In `agent/optimization/metrics.py`, new function:

```python
MAX_CONTRACT_ROUNDS = 3  # matches CONTRACT_MAX_ROUNDS default

def contract_metric(example, pred, trace=None) -> float:
    score       = float(example.get("score", 0))
    rounds      = int(example.get("rounds_taken", MAX_CONTRACT_ROUNDS))
    stall       = bool(example.get("stall_detected", False))
    scope_viol  = bool(example.get("write_scope_violations", False))

    convergence = (MAX_CONTRACT_ROUNDS - rounds) / MAX_CONTRACT_ROUNDS

    return (
        0.70 * score
        + 0.15 * convergence
        + 0.10 * (0.0 if stall else 1.0)
        + 0.05 * (0.0 if scope_viol else 1.0)
    )
```

### Optimizer target

In `scripts/optimize_prompts.py`, add `--target contract`:
- Compiles `ExecutorPropose` using `get_contract_trainset(role="executor")`
- Compiles `EvaluatorReview` using `get_contract_trainset(role="evaluator")`
- Saves to `data/contract_executor_program.json` and `data/contract_evaluator_program.json`
- Uses COPRO (respects `OPTIMIZER_CONTRACT` env, default `copro`)

### Loading compiled programs

In `contract_phase.py`, at module load time (after existing imports):
```python
_EXECUTOR_PROGRAM_PATH = _DATA / "contract_executor_program.json"
_EVALUATOR_PROGRAM_PATH = _DATA / "contract_evaluator_program.json"
```

`negotiate_contract()`: if both program files exist, use `ExecutorPredictor.load()` / `EvaluatorPredictor.load()` to run predictions instead of raw `call_llm_raw`. Falls back to current behavior if files are missing or load fails (fail-open).

---

## Component 3: Default Contract Distillation (Goal B)

New script `scripts/distill_contracts.py`.

### Algorithm

For each `task_type` in the collected examples:

1. Filter: `score=1.0` and `not is_default`
2. If fewer than `--min-examples` (default 10) examples — skip (leave `default.json` as fallback)
3. Normalize each field element: `text.lower().strip()`
4. Count frequency of each unique element across all examples
5. Select top-N by frequency:
   - `plan_steps`: top 6
   - `success_criteria`: top 4
   - `required_evidence`: top 3
   - `failure_conditions`: top 4
6. Write `data/default_contracts/{task_type}.json`

### CLI

```bash
uv run python scripts/distill_contracts.py                   # dry-run: print results
uv run python scripts/distill_contracts.py --apply           # write files
uv run python scripts/distill_contracts.py --min-examples 5  # lower threshold
uv run python scripts/distill_contracts.py --task-type email # single type
```

Idempotent: re-running `--apply` overwrites existing per-type files. `default.json` is never overwritten.

### Loading

`contract_phase.py::_load_default_contract(task_type)` already probes `data/default_contracts/{task_type}.json` before `default.json` — no changes needed.

---

## File Structure

| File | Change |
|------|--------|
| `agent/contract_models.py` | Add `ContractRound` |
| `agent/contract_phase.py` | Return `rounds_transcript`; `MODEL_CONTRACT` routing; load compiled programs |
| `agent/dspy_examples.py` | `record_contract_example()`, `get_contract_trainset()` |
| `agent/optimization/contract_modules.py` | `ExecutorPropose`, `EvaluatorReview` (new file) |
| `agent/optimization/metrics.py` | `contract_metric()` |
| `agent/__init__.py` | Pass `rounds_transcript` through `token_stats` |
| `main.py` | Update `CONTRACT_COLLECT_DSPY` block |
| `models.json` | `"contract"` routing entry |
| `scripts/optimize_prompts.py` | `--target contract` |
| `scripts/distill_contracts.py` | New script |
| `.env.example` | `MODEL_CONTRACT` |

---

## Environment Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `MODEL_CONTRACT` | (inherits `MODEL_DEFAULT`) | Model for contract negotiation |
| `CONTRACT_ENABLED` | `0` | Enable negotiation phase |
| `CONTRACT_COLLECT_DSPY` | `0` | Save examples to jsonl |
| `CONTRACT_MAX_ROUNDS` | `3` | Max negotiation rounds |
| `OPTIMIZER_CONTRACT` | `copro` | DSPy backend for contract optimization |

---

## Success Criteria

- Running with `CONTRACT_ENABLED=1 CONTRACT_COLLECT_DSPY=1 MODEL_CONTRACT=<non-cc>` produces entries in `data/dspy_contract_examples.jsonl`
- `uv run python scripts/optimize_prompts.py --target contract` compiles and saves both program files
- `contract_phase.py` loads compiled programs at startup (logged in DEBUG)
- `uv run python scripts/distill_contracts.py --apply` with ≥10 examples per type writes per-type contract files
- All existing tests pass; new tests cover collection, metric, and distillation logic
