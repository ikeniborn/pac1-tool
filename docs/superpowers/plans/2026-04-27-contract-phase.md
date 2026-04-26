# Contract Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pre-execution contract negotiation phase where executor and evaluator agents interactively agree on a plan and success criteria before tool execution begins.

**Architecture:** A new `contract_phase.py` coordinator runs N rounds of message-passing between two LLM roles (executor proposes plan, evaluator responds with criteria/objections) using Pydantic-validated JSON. The resulting `Contract` is injected into the execution loop, used as additional hard-gates in the evaluator, and used to improve stall hints. Feature-flagged via `CONTRACT_ENABLED=0` by default.

**Tech Stack:** Python, Pydantic v2, `dispatch.call_llm_raw` (existing 3-tier LLM routing), pytest. No new dependencies.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `agent/contract_models.py` | Pydantic models: `ExecutorProposal`, `EvaluatorResponse`, `Contract` |
| Create | `agent/contract_phase.py` | Negotiation coordinator: rounds loop, LLM calls, fallback |
| Create | `data/prompts/default/executor_contract.md` | System prompt for executor in contract phase |
| Create | `data/prompts/default/evaluator_contract.md` | System prompt for evaluator in contract phase |
| Create | `data/default_contracts/default.json` | Universal fallback contract (JSON) |
| Create | `tests/test_contract_models.py` | Pydantic model validation + edge cases |
| Create | `tests/test_contract_phase.py` | Negotiation logic with mocked LLM |
| Modify | `agent/stall.py:20` | Add `contract_plan_steps` param to `_check_stall` |
| Modify | `agent/evaluator.py:387` | Add `contract` param to `evaluate_completion`, contract hard-gates |
| Modify | `agent/loop.py:2350` | Add `contract` param to `run_loop`, inject into system prompt |
| Modify | `agent/__init__.py:165` | Insert contract phase before `run_loop`, pass contract |
| Modify | `.env.example` | Add `CONTRACT_*` env vars section |
| Modify | `main.py:299` | Add `contract_rounds_taken`, `contract_is_default`, `contract_criteria_met` to dspy examples |

---

## Task 1: Pydantic Contract Models

**Files:**
- Create: `agent/contract_models.py`
- Create: `tests/test_contract_models.py`

- [ ] **Step 1: Write failing tests for contract models**

```python
# tests/test_contract_models.py
import pytest
from agent.contract_models import Contract, EvaluatorResponse, ExecutorProposal


def test_executor_proposal_defaults():
    p = ExecutorProposal(
        plan_steps=["list /", "read /file.txt"],
        expected_outcome="file updated",
        required_tools=["list", "read", "write"],
        open_questions=[],
        agreed=False,
    )
    assert p.plan_steps == ["list /", "read /file.txt"]
    assert p.agreed is False


def test_executor_proposal_requires_plan_steps():
    with pytest.raises(Exception):
        ExecutorProposal(
            plan_steps=[],  # empty is valid; missing field raises
            expected_outcome="",
            required_tools=[],
            open_questions=[],
            agreed=False,
        )
        ExecutorProposal()  # type: ignore — missing required fields


def test_evaluator_response_counter_proposal_optional():
    r = EvaluatorResponse(
        success_criteria=["file written"],
        failure_conditions=["no file written"],
        required_evidence=["/outbox/1.json"],
        objections=[],
        counter_proposal=None,
        agreed=True,
    )
    assert r.counter_proposal is None
    assert r.agreed is True


def test_contract_is_default_flag():
    c = Contract(
        plan_steps=["step 1"],
        success_criteria=["criterion 1"],
        required_evidence=[],
        failure_conditions=[],
        is_default=True,
        rounds_taken=0,
    )
    assert c.is_default is True


def test_contract_from_negotiation():
    proposal = ExecutorProposal(
        plan_steps=["list /outbox", "write /outbox/1.json"],
        expected_outcome="email written",
        required_tools=["list", "write"],
        open_questions=[],
        agreed=True,
    )
    response = EvaluatorResponse(
        success_criteria=["file /outbox/1.json exists", "contains 'to' field"],
        failure_conditions=["file not written"],
        required_evidence=["/outbox/1.json"],
        objections=[],
        counter_proposal=None,
        agreed=True,
    )
    c = Contract(
        plan_steps=proposal.plan_steps,
        success_criteria=response.success_criteria,
        required_evidence=response.required_evidence,
        failure_conditions=response.failure_conditions,
        is_default=False,
        rounds_taken=1,
    )
    assert c.rounds_taken == 1
    assert "/outbox/1.json" in c.required_evidence
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_contract_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.contract_models'`

- [ ] **Step 3: Create `agent/contract_models.py`**

```python
# agent/contract_models.py
from __future__ import annotations
from pydantic import BaseModel


class ExecutorProposal(BaseModel):
    plan_steps: list[str]
    expected_outcome: str
    required_tools: list[str]
    open_questions: list[str]
    agreed: bool


class EvaluatorResponse(BaseModel):
    success_criteria: list[str]
    failure_conditions: list[str]
    required_evidence: list[str]
    objections: list[str]
    counter_proposal: str | None
    agreed: bool


class Contract(BaseModel):
    plan_steps: list[str]
    success_criteria: list[str]
    required_evidence: list[str]
    failure_conditions: list[str]
    is_default: bool
    rounds_taken: int
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_contract_models.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/contract_models.py tests/test_contract_models.py
git commit -m "feat(contract): Pydantic models ExecutorProposal, EvaluatorResponse, Contract"
```

---

## Task 2: Default Prompts and Fallback Contract

**Files:**
- Create: `data/prompts/default/executor_contract.md`
- Create: `data/prompts/default/evaluator_contract.md`
- Create: `data/default_contracts/default.json`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p data/prompts/default data/default_contracts
```

- [ ] **Step 2: Create `data/prompts/default/executor_contract.md`**

```markdown
You are an executor agent for a personal knowledge vault.
You are in the CONTRACT NEGOTIATION phase — no tools have been called yet.

Your role: read the task and propose a concrete execution plan.

Output ONLY valid JSON. No preamble, no explanation:
{
  "plan_steps": ["step 1 (tool + path)", "step 2", ...],
  "expected_outcome": "what success looks like in one sentence",
  "required_tools": ["list", "read", "write"],
  "open_questions": ["question if task is ambiguous, else empty list"],
  "agreed": false
}

Rules:
- plan_steps: 2–7 concrete steps naming the tool and target path
- required_tools: only tools from [list, read, write, delete, find, search, move, mkdir]
- open_questions: list genuine ambiguities only; [] if task is clear
- agreed: set true only after evaluator responds with agreed=true and no objections

When you receive the evaluator response, update your plan to address objections and criteria.
If evaluator sets agreed=true with empty objections, you MUST also set agreed=true.
```

- [ ] **Step 3: Create `data/prompts/default/evaluator_contract.md`**

```markdown
You are an evaluator agent for a personal knowledge vault.
You are in the CONTRACT NEGOTIATION phase — no tools have been called yet.

Your role: review the executor's plan and define verifiable success criteria.

Output ONLY valid JSON. No preamble, no explanation:
{
  "success_criteria": ["criterion 1 (verifiable)", "criterion 2", ...],
  "failure_conditions": ["failure scenario 1", ...],
  "required_evidence": ["/vault/path/that/must/appear/in/grounding_refs"],
  "objections": ["concern about plan if any, else empty list"],
  "counter_proposal": null,
  "agreed": false
}

Rules:
- success_criteria: 2–5 concrete, verifiable conditions (what must be true after execution)
- failure_conditions: explicit failure scenarios (what would make this a failed task)
- required_evidence: vault paths or IDs that MUST appear in grounding_refs
- objections: list concerns about the executor's plan; [] if plan looks correct
- counter_proposal: suggest a different approach if the plan is wrong; null if acceptable
- agreed: set true when executor's plan_steps satisfy all criteria with empty objections

Be precise but practical. The goal is shared understanding, not a perfect specification.
If the executor plan is reasonable and complete, agree immediately (agreed=true, objections=[]).
```

- [ ] **Step 4: Create `data/default_contracts/default.json`**

```json
{
  "plan_steps": [
    "discover vault structure via tree or list",
    "read relevant files to understand content",
    "execute the task action (write/delete/move as needed)",
    "verify the action completed and call report_completion"
  ],
  "success_criteria": [
    "task outcome matches the request",
    "all mutations recorded in done_operations",
    "grounding_refs contains the modified file path"
  ],
  "required_evidence": [],
  "failure_conditions": [
    "no files written for a task requiring a write",
    "wrong entity or path modified",
    "task completed without verifying the write succeeded"
  ],
  "is_default": true,
  "rounds_taken": 0
}
```

- [ ] **Step 5: Commit**

```bash
git add data/prompts/default/executor_contract.md data/prompts/default/evaluator_contract.md data/default_contracts/default.json
git commit -m "feat(contract): default prompts and fallback contract JSON"
```

---

## Task 3: Contract Phase Coordinator

**Files:**
- Create: `agent/contract_phase.py`
- Create: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_contract_phase.py
import json
from unittest.mock import patch

from agent.contract_models import Contract


def _make_executor_json(agreed=False, steps=None):
    return json.dumps({
        "plan_steps": steps or ["list /", "write /out/1.json"],
        "expected_outcome": "file written",
        "required_tools": ["list", "write"],
        "open_questions": [],
        "agreed": agreed,
    })


def _make_evaluator_json(agreed=False, objections=None):
    return json.dumps({
        "success_criteria": ["file /out/1.json written"],
        "failure_conditions": ["no file written"],
        "required_evidence": ["/out/1.json"],
        "objections": objections or [],
        "counter_proposal": None,
        "agreed": agreed,
    })


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_on_round_1(mock_llm):
    """Both agents agree on round 1 → contract finalized, is_default=False."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok = negotiate_contract(
        task_text="Write email to bob@x.com",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    assert isinstance(contract, Contract)
    assert contract.is_default is False
    assert contract.rounds_taken == 1
    assert "/out/1.json" in contract.required_evidence


@patch("agent.contract_phase.call_llm_raw")
def test_consensus_on_round_2(mock_llm):
    """Evaluator objects on round 1, agrees on round 2 → rounds_taken=2."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),            # round 1 executor
        _make_evaluator_json(agreed=False, objections=["missing read step"]),  # round 1 evaluator
        _make_executor_json(agreed=True, steps=["list /", "read /f.json", "write /out/1.json"]),  # round 2 executor
        _make_evaluator_json(agreed=True),            # round 2 evaluator
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.rounds_taken == 2
    assert contract.is_default is False


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_max_rounds(mock_llm):
    """Never agree → falls back to default contract after max_rounds."""
    # Never agree — always return disagreement
    mock_llm.return_value = _make_executor_json(agreed=False)
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_llm_error(mock_llm):
    """LLM returns None (all tiers failed) → falls back to default contract."""
    mock_llm.return_value = None
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_fallback_on_invalid_json(mock_llm):
    """LLM returns malformed JSON → falls back to default contract."""
    mock_llm.return_value = "not json at all"
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert contract.is_default is True


@patch("agent.contract_phase.call_llm_raw")
def test_token_counting(mock_llm):
    """in_tok and out_tok are populated from LLM calls."""
    tok = {}

    def side_effect(system, user_msg, model, cfg, max_tokens=800, token_out=None, **kwargs):
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 50
        return _make_executor_json(agreed=True) if "executor" in system else _make_evaluator_json(agreed=True)

    mock_llm.side_effect = side_effect
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=3,
    )
    assert in_tok > 0
    assert out_tok > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.contract_phase'`

- [ ] **Step 3: Create `agent/contract_phase.py`**

```python
# agent/contract_phase.py
"""Pre-execution contract negotiation between executor and evaluator agents.

Two LLM roles exchange Pydantic-validated JSON messages for up to max_rounds.
When both set agreed=True, a Contract is finalized. Otherwise falls back to
data/default_contracts/{task_type}.json (then data/default_contracts/default.json).

Fail-open: any LLM error or JSON parse failure → returns default contract.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import ValidationError

from .contract_models import Contract, EvaluatorResponse, ExecutorProposal
from .dispatch import call_llm_raw

_DATA = Path(__file__).parent.parent / "data"
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


def _load_prompt(role: str, task_type: str) -> str:
    """Load domain-specific prompt, falling back to default."""
    for folder in (task_type, "default"):
        p = _DATA / "prompts" / folder / f"{role}_contract.md"
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return ""


def _load_default_contract(task_type: str) -> Contract:
    """Load fallback contract: per-type first, then universal default."""
    for name in (f"{task_type}.json", "default.json"):
        p = _DATA / "default_contracts" / name
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                data["is_default"] = True
                data.setdefault("rounds_taken", 0)
                return Contract(**data)
            except Exception:
                pass
    # Hard fallback if files missing
    return Contract(
        plan_steps=["discover vault", "execute task", "report"],
        success_criteria=["task completed"],
        required_evidence=[],
        failure_conditions=["no action taken"],
        is_default=True,
        rounds_taken=0,
    )


def negotiate_contract(
    task_text: str,
    task_type: str,
    agents_md: str,
    wiki_context: str,
    graph_context: str,
    model: str,
    cfg: dict,
    max_rounds: int = 3,
) -> tuple[Contract, int, int]:
    """Run contract negotiation. Returns (contract, total_in_tokens, total_out_tokens).

    Each round:
      1. ExecutorAgent proposes/refines plan → ExecutorProposal
      2. EvaluatorAgent responds with criteria/objections → EvaluatorResponse
      3. Both agreed=True → finalize; else continue.
    Fallback to default contract on: max_rounds exceeded, LLM error, parse error.
    """
    executor_system = _load_prompt("executor", task_type)
    evaluator_system = _load_prompt("evaluator", task_type)

    if not executor_system or not evaluator_system:
        if _LOG_LEVEL == "DEBUG":
            print("[contract] prompts missing — using default contract")
        return _load_default_contract(task_type), 0, 0

    context_block = ""
    if agents_md:
        context_block += f"\n\nAGENTS.MD:\n{agents_md[:2000]}"
    if wiki_context:
        context_block += f"\n\nWIKI CONTEXT:\n{wiki_context[:1000]}"
    if graph_context:
        context_block += f"\n\nKNOWLEDGE GRAPH:\n{graph_context[:500]}"

    total_in = total_out = 0
    last_evaluator_response = ""

    for round_num in range(1, max_rounds + 1):
        # --- Executor turn ---
        executor_user = f"TASK: {task_text}{context_block}"
        if last_evaluator_response:
            executor_user += f"\n\nEVALUATOR RESPONSE (round {round_num - 1}):\n{last_evaluator_response}"
        executor_user += "\n\nPropose your execution plan as JSON."

        executor_tok: dict = {}
        raw_executor = call_llm_raw(
            executor_system, executor_user, model, cfg,
            max_tokens=800, token_out=executor_tok,
        )
        total_in += executor_tok.get("input", 0)
        total_out += executor_tok.get("output", 0)

        if not raw_executor:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        try:
            proposal = ExecutorProposal(**json.loads(raw_executor))
        except (json.JSONDecodeError, ValidationError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out

        # --- Evaluator turn ---
        evaluator_user = (
            f"TASK: {task_text}{context_block}\n\n"
            f"EXECUTOR PROPOSAL (round {round_num}):\n{raw_executor}\n\n"
            "Review the plan and respond with your criteria as JSON."
        )

        evaluator_tok: dict = {}
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, model, cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
        total_in += evaluator_tok.get("input", 0)
        total_out += evaluator_tok.get("output", 0)

        if not raw_evaluator:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        try:
            response = EvaluatorResponse(**json.loads(raw_evaluator))
        except (json.JSONDecodeError, ValidationError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out

        last_evaluator_response = raw_evaluator

        if _LOG_LEVEL == "DEBUG":
            print(
                f"[contract] round {round_num}: executor.agreed={proposal.agreed} "
                f"evaluator.agreed={response.agreed} objections={response.objections}"
            )

        # Consensus: both agreed with no objections
        if proposal.agreed and response.agreed and not response.objections:
            contract = Contract(
                plan_steps=proposal.plan_steps,
                success_criteria=response.success_criteria,
                required_evidence=response.required_evidence,
                failure_conditions=response.failure_conditions,
                is_default=False,
                rounds_taken=round_num,
            )
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] consensus reached in {round_num} round(s)")
            return contract, total_in, total_out

    # Max rounds exceeded — fallback
    if _LOG_LEVEL == "DEBUG":
        print(f"[contract] max_rounds={max_rounds} exceeded — using default contract")
    return _load_default_contract(task_type), total_in, total_out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): contract phase coordinator with message-passing negotiation"
```

---

## Task 4: Stall Detector — Plan Adherence Hints

**Files:**
- Modify: `agent/stall.py:20-79`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_contract_models.py

def test_stall_includes_contract_plan_steps():
    """When contract_plan_steps provided, stall hint mentions the agreed plan."""
    from collections import Counter, deque
    from agent.stall import _check_stall

    fingerprints = deque(["list:/", "list:/", "list:/"])
    hint = _check_stall(
        fingerprints=fingerprints,
        steps_since_write=0,
        error_counts=Counter(),
        contract_plan_steps=["list /", "read /contacts/c01.json", "write /out/1.json"],
    )
    assert hint is not None
    assert "agreed plan" in hint.lower() or "contract" in hint.lower()


def test_stall_without_contract_plan_steps_unchanged():
    """Without contract_plan_steps, stall hint is unchanged from current behaviour."""
    from collections import Counter, deque
    from agent.stall import _check_stall

    fingerprints = deque(["list:/", "list:/", "list:/"])
    hint = _check_stall(
        fingerprints=fingerprints,
        steps_since_write=0,
        error_counts=Counter(),
        contract_plan_steps=None,
    )
    assert hint is not None
    assert "3 times in a row" in hint
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_contract_models.py::test_stall_includes_contract_plan_steps tests/test_contract_models.py::test_stall_without_contract_plan_steps_unchanged -v
```

Expected: `TypeError: _check_stall() got an unexpected keyword argument 'contract_plan_steps'`

- [ ] **Step 3: Modify `agent/stall.py` — add `contract_plan_steps` parameter**

In `agent/stall.py`, change the `_check_stall` signature at line 20 from:

```python
def _check_stall(
    fingerprints: deque,
    steps_since_write: int,
    error_counts: Counter,
    step_facts: "list[_StepFact] | None" = None,
) -> str | None:
```

to:

```python
def _check_stall(
    fingerprints: deque,
    steps_since_write: int,
    error_counts: Counter,
    step_facts: "list[_StepFact] | None" = None,
    contract_plan_steps: "list[str] | None" = None,
) -> str | None:
```

Then in the Signal 1 block (after line 43, inside the repeated-action branch), append the agreed-plan context to the hint. Change:

```python
    if len(fingerprints) >= 3 and fingerprints[-1] == fingerprints[-2] == fingerprints[-3]:
        tool_name = fingerprints[-1].split(":")[0]
        # Include recent exploration context in hint
        _recent = [f"{f.kind}({f.path})" for f in step_facts[-4:]] if step_facts else []
        _ctx = f" Recent actions: {_recent}." if _recent else ""
        return (
            f"You have called {tool_name} with the same arguments 3 times in a row without progress.{_ctx} "
            "Try a different tool, a different path, or use search/find with different terms. "
            "If the task is complete or cannot be completed, call report_completion."
        )
```

to:

```python
    if len(fingerprints) >= 3 and fingerprints[-1] == fingerprints[-2] == fingerprints[-3]:
        tool_name = fingerprints[-1].split(":")[0]
        _recent = [f"{f.kind}({f.path})" for f in step_facts[-4:]] if step_facts else []
        _ctx = f" Recent actions: {_recent}." if _recent else ""
        _plan_ctx = ""
        if contract_plan_steps:
            _plan_ctx = f" Your agreed plan was: {contract_plan_steps}."
        return (
            f"You have called {tool_name} with the same arguments 3 times in a row without progress.{_ctx}{_plan_ctx} "
            "Try a different tool, a different path, or use search/find with different terms. "
            "If the task is complete or cannot be completed, call report_completion."
        )
```

Also update `_handle_stall_retry` at line 82 to accept and forward `contract_plan_steps`. Change signature from:

```python
def _handle_stall_retry(
    job,
    log: list,
    model: str,
    max_tokens: int,
    cfg: dict,
    fingerprints: deque,
    steps_since_write: int,
    error_counts: Counter,
    step_facts: "list[_StepFact]",
    stall_active: bool,
    call_llm_fn,
) -> tuple:
```

to:

```python
def _handle_stall_retry(
    job,
    log: list,
    model: str,
    max_tokens: int,
    cfg: dict,
    fingerprints: deque,
    steps_since_write: int,
    error_counts: Counter,
    step_facts: "list[_StepFact]",
    stall_active: bool,
    call_llm_fn,
    contract_plan_steps: "list[str] | None" = None,
) -> tuple:
```

And update the internal `_check_stall` call on line 100 from:

```python
    _stall_hint = _check_stall(fingerprints, steps_since_write, error_counts, step_facts)
```

to:

```python
    _stall_hint = _check_stall(fingerprints, steps_since_write, error_counts, step_facts, contract_plan_steps)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_contract_models.py -v
```

Expected: all tests PASS (including 2 new stall tests)

- [ ] **Step 5: Commit**

```bash
git add agent/stall.py tests/test_contract_models.py
git commit -m "feat(contract): stall detector surfaces agreed plan steps in stall hints"
```

---

## Task 5: Evaluator — Contract Hard-Gates

**Files:**
- Modify: `agent/evaluator.py:387`

- [ ] **Step 1: Write failing test**

Add to `tests/test_evaluator.py`:

```python
def test_evaluate_rejects_when_contract_evidence_missing():
    """Contract required_evidence not in grounding_refs → rejected without LLM call."""
    import types
    from agent.contract_models import Contract
    from agent.evaluator import evaluate_completion

    contract = Contract(
        plan_steps=["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["no file written"],
        is_default=False,
        rounds_taken=1,
    )
    report = types.SimpleNamespace(
        outcome="OUTCOME_OK",
        message="Email sent",
        completed_steps_laconic=[],
        done_operations=[],
        grounding_refs=[],  # missing /outbox/1.json
    )
    verdict = evaluate_completion(
        task_text="Send email",
        task_type="email",
        report=report,
        done_ops=["WRITTEN: /outbox/1.json"],
        digest_str="",
        model="test",
        cfg={},
        contract=contract,
    )
    assert verdict.approved is False
    assert any("/outbox/1.json" in issue for issue in verdict.issues)


def test_evaluate_passes_when_contract_evidence_present():
    """Contract required_evidence present in grounding_refs → not blocked by this gate."""
    import json
    import types
    from agent.contract_models import Contract

    contract = Contract(
        plan_steps=["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["no file written"],
        is_default=False,
        rounds_taken=1,
    )
    report = types.SimpleNamespace(
        outcome="OUTCOME_OK",
        message="Email sent",
        completed_steps_laconic=[],
        done_operations=[],
        grounding_refs=["/outbox/1.json"],
    )

    approved_response = json.dumps({
        "reasoning": "Contract satisfied.",
        "approved_str": "yes",
        "issues_str": "",
        "correction_hint": "",
    })

    with patch("agent.dspy_lm.call_llm_raw", return_value=approved_response):
        from agent.evaluator import evaluate_completion
        verdict = evaluate_completion(
            task_text="Send email",
            task_type="email",
            report=report,
            done_ops=["WRITTEN: /outbox/1.json"],
            digest_str="",
            model="test",
            cfg={},
            contract=contract,
        )
    assert verdict.approved is True
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/test_evaluator.py::test_evaluate_rejects_when_contract_evidence_missing tests/test_evaluator.py::test_evaluate_passes_when_contract_evidence_present -v
```

Expected: `TypeError: evaluate_completion() got an unexpected keyword argument 'contract'`

- [ ] **Step 3: Modify `agent/evaluator.py` — add contract parameter and hard-gate**

Add import at the top of `agent/evaluator.py` (after line 19, with other imports):

```python
from .contract_models import Contract
```

Change the `evaluate_completion` signature at line 387 from:

```python
def evaluate_completion(
    task_text: str,
    task_type: str,
    report,
    done_ops: list[str],
    digest_str: str,
    model: str,
    cfg: dict,
    skepticism: str = "mid",
    efficiency: str = "mid",
    account_evidence: str = "",
    inbox_evidence: str = "",
    fail_closed: bool = False,
) -> EvalVerdict:
```

to:

```python
def evaluate_completion(
    task_text: str,
    task_type: str,
    report,
    done_ops: list[str],
    digest_str: str,
    model: str,
    cfg: dict,
    skepticism: str = "mid",
    efficiency: str = "mid",
    account_evidence: str = "",
    inbox_evidence: str = "",
    fail_closed: bool = False,
    contract: "Contract | None" = None,
) -> EvalVerdict:
```

After the existing `validate_grounding_refs` call (after line 420), add the contract evidence gate:

```python
    # Contract hard-gate: required_evidence must appear in grounding_refs
    if contract is not None and not contract.is_default and contract.required_evidence:
        refs = [str(r) for r in (getattr(report, "grounding_refs", None) or [])]
        refs_str = "\n".join(refs).lower()
        missing = [e for e in contract.required_evidence if e.lower() not in refs_str]
        if missing:
            _issue = (
                f"Contract required_evidence missing from grounding_refs: {missing}. "
                "Add the missing paths to grounding_refs before reporting completion."
            )
            return EvalVerdict(approved=False, issues=[_issue], correction_hint=_issue)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_evaluator.py -v --tb=short
```

Expected: all tests PASS including 2 new contract tests

- [ ] **Step 5: Commit**

```bash
git add agent/evaluator.py tests/test_evaluator.py
git commit -m "feat(contract): evaluator hard-gate on contract required_evidence"
```

---

## Task 6: Loop — Inject Contract into System Prompt

**Files:**
- Modify: `agent/loop.py:2350-2370`

- [ ] **Step 1: Write failing test**

Add to `tests/test_contract_models.py`:

```python
def test_contract_injected_into_system_prompt():
    """run_loop receives contract and appends AGREED CONTRACT section to system prompt."""
    from agent.contract_models import Contract
    # We verify the injection helper builds the correct block
    from agent.loop import _format_contract_block

    contract = Contract(
        plan_steps=["list /outbox", "write /outbox/1.json"],
        success_criteria=["file written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["no write"],
        is_default=False,
        rounds_taken=1,
    )
    block = _format_contract_block(contract)
    assert "## AGREED CONTRACT" in block
    assert "list /outbox" in block
    assert "file written" in block
    assert "/outbox/1.json" in block
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/test_contract_models.py::test_contract_injected_into_system_prompt -v
```

Expected: `ImportError: cannot import name '_format_contract_block' from 'agent.loop'`

- [ ] **Step 3: Add `_format_contract_block` to `agent/loop.py`**

Add after the imports block (after line 55 or near `_EVALUATOR_ENABLED` constants), insert:

```python
# CONTRACT PHASE integration (FIX-N)
def _format_contract_block(contract: "Contract") -> str:
    """Format a Contract into a system-prompt section."""
    lines = ["## AGREED CONTRACT"]
    lines.append("Plan steps:")
    for i, step in enumerate(contract.plan_steps, 1):
        lines.append(f"  {i}. {step}")
    lines.append("Success criteria:")
    for c in contract.success_criteria:
        lines.append(f"  - {c}")
    if contract.required_evidence:
        lines.append("Required evidence in grounding_refs:")
        for e in contract.required_evidence:
            lines.append(f"  - {e}")
    return "\n".join(lines)
```

Also add the import at the top of `loop.py` (with the other local imports):

```python
from .contract_models import Contract as _Contract
```

- [ ] **Step 4: Update `run_loop` signature to accept `contract`**

Change `run_loop` signature at line 2350 from:

```python
def run_loop(vm: PcmRuntimeClientSync, model: str, _task_text: str,
             pre: PrephaseResult, cfg: dict, task_type: str = "default",
             evaluator_model: str = "", evaluator_cfg: "dict | None" = None,
             researcher_mode: bool = False, max_steps: int | None = None,
             researcher_breakout_check=None) -> dict:
```

to:

```python
def run_loop(vm: PcmRuntimeClientSync, model: str, _task_text: str,
             pre: PrephaseResult, cfg: dict, task_type: str = "default",
             evaluator_model: str = "", evaluator_cfg: "dict | None" = None,
             researcher_mode: bool = False, max_steps: int | None = None,
             researcher_breakout_check=None,
             contract: "_Contract | None" = None) -> dict:
```

After `st.researcher_mode = bool(researcher_mode)` at line 2369, add:

```python
    # FIX-N: inject agreed contract into system prompt
    if contract is not None:
        _contract_block = _format_contract_block(contract)
        _current_system = pre.log[0]["content"] if pre.log else ""
        _new_system = _current_system + "\n\n" + _contract_block
        pre.log[0]["content"] = _new_system
        if pre.preserve_prefix:
            pre.preserve_prefix[0]["content"] = _new_system
    st.contract = contract  # for evaluator and stall detector
```

Add `contract` field to `_LoopState` (find the `_LoopState` dataclass, typically defined around line 185-210 in loop.py):

```python
    contract: "_Contract | None" = None
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_contract_models.py -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/loop.py
git commit -m "feat(contract): inject agreed contract block into execution loop system prompt"
```

---

## Task 7: Agent Orchestrator — Run Contract Phase

**Files:**
- Modify: `agent/__init__.py:165-189`

- [ ] **Step 1: Add environment variable reading at the top of `agent/__init__.py`**

After line 31 (after `_PROMPT_BUILDER_MAX_TOKENS` block), add:

```python
# FIX-N: contract negotiation phase (CONTRACT_ENABLED=1 to activate)
_CONTRACT_ENABLED = os.getenv("CONTRACT_ENABLED", "0") == "1"
try:
    _CONTRACT_MAX_ROUNDS = int(os.getenv("CONTRACT_MAX_ROUNDS", "3"))
except ValueError:
    _CONTRACT_MAX_ROUNDS = 3
```

- [ ] **Step 2: Insert contract phase call in `run_agent`**

In `agent/__init__.py`, after `final_prompt = _inject_addendum(base_prompt, addendum)` at line 181, and before `pre.log[0]["content"] = final_prompt` at line 182, insert:

```python
    contract = None
    contract_in_tok = contract_out_tok = 0
    if _CONTRACT_ENABLED:
        from .contract_phase import negotiate_contract
        contract_model = os.getenv("CONTRACT_MODEL") or router.prompt_builder or model
        contract_cfg = router._adapt_config(
            router.configs.get(contract_model, {}), "classifier"
        )
        try:
            contract, contract_in_tok, contract_out_tok = negotiate_contract(
                task_text=task_text,
                task_type=task_type,
                agents_md=pre.agents_md_content or "",
                wiki_context=_wiki_patterns if _WIKI_ENABLED else "",
                graph_context=graph_section,
                model=contract_model,
                cfg=contract_cfg,
                max_rounds=_CONTRACT_MAX_ROUNDS,
            )
        except Exception as _ce:
            print(f"[contract] negotiation failed ({_ce}) — proceeding without contract")
            contract = None
```

- [ ] **Step 3: Pass `contract` to `run_loop`**

Change the `run_loop` call at line 188 from:

```python
    stats = run_loop(vm, model, task_text, pre, cfg, task_type=task_type,
                     evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg)
```

to:

```python
    stats = run_loop(vm, model, task_text, pre, cfg, task_type=task_type,
                     evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg,
                     contract=contract)
```

- [ ] **Step 4: Add contract metrics to stats**

After `stats["graph_context"] = graph_section` (line 197), add:

```python
    stats["contract_rounds_taken"] = getattr(contract, "rounds_taken", 0) if contract else 0
    stats["contract_is_default"] = getattr(contract, "is_default", True) if contract else True
    stats["contract_in_tok"] = contract_in_tok
    stats["contract_out_tok"] = contract_out_tok
```

- [ ] **Step 5: Run tests to confirm no regressions**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/__init__.py
git commit -m "feat(contract): wire contract phase into run_agent, pass contract to run_loop"
```

---

## Task 8: Config, Metrics, and Documentation

**Files:**
- Modify: `.env.example`
- Modify: `main.py:299`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add CONTRACT vars to `.env.example`**

After the `# ─── Prompt Builder (DSPy)` section (line 55–57), add:

```bash
# ─── Contract Phase ─────────────────────────────────────────────────────────
CONTRACT_ENABLED=0                   # 1 = enable pre-execution contract negotiation
CONTRACT_MAX_ROUNDS=3                # max negotiation rounds before fallback
# CONTRACT_MODEL=                    # model for contract agents; empty → CONTRACT_MODEL_DEFAULT
CONTRACT_COLLECT_DSPY=1              # add contract metrics to dspy_examples.jsonl
```

- [ ] **Step 2: Add contract metrics to DSPy example recording in `main.py`**

In `main.py` inside the `if _DSPY_COLLECT:` block (around line 299), after the existing `_record_dspy_example` call, add:

```python
            if os.getenv("CONTRACT_COLLECT_DSPY", "1") == "1":
                _rounds = token_stats.get("contract_rounds_taken", 0)
                _is_default = token_stats.get("contract_is_default", True)
                if _rounds > 0 or not _is_default:
                    _record_dspy_example(
                        task_text=trial.instruction,
                        task_type=token_stats.get("task_type", "default"),
                        addendum=f"[contract] rounds={_rounds} is_default={_is_default}",
                        score=_score_f,
                        graph_context=token_stats.get("graph_context", ""),
                        stall_detected=bool(token_stats.get("stall_hints")),
                        write_scope_violations=bool(token_stats.get("write_scope_blocks")),
                    )
```

- [ ] **Step 3: Add CHANGELOG entry**

Open `CHANGELOG.md` and prepend under the `[Unreleased]` or latest section:

```markdown
### FIX-N: Contract Phase — pre-execution executor/evaluator negotiation

- `agent/contract_models.py`: Pydantic models `ExecutorProposal`, `EvaluatorResponse`, `Contract`
- `agent/contract_phase.py`: negotiation coordinator, N-round message-passing, fallback to `data/default_contracts/`
- `data/prompts/default/executor_contract.md`, `evaluator_contract.md`: default negotiation prompts
- `data/default_contracts/default.json`: universal fallback contract
- `agent/evaluator.py`: `contract` param + hard-gate on `contract.required_evidence`
- `agent/stall.py`: `contract_plan_steps` surfaces agreed plan in stall hints
- `agent/loop.py`: `contract` param → `## AGREED CONTRACT` injected into system prompt
- `agent/__init__.py`: contract phase wired into `run_agent`, stats collected
- Env: `CONTRACT_ENABLED` (default 0), `CONTRACT_MAX_ROUNDS` (default 3), `CONTRACT_MODEL`, `CONTRACT_COLLECT_DSPY`
```

- [ ] **Step 4: Run full test suite**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add .env.example main.py CHANGELOG.md
git commit -m "feat(contract): env config, dspy metrics collection, changelog"
```

---

## Self-Review Checklist

After writing this plan, checked against the spec:

| Spec requirement | Covered by task |
|-----------------|-----------------|
| Interactive message-passing negotiation | Task 3 (`contract_phase.py`) |
| Pydantic Structured Output | Task 1 (`contract_models.py`) |
| Domain-specific prompts (executor + evaluator) | Task 2 (file structure), Task 3 (loader) |
| Default contract fallback + DSPy optimizable | Task 2, Task 3 |
| Contract injected into execution loop | Task 6 (`_format_contract_block`, `run_loop`) |
| Contract criteria as evaluator hard-gates | Task 5 (`evaluate_completion`) |
| Stall hints surface agreed plan | Task 4 (`_check_stall`) |
| Agent orchestrator wires it all together | Task 7 (`run_agent`) |
| Env vars `CONTRACT_*` | Task 8 (`.env.example`) |
| DSPy metrics `contract_rounds_taken` etc. | Task 7 (stats), Task 8 (`main.py`) |
| Fail-open on error | Task 3 (every error path returns default) |
| `CONTRACT_ENABLED=0` default | Task 7 (feature flag) |
