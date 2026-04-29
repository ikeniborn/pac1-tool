# Contract B3: Grounding + Enforcement Design

**Date:** 2026-04-29  
**Status:** Approved  
**Context:** Analysis of 43 tasks from run `20260429_071815_minimax-m2.7-cloud` (65% win rate, 15 failures).

---

## Problem

Three distinct failure patterns were identified in contract negotiation:

1. **False consensus (t01, t20):** Both sides agreed on a plan that was factually wrong — executor proposed "delete all contents" without knowing which specific files exist. Contract negotiated before seeing real vault structure.
2. **Execution gap (t11, t18, t37):** Contract was correct, both agreed, but agent deviated during execution. Evaluator catches this only after `report_completion` — too late to course-correct.
3. **Default degradation (t09, t40, t30):** Parse errors and max-rounds exhaustion fall back to a hardcoded generic default contract that lacks task-specific logic (e.g., security detection for injection tasks).

**Win rates by consensus type (43 tasks):**
- Full consensus: 61% (11/18)
- Evaluator-only consensus: 58% (7/12)
- Default contract: 42% (3/7)

The 3% gap between full and evaluator-only consensus is statistically insignificant — executor self-agreement does not predict success. The contract's content quality and enforcement matter more than consensus type.

---

## Approach: B3 — Grounding + Reliability + Active Monitoring

### Architecture

| File | Change |
|---|---|
| `agent/__init__.py` | Pass `pre.vault_tree_text` to `negotiate_contract` |
| `agent/contract_phase.py` | Add `vault_tree` param, parse-error retry (3x), partial fallback from `rounds_transcript[-1]` |
| `agent/evaluator.py` | Accept `contract: Contract | None`, add compliance section to evaluator prompt |
| `agent/loop.py` | Call `contract_monitor()` after each step, pass `contract` to `evaluate_completion()` |
| `agent/contract_monitor.py` | **New file** — rule-based monitor, no LLM calls |

Data flow:  
`pre.vault_tree_text` → `negotiate_contract` → `Contract` → `run_loop` → per-step: `contract_monitor()` → pre-final: `evaluate_completion(contract=...)`

---

## Section 1: Grounding (vault_tree in negotiation)

**Root cause of false consensus:** `negotiate_contract` receives `agents_md`, `wiki_context`, `graph_context` but not the actual vault file tree. Both agents negotiate over abstract folder names.

**Fix in `contract_phase.py`:**
- Add `vault_tree: str = ""` parameter
- Append to `context_block` alongside `agents_md`:
  ```
  VAULT STRUCTURE:
  {vault_tree}
  ```
- Both executor and evaluator receive the same vault context block

**Fix in `agent/__init__.py`:**
- Single line addition: `vault_tree=pre.vault_tree_text` in the `negotiate_contract()` call

**Expected effect:** Executor proposes specific paths (`/01_capture/influential/2026-02-15__openai-harness.md` rather than "all contents of 01_capture/"). Evaluator validates scope against real structure.

---

## Section 2: Reliability (retry + partial fallback)

**Root cause of default degradation:** Any parse error or max-rounds condition immediately falls back to a hardcoded generic default. The default contract for `capture` lacks injection detection; the default for `lookup` lacks entity-resolution steps.

**Parse error retry in `contract_phase.py`:**
- Current: parse error → `return _load_default_contract()`
- New: up to 3 retries per round with the same prompt before giving up
- Retry counter is independent for executor and evaluator turns
- After 3 failed attempts on a turn: skip that round, continue to next (not immediate default)

**Partial fallback from `rounds_transcript`:**
- Current: max rounds exceeded → `_load_default_contract()`
- New: if `rounds_transcript` is non-empty, build `Contract` from last round:
  - `plan_steps` ← `executor_proposal["plan_steps"]`
  - `success_criteria` ← `evaluator_response["success_criteria"]`
  - `required_evidence` ← `evaluator_response["required_evidence"]`
  - `failure_conditions` ← `evaluator_response["failure_conditions"]`
  - `is_default=False`, `rounds_taken=max_rounds`
- `_load_default_contract()` called only when `rounds_transcript` is empty

**Expected effect:** t30 (lookup, 5 rounds exhausted) would receive a task-specific partial contract instead of the generic default.

---

## Section 3: Compliance Check in Evaluator

**Root cause of execution gap (evaluator side):** `evaluate_completion()` checks general task quality but does not know the pre-agreed contract terms. `required_evidence` and `failure_conditions` from the contract are invisible to the evaluator.

**Fix in `evaluator.py`:**
- `evaluate_completion()` accepts new parameter `contract: Contract | None = None`
- When contract is not None and not default (`contract.is_default == False`), append to evaluator prompt:
  ```
  CONTRACT COMPLIANCE:
  Required evidence: {contract.required_evidence}
  Failure conditions: {contract.failure_conditions}
  Verify: are required_evidence items present in grounding_refs?
  Are any failure_conditions triggered by the agent's actions?
  ```
- Evaluator can reject completion with a specific contract violation reason

**Fix in `loop.py`:**
- Pass `contract=contract` to `evaluate_completion()` call

**Limitation:** Evaluator runs only after `report_completion` — catches deviations but cannot prevent them mid-run. This is why Section 4 (contract_monitor) is needed.

---

## Section 4: contract_monitor in loop (Active Monitoring)

**Root cause of execution gap (runtime side):** Agent receives the contract in the system prompt but can still take actions that violate it mid-run. By the time the evaluator rejects the completion, the agent has already written incorrect files or reported a wrong outcome.

**New file `agent/contract_monitor.py`:**

```python
def check_step(
    contract: Contract,
    done_operations: list[str],
    step_num: int,
) -> str | None:
```

Rule-based, zero LLM calls. Returns a warning string or `None`.

Two checks (both path-based, no text matching):

1. **Unexpected delete:** if `done_operations` contains `DELETED:` a path not mentioned in any `plan_steps` entry → return warning. `failure_conditions` are textual descriptions — not reliably matchable to paths, so the monitor uses structural path checks instead.
2. **Scope violation:** if `done_operations` contains `WRITTEN:` a path whose parent directory is not mentioned in any `plan_steps` entry → return warning. Only active at `step_num >= 3` to avoid false positives on early discovery steps.

**Fix in `loop.py`:**
- After each successful tool call, if `contract` is not None and `not contract.is_default`:
  ```python
  warning = check_step(contract, done_operations, step_num)
  if warning:
      # inject into next user-message turn
      next_user_content += f"\n[CONTRACT MONITOR]: {warning}"
  ```
- Cap: maximum 1 warning per step, maximum 3 warnings total per task (avoid context pollution)

**Expected effect:** In t37, writing to `/outbox/` would trigger a scope-violation warning because the contract's `plan_steps` required `OUTCOME_DENIED_SECURITY` for the detected message type — giving the agent one more chance to self-correct before `report_completion`.

---

## Success Criteria

- Vault tree injected into both executor and evaluator prompts during negotiation
- Parse errors trigger retry (up to 3x) before default fallback
- Max-rounds exhaustion produces partial contract from last round, not generic default
- `evaluate_completion()` checks `required_evidence` and `failure_conditions` from contract
- `contract_monitor()` fires after each step, injects at most 3 warnings per task
- All changes fail-open: any exception → contract behaves as before (no regression)

## Out of Scope

- Two-phase contract (pre-prephase abstract + post-prephase concrete) — user confirmed single phase after prephase is sufficient
- LLM-based mid-loop monitoring — rule-based only for contract_monitor
- Changes to DSPy optimization of contract executor/evaluator programs
