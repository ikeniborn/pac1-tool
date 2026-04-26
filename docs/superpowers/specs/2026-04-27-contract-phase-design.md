# Contract Phase Design

**Date:** 2026-04-27  
**Status:** Draft — approved by user  
**Scope:** Pre-execution contract negotiation between executor and evaluator agents

---

## Problem Statement

The current harness implements evaluation as a post-execution skeptic gate: the evaluator only sees results after the agent has finished running tools. There is no upfront agreement on what "success" means for a specific task. This leads to:

- Evaluator judging against generic rules, not task-specific criteria
- Agent and evaluator potentially having different interpretations of the task
- No structured basis for verifying that the agent followed its own plan

---

## Target Architecture

```
AGENT.md + task + wiki_context + graph_context
         ↓
┌─────────────────────────────────────────┐
│           CONTRACT PHASE                │
│                                         │
│  ExecutorAgent  ←──────→  EvaluatorAgent│
│  (domain-specific         (domain-      │
│   executor prompt)         specific     │
│                            eval prompt) │
│         ↕ JSON message passing          │
│    round 1 … round N (max N rounds)     │
│         ↓                               │
│  Contract  OR  default_contract fallback│
└─────────────────────────────────────────┘
         ↓
   EXECUTION LOOP (Contract injected)
         ↓
   VERIFICATION (validates vs Contract)
         ↓
   bitgn submit
```

---

## Section 1 — Contract Phase Protocol

Two agents with isolated conversation contexts exchange structured messages coordinated by `contract_phase.py`.

**Each round:**
1. ExecutorAgent proposes/refines plan → `ExecutorProposal`
2. EvaluatorAgent responds with criteria/objections → `EvaluatorResponse`
3. If both `agreed=True` → contract is finalized
4. If `rounds_taken >= MAX_CONTRACT_ROUNDS` → load default contract

The coordinator passes only the counterpart's last message to each agent — they do not share full conversation context with each other. This is a deliberate token-saving tradeoff; full history is not needed because each Pydantic message is self-contained.

---

## Section 2 — Structured Output (Pydantic)

```python
class ExecutorProposal(BaseModel):
    plan_steps: list[str]       # execution steps
    expected_outcome: str       # anticipated result
    required_tools: list[str]   # tools the executor plans to use
    open_questions: list[str]   # ambiguities needing clarification
    agreed: bool                # executor considers contract settled

class EvaluatorResponse(BaseModel):
    success_criteria: list[str]    # what must be true for success
    failure_conditions: list[str]  # explicit failure conditions
    required_evidence: list[str]   # what must appear in grounding_refs
    objections: list[str]          # objections to the current plan
    counter_proposal: str | None   # clarification or alternative if any
    agreed: bool                   # evaluator considers contract settled

class Contract(BaseModel):
    plan_steps: list[str]
    success_criteria: list[str]
    required_evidence: list[str]
    failure_conditions: list[str]
    is_default: bool            # True if fallback was used
    rounds_taken: int
```

**Consensus:** both `agreed=True` in last round → `Contract` is fixed.  
**Fallback:** `rounds_taken >= MAX_CONTRACT_ROUNDS` → load `data/default_contracts/{task_type}.json`.

---

## Section 3 — Domain-Specific Prompts

Each domain has dedicated prompts for all active roles:

```
data/
  prompts/
    {task_type}/
      executor_contract.md    # executor prompt in contract phase
      evaluator_contract.md   # evaluator prompt in contract phase
      executor_loop.md        # executor prompt in execution loop (migrated from _TASK_BLOCKS in prompt.py)
      evaluator_loop.md       # evaluator prompt in verification
  default_contracts/
    {task_type}.json          # per-domain fallback contract
    default.json              # universal fallback
```

**Classifier prompt:** single universal prompt, unchanged.

**Fallback hierarchy for prompts:**
```
{task_type}/executor_contract.md
    → default/executor_contract.md
```

**Wiki and graph** are injected into both contract-phase agents as memory of past tasks in the same domain — primary driver of round count reduction over time.

**DSPy optimizes:**
- `executor_contract` prompt — metric: `rounds_taken` ↓ + `contract_quality` ↑ (contract_quality = correlation between `contract_criteria_met` and final benchmark `score`)
- `evaluator_contract` prompt — metric: `false_approves` ↓ + `rounds_taken` ↓
- `evaluator_loop` prompt — existing metric: `approved` vs benchmark `score`
- `default_contracts` — optimized on negative scenarios

---

## Section 4 — Loop Integration and Verification

### Contract injection into execution loop

`Contract` is injected into the executor's system prompt as a dedicated section:

```
## AGREED CONTRACT
Plan steps:
  1. ...
  2. ...
Success criteria: ...
Required evidence: ...
```

The stall detector (`stall.py`) receives `contract.plan_steps` and can generate more precise hints when execution deviates from the agreed plan.

### Post-execution verification

After `ReportTaskCompletion`, the evaluator receives `done_ops`, proposed outcome, **and** `Contract`. Verification becomes structured:

```python
# New hard-gates in evaluator.py
for criterion in contract.success_criteria:
    check(criterion, done_ops)

for evidence in contract.required_evidence:
    check_in_grounding_refs(evidence)
```

### Flow to bitgn

```
loop → ReportTaskCompletion
  → contract_verification(done_ops, Contract)
      agreed? → bitgn.end_trial()
      rejected? → corrective hint → loop retry (max MAX_EVAL_REJECTIONS, existing constant)
      max retries exhausted? → OUTCOME_NONE + contract.is_default flag
```

### DSPy data collection

After `end_trial()` in `main.py`, new fields added to `dspy_examples.jsonl`:
- `contract_rounds_taken`
- `contract_is_default`
- `contract_criteria_met: list[bool]`

These feed the contract prompt optimization pipeline.

---

## Implementation Gaps vs Current State

| Gap | Current | Target |
|-----|---------|--------|
| Plan generation from AGENT.md | AGENTS.MD is read-only context | Executor generates `plan_steps` from AGENT.md + task in contract phase |
| Pre-loop contract negotiation | None | Interactive message-passing, N rounds, Pydantic-validated |
| Success criteria | Implicit in system prompt rules | Explicit `success_criteria` in `Contract`, agreed pre-loop |
| Domain-specific evaluator prompt | Single universal evaluator prompt | Per-domain `evaluator_contract.md` + `evaluator_loop.md` |
| Contract-based verification | Generic hard-gates | Hard-gates derived from `contract.success_criteria` + `required_evidence` |
| bitgn handoff | Immediate post-approval | Explicit contract-verified handoff |
| DSPy contract metrics | Not collected | `rounds_taken`, `is_default`, `criteria_met` in examples |

---

## Environment Variables (new)

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTRACT_ENABLED` | `0` | Enable contract phase |
| `CONTRACT_MAX_ROUNDS` | `3` | Max negotiation rounds before fallback |
| `CONTRACT_MODEL` | (inherits `MODEL_DEFAULT`) | Model for contract agents |
| `CONTRACT_DOMAIN_PROMPTS` | `1` | Use domain-specific prompts |
| `CONTRACT_COLLECT_DSPY` | `1` | Collect contract metrics for DSPy |
