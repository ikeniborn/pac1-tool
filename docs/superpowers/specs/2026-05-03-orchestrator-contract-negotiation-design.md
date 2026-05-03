# Design: Full Orchestrator Wiring + Three-Party Contract Negotiation

**Date:** 2026-05-03  
**Status:** Approved  
**Scope:** Two parallel tracks — (1) wire all subagents through orchestrator via structured messages, (2) add Round 0 `PlannerStrategize` to contract negotiation + DSPy joint optimization.

---

## Problem Statement

Two failures from benchmark run (t42, t43 — both score 0.00) exposed two structural gaps:

1. **Narrow search scope**: agent searched only `/01_capture/influential/` instead of all capture subfolders. No mechanism existed to enforce a broader search plan before execution.
2. **Orchestrator bypasses ExecutorAgent**: `orchestrator.py` calls `run_loop` directly. All subagents (`SecurityAgent`, `StallAgent`, `StepGuardAgent`, `VerifierAgent`, `CompactionAgent`) are defined but not wired through the orchestrator. `run_loop` accepts injected agent params but ignores them entirely.

Additionally, `CONTRACT_ENABLED=0` was the default in code, meaning contract negotiation never ran despite infrastructure existing.

---

## Architecture: Target State

```
orchestrator.py  (hub)
  │
  ├─ 1. ClassifierAgent.run(TaskInput) → ClassificationResult
  │
  ├─ 2. WikiGraphAgent.read(WikiReadRequest) → WikiContext
  │
  ├─ 3. PlannerAgent.run(PlannerInput) → ExecutionPlan
  │       └─ negotiate_contract()
  │            ├─ Round 0: PlannerStrategize(vault_tree, task_type) → strategy
  │            └─ Round 1–N: ExecutorPropose ↔ EvaluatorReview → Contract
  │
  └─ 4. ExecutorAgent.run(ExecutorInput) → ExecutionResult
          ├─ SecurityAgent   — validates each tool call
          ├─ StallAgent      — detects execution stalls
          ├─ StepGuardAgent  — validates steps against Contract
          ├─ VerifierAgent   — evaluates before report_completion
          └─ CompactionAgent — compacts message log
```

All agent interactions use typed Pydantic contracts from `agent/contracts/`. No direct module imports between agents.

---

## Track 1: Orchestrator Wiring

### What changes

**`orchestrator.py`**
- Remove direct `run_loop(...)` call
- Instantiate all subagents: `SecurityAgent`, `StallAgent`, `CompactionAgent`, `StepGuardAgent`, `VerifierAgent`
- Pass them to `ExecutorAgent(security=..., stall=..., ...)` 
- Call `ExecutorAgent.run(ExecutorInput(...))` → `ExecutionResult`
- Map `ExecutionResult` fields back to the stats dict returned by `run_agent()`

**`agent/loop.py`**
- The five injected params (`_security_agent`, `_stall_agent`, `_compaction_agent`, `_step_guard_agent`, `_verifier_agent`) are currently accepted but ignored
- Wire each param: replace direct module calls with agent interface calls
  - `_check_write_scope()`, `_check_injection()` → `_security_agent.check(SecurityRequest)`
  - `_check_stall()` → `_stall_agent.check(StallRequest)`
  - `_compact_log()` → `_compaction_agent.compact(CompactionRequest)`
  - `check_step()` (contract_monitor) → `_step_guard_agent.check(StepGuardRequest)`
  - `evaluate_completion()` → `_verifier_agent.verify(CompletionRequest)`
- Behavior is identical — only the call path changes
- Existing modules (`security.py`, `stall.py`, etc.) remain untouched; agents delegate to them

### What does NOT change
- `loop.py` logic, step limits, stall thresholds, evaluator rejection cap
- All existing agent implementations (they already wrap the right modules)
- `agent/__init__.py` legacy path (kept for compatibility, still calls `run_loop` directly)

---

## Track 2: Round 0 + DSPy Joint Optimization

### New DSPy Signature: `PlannerStrategize`

Added to `agent/optimization/contract_modules.py`:

```python
class PlannerStrategize(dspy.Signature):
    """Analyze vault structure and define search strategy before execution."""
    task_text:   str       = dspy.InputField()
    task_type:   str       = dspy.InputField()
    vault_tree:  str       = dspy.InputField(desc="output of tree -L 2 /")
    agents_md:   str       = dspy.InputField(desc="AGENTS.MD content")

    search_scope:   list[str] = dspy.OutputField(desc="folders to search, ordered by priority")
    interpretation: str       = dspy.OutputField(desc="one sentence: what the task is asking")
    critical_paths: list[str] = dspy.OutputField(desc="specific paths agent must visit")
    ambiguities:    list[str] = dspy.OutputField(desc="open questions; [] if clear")
```

### Modified Signatures

`ExecutorPropose` and `EvaluatorReview` gain one new InputField each:

```python
planner_strategy: str = dspy.InputField(desc="strategy from PlannerStrategize round 0")
```

### `contract_phase.negotiate_contract()` — Round 0

Before the executor-evaluator loop:

```python
# Round 0 — planner strategy (always runs, fail-open)
strategy_obj = _planner_predictor(
    task_text=task_text, task_type=task_type,
    vault_tree=vault_tree, agents_md=agents_md,
)
strategy_text = strategy_obj.model_dump_json()  # Pydantic → JSON string passed to rounds 1–N
```

`strategy_text` is injected into both executor and evaluator user prompts for all subsequent rounds.

### New prompt templates

`data/prompts/{task_type}/planner_contract.md` — one file per task type. Priority types to create first: `temporal`, `lookup`, `queue`. Falls back to `data/prompts/default/planner_contract.md`.

### `data/default_contracts/*.json`

Add field `planner_strategy: str = ""` to the `Contract` Pydantic model and all JSON files. Populated from Round 0 output when negotiation runs; empty string when using default contract.

### DSPy Joint Optimization

New `dspy.Module`:

```python
class ContractNegotiationModule(dspy.Module):
    def __init__(self):
        self.planner   = dspy.Predict(PlannerStrategize)
        self.executor  = dspy.Predict(ExecutorPropose)
        self.evaluator = dspy.Predict(EvaluatorReview)

    def forward(self, task_text, task_type, vault_tree, agents_md,
                evaluator_feedback=""):
        strategy = self.planner(task_text=task_text, task_type=task_type,
                                vault_tree=vault_tree, agents_md=agents_md)
        proposal = self.executor(task_text=task_text, task_type=task_type,
                                 planner_strategy=str(strategy), evaluator_feedback=evaluator_feedback)
        review   = self.evaluator(task_text=task_text, task_type=task_type,
                                  planner_strategy=str(strategy),
                                  executor_proposal=str(proposal))
        return review
```

**Metric:** `contract_quality_metric(example, pred)` — returns 1.0 if downstream task score=1.0, 0.0 if score=0.0 or evaluator rejections > 1.

**Training data:** examples from `data/dspy_examples.jsonl` where `contract_rounds_taken > 0`. Requires 5–10 prогонов with `CONTRACT_ENABLED=1` to accumulate sufficient examples.

**New optimize target:**
```bash
uv run python scripts/optimize_prompts.py --target contract
```

Saves to `data/contract_negotiation_program.json`. Loaded at startup in `contract_phase.py` alongside existing programs.

---

## Files Changed

| File | Change |
|------|--------|
| `agent/orchestrator.py` | Replace `run_loop` call with `ExecutorAgent.run()` |
| `agent/loop.py` | Wire 5 injected agent params to replace direct module calls |
| `agent/optimization/contract_modules.py` | Add `PlannerStrategize`; add `planner_strategy` InputField to `ExecutorPropose` and `EvaluatorReview` |
| `agent/contract_phase.py` | Add Round 0 before negotiation loop |
| `agent/contract_models.py` | Add `planner_strategy: str = ""` to `Contract` |
| `data/prompts/*/planner_contract.md` | New (temporal, lookup, queue, default) |
| `data/default_contracts/*.json` | Add `planner_strategy: ""` field |
| `scripts/optimize_prompts.py` | Add `--target contract` |

**Not changed:** `agent/agents/executor_agent.py`, `agent/agents/*_agent.py` (already correct), all existing module files (`security.py`, `stall.py`, etc.).

---

## Rollout Order

1. **Track 1 first**: wire orchestrator → ExecutorAgent → loop.py. Run full benchmark to verify no regression.
2. **Track 2**: add Round 0 + update signatures. Run t42/t43 specifically to verify search scope fix.
3. **Accumulate data**: 5–10 runs with `CONTRACT_ENABLED=1` → collect contract examples.
4. **Optimize**: `--target contract` → compare score before/after.

---

## Success Criteria

- t42 and t43 score > 0.00 with Round 0 active (agent searches all capture subfolders)
- Full benchmark score does not regress vs baseline
- All subagent calls in loop.py go through injected interfaces (verifiable by grep: no direct `_check_write_scope`, `_check_stall`, `evaluate_completion` calls in loop.py)
- `ContractNegotiationModule` compiles and loads without error
