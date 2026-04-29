# Contract B3: Grounding + Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three contract failure patterns: vault_tree grounding in negotiation, parse-error retry with partial fallback, failure_conditions in evaluator prompt, and rule-based contract_monitor in loop.

**Architecture:** `pre.vault_tree_text` is passed to `negotiate_contract()` and injected into both executor/evaluator context blocks. Parse errors retry up to 3x per turn; max_rounds uses last round's partial contract. `EvaluateCompletion` gains a `contract_context` field for failure_conditions. New `contract_monitor.py` fires after each mutation in `_run_step()`, injecting up to 3 warnings per task.

**Tech Stack:** Python 3.12, Pydantic v2, DSPy, pytest

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `agent/contract_phase.py` | Modify | Add `vault_tree` param, parse retry, partial fallback |
| `agent/__init__.py` | Modify | Pass `vault_tree=pre.vault_tree_text` |
| `agent/evaluator.py` | Modify | Add `contract_context` to DSPy signature + call |
| `agent/contract_monitor.py` | Create | Rule-based `check_step()` |
| `agent/loop.py` | Modify | `contract_monitor_warnings` in `_LoopState`, call `check_step` |
| `tests/test_contract_phase.py` | Modify | Tests for vault_tree, retry, partial fallback |
| `tests/test_contract_monitor.py` | Create | Tests for `check_step()` |

---

## Task 1: vault_tree grounding in contract_phase.py

**Files:**
- Modify: `agent/contract_phase.py:107` (`negotiate_contract` signature)
- Modify: `agent/__init__.py:174` (`negotiate_contract` call)
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
def test_vault_tree_injected_into_llm_prompt(mock_llm):
    """vault_tree appears in the user prompt sent to both executor and evaluator."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    negotiate_contract(
        task_text="Write email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        vault_tree="├── 00_inbox\n└── 01_capture",
        model="test-model",
        cfg={},
        max_rounds=3,
    )
    # Both calls (executor + evaluator) must contain the vault tree
    for call_args in mock_llm.call_args_list:
        user_msg = call_args[0][1]  # second positional arg is user prompt
        assert "01_capture" in user_msg, f"vault_tree missing from prompt: {user_msg[:200]}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_contract_phase.py::test_vault_tree_injected_into_llm_prompt -v
```

Expected: `FAILED` — `negotiate_contract` doesn't accept `vault_tree` yet.

- [ ] **Step 3: Add `vault_tree` parameter to `negotiate_contract`**

In `agent/contract_phase.py`, change the function signature (line 107):

```python
def negotiate_contract(
    task_text: str,
    task_type: str,
    agents_md: str,
    wiki_context: str,
    graph_context: str,
    model: str,
    cfg: dict,
    max_rounds: int = 3,
    vault_date_hint: str = "",
    vault_tree: str = "",
) -> tuple[Contract, int, int, list[dict]]:
```

Then inject it into `context_block` after `graph_context` (after line 147):

```python
    if graph_context:
        context_block += f"\n\nKNOWLEDGE GRAPH:\n{graph_context}"
    if vault_tree:
        context_block += f"\n\nVAULT STRUCTURE:\n{vault_tree}"
```

- [ ] **Step 4: Pass `vault_tree` from `agent/__init__.py`**

In `agent/__init__.py`, the `negotiate_contract()` call (around line 174). Add `vault_tree=pre.vault_tree_text`:

```python
            contract, contract_in_tok, contract_out_tok, _rounds = negotiate_contract(
                task_text=task_text,
                task_type=task_type,
                agents_md=getattr(pre, "agents_md_content", "") or "",
                wiki_context=_wiki_patterns,
                graph_context=graph_section,
                vault_date_hint=getattr(pre, "vault_date_est", "") or "",
                vault_tree=getattr(pre, "vault_tree_text", "") or "",
                model=model,
                cfg=cfg,
                max_rounds=_CONTRACT_MAX_ROUNDS,
            )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_contract_phase.py::test_vault_tree_injected_into_llm_prompt -v
```

Expected: `PASSED`

- [ ] **Step 6: Run full contract_phase test suite to confirm no regression**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: all existing tests still pass (vault_tree defaults to "").

- [ ] **Step 7: Commit**

```bash
git add agent/contract_phase.py agent/__init__.py tests/test_contract_phase.py
git commit -m "feat(contract): inject vault_tree into negotiation context"
```

---

## Task 2: Parse error retry (3x) in contract_phase.py

**Files:**
- Modify: `agent/contract_phase.py:183-219` (executor and evaluator parse blocks)
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
def test_parse_retry_succeeds_on_third_attempt(mock_llm):
    """Executor parse fails twice then succeeds — contract finalized, not default."""
    bad_executor = "not json"
    good_executor = _make_executor_json(agreed=True)
    good_evaluator = _make_evaluator_json(agreed=True)
    # Round 1: executor fails 2x, succeeds 3rd; then evaluator succeeds
    mock_llm.side_effect = [
        bad_executor, bad_executor, good_executor,
        good_evaluator,
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Should finalize after retry success"


@patch("agent.contract_phase.call_llm_raw")
def test_parse_retry_exhausted_continues_to_next_round(mock_llm):
    """Executor parse fails 3x on round 1 → skips round, tries round 2 which succeeds."""
    bad_executor = "not json"
    good_executor = _make_executor_json(agreed=True)
    good_evaluator = _make_evaluator_json(agreed=True)
    # Round 1: executor fails 3x (exhausted); Round 2: both succeed
    mock_llm.side_effect = [
        bad_executor, bad_executor, bad_executor,
        good_executor, good_evaluator,
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Round 2 should succeed after round 1 retry exhaustion"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_contract_phase.py::test_parse_retry_succeeds_on_third_attempt tests/test_contract_phase.py::test_parse_retry_exhausted_continues_to_next_round -v
```

Expected: both `FAILED` — current code returns default on first parse error.

- [ ] **Step 3: Implement parse retry in `agent/contract_phase.py`**

Replace the executor parse block (lines 183-190) and evaluator parse block (lines 212-219) with retry loops. Replace the entire `for round_num in range(...)` loop body with:

```python
    _PARSE_RETRIES = 3

    for round_num in range(1, max_rounds + 1):
        # --- Executor turn ---
        executor_user = f"TASK: {task_text}{context_block}"
        if last_evaluator_response:
            executor_user += f"\n\nEVALUATOR RESPONSE (round {round_num - 1}):\n{last_evaluator_response}"
        executor_user += "\n\nPropose your execution plan as JSON."

        executor_tok: dict = {}
        raw_executor = call_llm_raw(
            executor_system, executor_user, negotiation_model, executor_cfg,
            max_tokens=800, token_out=executor_tok,
        )
        total_in += executor_tok.get("input", 0)
        total_out += executor_tok.get("output", 0)

        if not raw_executor:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript

        # FIX-401: use multi-level JSON extractor instead of bare json.loads
        proposal = None
        for _retry in range(_PARSE_RETRIES):
            extracted_executor = _extract_json_from_text(raw_executor)
            try:
                proposal = ExecutorProposal(**(extracted_executor or {}))
                break
            except (ValidationError, TypeError) as e:
                if _LOG_LEVEL == "DEBUG":
                    print(f"[contract] executor parse error round {round_num} attempt {_retry + 1}: {e}")
                if _retry < _PARSE_RETRIES - 1:
                    # Re-call LLM for a fresh response
                    _retry_tok: dict = {}
                    raw_executor = call_llm_raw(
                        executor_system, executor_user, negotiation_model, executor_cfg,
                        max_tokens=800, token_out=_retry_tok,
                    ) or raw_executor
                    total_in += _retry_tok.get("input", 0)
                    total_out += _retry_tok.get("output", 0)

        if proposal is None:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor parse exhausted round {round_num} — skipping round")
            continue  # skip to next round instead of falling back to default

        # --- Evaluator turn ---
        evaluator_user = (
            f"TASK: {task_text}{context_block}\n\n"
            f"EXECUTOR PROPOSAL (round {round_num}):\n{raw_executor}\n\n"
            "Review the plan and respond with your criteria as JSON."
        )

        evaluator_tok: dict = {}
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, negotiation_model, evaluator_cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
        total_in += evaluator_tok.get("input", 0)
        total_out += evaluator_tok.get("output", 0)

        if not raw_evaluator:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript

        response = None
        for _retry in range(_PARSE_RETRIES):
            extracted_evaluator = _extract_json_from_text(raw_evaluator)
            try:
                response = EvaluatorResponse(**(extracted_evaluator or {}))
                break
            except (ValidationError, TypeError) as e:
                if _LOG_LEVEL == "DEBUG":
                    print(f"[contract] evaluator parse error round {round_num} attempt {_retry + 1}: {e}")
                if _retry < _PARSE_RETRIES - 1:
                    _retry_tok2: dict = {}
                    raw_evaluator = call_llm_raw(
                        evaluator_system, evaluator_user, negotiation_model, evaluator_cfg,
                        max_tokens=800, token_out=_retry_tok2,
                    ) or raw_evaluator
                    total_in += _retry_tok2.get("input", 0)
                    total_out += _retry_tok2.get("output", 0)

        if response is None:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator parse exhausted round {round_num} — skipping round")
            continue  # skip to next round

        rounds_transcript.append(ContractRound(
            round_num=round_num,
            executor_proposal=proposal.model_dump(),
            evaluator_response=response.model_dump(),
        ).model_dump())

        last_evaluator_response = raw_evaluator

        if _LOG_LEVEL == "DEBUG":
            print(
                f"[contract] round {round_num}: executor.agreed={proposal.agreed} "
                f"evaluator.agreed={response.agreed} objections={response.objections}"
            )

        evaluator_accepts = response.agreed and not response.objections
        full_consensus = proposal.agreed and evaluator_accepts
        if full_consensus or evaluator_accepts:
            contract = Contract(
                plan_steps=proposal.plan_steps,
                success_criteria=response.success_criteria,
                required_evidence=response.required_evidence,
                failure_conditions=response.failure_conditions,
                is_default=False,
                rounds_taken=round_num,
            )
            if _LOG_LEVEL == "DEBUG":
                mode = "full consensus" if full_consensus else "evaluator-only consensus"
                print(f"[contract] {mode} reached in {round_num} round(s)")
            return contract, total_in, total_out, rounds_transcript
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
uv run pytest tests/test_contract_phase.py::test_parse_retry_succeeds_on_third_attempt tests/test_contract_phase.py::test_parse_retry_exhausted_continues_to_next_round -v
```

Expected: both `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: all tests pass. Note: `test_fallback_on_invalid_json` now retries 3x — mock will be called 3× for executor + 0 for evaluator. Update the test assertion if needed:

```python
# test_fallback_on_invalid_json: mock called 3 times (3 executor retries), then round 2 retries, etc.
# Since max_rounds=3 and all retries fail, result is still default. No assertion change needed.
assert contract.is_default is True
```

- [ ] **Step 6: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): retry parse errors 3x before skipping round"
```

---

## Task 3: Partial fallback from rounds_transcript

**Files:**
- Modify: `agent/contract_phase.py` (final return after max_rounds loop)
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
def test_partial_fallback_from_last_round(mock_llm):
    """max_rounds exceeded but transcript non-empty → non-default contract from last round."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["not satisfied"]),
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["still not"]),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False, "Should use partial contract from last round"
    assert contract.rounds_taken == 2
    assert contract.plan_steps == ["list /", "write /out/1.json"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_contract_phase.py::test_partial_fallback_from_last_round -v
```

Expected: `FAILED` — current code returns `is_default=True`.

- [ ] **Step 3: Implement partial fallback in `agent/contract_phase.py`**

Replace the final `return _load_default_contract(...)` line at the end of `negotiate_contract` (after the `for` loop) with:

```python
    # Max rounds exceeded — use partial contract from last round if available
    if _LOG_LEVEL == "DEBUG":
        print(f"[contract] max_rounds={max_rounds} exceeded — "
              f"{'using partial from last round' if rounds_transcript else 'using default contract'}")
    if rounds_transcript:
        last = rounds_transcript[-1]
        ep = last["executor_proposal"]
        er = last["evaluator_response"]
        return Contract(
            plan_steps=ep.get("plan_steps", []),
            success_criteria=er.get("success_criteria", []),
            required_evidence=er.get("required_evidence", []),
            failure_conditions=er.get("failure_conditions", []),
            is_default=False,
            rounds_taken=max_rounds,
        ), total_in, total_out, rounds_transcript
    return _load_default_contract(task_type), total_in, total_out, rounds_transcript
```

- [ ] **Step 4: Update the existing `test_fallback_on_max_rounds` test**

The existing test asserts `is_default is True` — now it should be `False` since the transcript is non-empty. Update:

```python
def test_fallback_on_max_rounds(mock_llm):
    """Never agree → uses partial contract from last round (non-default)."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["not satisfied"]),
        _make_executor_json(agreed=False),
        _make_evaluator_json(agreed=False, objections=["still not satisfied"]),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _rounds = negotiate_contract(
        task_text="task", task_type="default", agents_md="", wiki_context="",
        graph_context="", model="m", cfg={}, max_rounds=2,
    )
    assert contract.is_default is False  # partial fallback, not generic default
    assert contract.rounds_taken == 2
    assert mock_llm.call_count == 4  # both rounds fully executed
```

- [ ] **Step 5: Run all contract_phase tests**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: all pass including updated `test_fallback_on_max_rounds`.

- [ ] **Step 6: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): use partial contract from last round on max_rounds exhaustion"
```

---

## Task 4: failure_conditions in evaluator LLM prompt

**Files:**
- Modify: `agent/evaluator.py:229-251` (EvaluateCompletion signature)
- Modify: `agent/evaluator.py:460-476` (evaluate_completion call)

- [ ] **Step 1: Write failing test**

Create `tests/test_evaluator_contract.py`:

```python
# tests/test_evaluator_contract.py
from unittest.mock import patch, MagicMock
from agent.contract_models import Contract


def _make_contract(failure_conditions=None):
    return Contract(
        plan_steps=["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=failure_conditions or ["unauthorized write detected"],
        is_default=False,
        rounds_taken=1,
    )


def _make_report(outcome="OUTCOME_OK", grounding_refs=None):
    report = MagicMock()
    report.outcome = outcome
    report.message = "done"
    report.grounding_refs = grounding_refs or ["/outbox/1.json"]
    report.done_operations = []
    report.completed_steps_laconic = []
    return report


@patch("agent.evaluator.dspy")
def test_contract_context_passed_to_predictor(mock_dspy):
    """failure_conditions from contract appear in the predictor call."""
    mock_predictor = MagicMock()
    mock_dspy.ChainOfThought.return_value = mock_predictor
    mock_dspy.context.return_value.__enter__ = lambda s: s
    mock_dspy.context.return_value.__exit__ = MagicMock(return_value=False)
    mock_dspy.JSONAdapter.return_value = MagicMock()
    result = MagicMock()
    result.approved_str = "yes"
    result.issues_str = ""
    result.correction_hint = ""
    mock_predictor.return_value = result

    from agent.evaluator import evaluate_completion
    contract = _make_contract(failure_conditions=["do not write to /secrets/"])
    evaluate_completion(
        task_text="write email",
        task_type="email",
        report=_make_report(),
        done_ops=["/outbox/1.json"],
        digest_str="",
        model="test-model",
        cfg={},
        contract=contract,
    )
    # The predictor must have been called with contract_context containing the failure condition
    call_kwargs = mock_predictor.call_args[1]
    assert "contract_context" in call_kwargs
    assert "do not write to /secrets/" in call_kwargs["contract_context"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_evaluator_contract.py::test_contract_context_passed_to_predictor -v
```

Expected: `FAILED` — `predictor` call doesn't include `contract_context`.

- [ ] **Step 3: Add `contract_context` InputField to `EvaluateCompletion`**

In `agent/evaluator.py`, add to the `EvaluateCompletion` class after line 243 (`graph_insights` field):

```python
    contract_context: str = dspy.InputField(
        desc="Pre-agreed failure_conditions from contract negotiation. '(none)' if no contract."
    )
```

Also add a sentence to the docstring (after the `graph_insights` paragraph):

```
    - `contract_context` contains failure_conditions from the pre-agreed executor/evaluator
      contract. If any failure condition is triggered by done_ops or agent_message, reject.
```

- [ ] **Step 4: Build `contract_context` and pass it to `predictor()` in `evaluate_completion()`**

In `agent/evaluator.py`, after the `graph_insights` line (~line 461), add:

```python
    _contract_ctx = "(none)"
    if contract is not None and not contract.is_default and contract.failure_conditions:
        _contract_ctx = "\n".join(f"- {fc}" for fc in contract.failure_conditions)
```

Then in the `predictor(...)` call (around line 466), add `contract_context=_contract_ctx`:

```python
            result = predictor(
                task_text=task_text,
                task_type=task_type,
                proposed_outcome=report.outcome,
                agent_message=report.message,
                done_ops=ops_str,
                completed_steps=steps_str or "(none)",
                skepticism_level=skepticism,
                reference_patterns=ref_patterns,
                graph_insights=graph_insights,
                contract_context=_contract_ctx,
            )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_evaluator_contract.py -v
```

Expected: `PASSED`

- [ ] **Step 6: Run broader evaluator tests to confirm no regression**

```bash
uv run pytest tests/ -k "evaluator or contract" -v
```

Expected: all pass. Note: compiled evaluator DSPy programs load with try/except fail-open — the new field won't break existing compiled programs.

- [ ] **Step 7: Commit**

```bash
git add agent/evaluator.py tests/test_evaluator_contract.py
git commit -m "feat(evaluator): inject contract failure_conditions into LLM compliance check"
```

---

## Task 5: contract_monitor.py — new file

**Files:**
- Create: `agent/contract_monitor.py`
- Create: `tests/test_contract_monitor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_contract_monitor.py`:

```python
# tests/test_contract_monitor.py
from agent.contract_models import Contract


def _make_contract(plan_steps=None):
    return Contract(
        plan_steps=plan_steps or ["write /outbox/1.json", "read /contacts/"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=["unauthorized delete"],
        is_default=False,
        rounds_taken=1,
    )


def test_no_warning_when_done_ops_empty():
    from agent.contract_monitor import check_step
    contract = _make_contract()
    assert check_step(contract, [], step_num=5) is None


def test_no_warning_on_expected_write():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["write to /outbox/"])
    result = check_step(contract, ["WRITTEN: /outbox/1.json"], step_num=5)
    assert result is None


def test_warning_on_unexpected_write_at_step_gte_3():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["read /contacts/", "write /outbox/"])
    # Writing to /secrets/ not mentioned in plan
    result = check_step(contract, ["WRITTEN: /secrets/key.txt"], step_num=4)
    assert result is not None
    assert "secrets" in result.lower()


def test_no_warning_on_unexpected_write_before_step_3():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["read /contacts/"])
    # Writing before step 3 — grace period, no warning
    result = check_step(contract, ["WRITTEN: /outbox/1.json"], step_num=2)
    assert result is None


def test_warning_on_unexpected_delete():
    from agent.contract_monitor import check_step
    # Plan says write only; delete to /important/ is unexpected
    contract = _make_contract(plan_steps=["write /outbox/1.json"])
    result = check_step(contract, ["DELETED: /important/file.md"], step_num=1)
    assert result is not None
    assert "important" in result.lower()


def test_no_warning_on_expected_delete():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["delete /01_capture/ contents", "write /outbox/"])
    result = check_step(contract, ["DELETED: /01_capture/note.md"], step_num=3)
    assert result is None


def test_only_last_op_checked():
    from agent.contract_monitor import check_step
    contract = _make_contract(plan_steps=["write /outbox/"])
    # Last op is expected, prior ops don't matter
    result = check_step(
        contract,
        ["DELETED: /bad/file.md", "WRITTEN: /outbox/1.json"],
        step_num=5,
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_contract_monitor.py -v
```

Expected: `ERROR` — `agent.contract_monitor` module does not exist.

- [ ] **Step 3: Create `agent/contract_monitor.py`**

```python
# agent/contract_monitor.py
"""Rule-based contract compliance monitor for the agent loop.

check_step() fires after each mutation (WRITTEN/DELETED) in _run_step().
Returns a warning string if the operation is unexpected per the contract,
or None if everything looks fine.

No LLM calls — purely structural path matching against contract.plan_steps.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from .contract_models import Contract


def check_step(
    contract: Contract,
    done_operations: list[str],
    step_num: int,
) -> str | None:
    """Check the most recent operation against the contract plan.

    Returns a warning string if unexpected, None otherwise.
    Only the last entry in done_operations is checked (the current step's op).
    """
    if not done_operations:
        return None

    last_op = done_operations[-1]
    plan_text = " ".join(contract.plan_steps).lower()

    if last_op.startswith("DELETED:"):
        path = last_op[len("DELETED:"):].strip()
        parent = str(PurePosixPath(path).parent).strip("/")
        name = PurePosixPath(path).name
        if (path.lower() not in plan_text
                and parent.lower() not in plan_text
                and name.lower() not in plan_text):
            return (
                f"[CONTRACT MONITOR] Unexpected delete: '{path}' not mentioned in contract plan. "
                "Verify this deletion is required before proceeding."
            )

    if step_num >= 3 and last_op.startswith("WRITTEN:"):
        path = last_op[len("WRITTEN:"):].strip()
        parent = str(PurePosixPath(path).parent).strip("/")
        if path.lower() not in plan_text and parent.lower() not in plan_text:
            return (
                f"[CONTRACT MONITOR] Unexpected write to '{path}': "
                f"parent directory '{parent}' not mentioned in contract plan. "
                "Verify this is the correct target."
            )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_contract_monitor.py -v
```

Expected: all `PASSED`

- [ ] **Step 5: Commit**

```bash
git add agent/contract_monitor.py tests/test_contract_monitor.py
git commit -m "feat(contract): add rule-based contract_monitor with check_step()"
```

---

## Task 6: Integrate contract_monitor into loop.py

**Files:**
- Modify: `agent/loop.py:220` (`_LoopState` — add `contract_monitor_warnings`)
- Modify: `agent/loop.py:2278-2286` (mutation branch — call `check_step`)
- Modify: `agent/loop.py:2363-2365` (log append — inject warning into result)

- [ ] **Step 1: Add `contract_monitor_warnings` to `_LoopState`**

In `agent/loop.py`, after line 220 (`contract: "Any" = None`):

```python
    contract: "Any" = None  # FIX-392
    contract_monitor_warnings: int = 0  # cap: 3 per task
```

- [ ] **Step 2: Import `check_step` at the top of `loop.py`**

Find the block of local imports near the top of `loop.py`. Add:

```python
from .contract_monitor import check_step as _contract_check_step
```

- [ ] **Step 3: Call `check_step` after `_record_done_op` in the mutation branch**

In `agent/loop.py`, the mutation branch (around line 2278). After `_record_done_op` and `successful_writes` append, add the monitor call. Define `_cm_warning = None` before the `try` block of `_run_step` and set it inside the mutation branch:

Find the line:
```python
            st.ledger_msg = _record_done_op(job, txt, st.done_ops, st.ledger_msg, st.preserve_prefix)
            # Preserve full content of successful writes for hard-gate checks
            if isinstance(job.function, Req_Write) and job.function.content:
                st.successful_writes.append((job.function.path, job.function.content))
```

Add after the `successful_writes` append:

```python
            # Contract monitor: check last op against plan, cap 3 warnings per task
            if (st.contract is not None and not st.contract.is_default
                    and st.contract_monitor_warnings < 3):
                _cm_warning = _contract_check_step(
                    st.contract, st.done_ops, st.step_count
                )
                if _cm_warning:
                    st.contract_monitor_warnings += 1
```

Also define `_cm_warning = None` at the start of `_run_step` (before the `try` block), so it's in scope at the log append step below.

- [ ] **Step 4: Inject warning into tool result message**

Find the log append line (around line 2364-2365):

```python
    _history_txt = _compact_tool_result(action_name, txt)
    st.log.append({"role": "user", "content": f"Result of {action_name}: {_history_txt}"})
```

Replace with:

```python
    _history_txt = _compact_tool_result(action_name, txt)
    _content = f"Result of {action_name}: {_history_txt}"
    if _cm_warning:
        _content += f"\n{_cm_warning}"
    st.log.append({"role": "user", "content": _content})
```

- [ ] **Step 5: Run full test suite**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all tests pass. Any `_cm_warning` not-defined errors mean `_cm_warning = None` initialization was missed — add it at the top of `_run_step`.

- [ ] **Step 6: Commit**

```bash
git add agent/loop.py
git commit -m "feat(loop): call contract_monitor after each mutation, inject up to 3 warnings"
```

---

## Task 7: Final integration verification

- [ ] **Step 1: Run complete test suite**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all tests pass, no regressions.

- [ ] **Step 2: Smoke-test contract negotiation with vault_tree**

```bash
LOG_LEVEL=DEBUG uv run python -c "
from agent.contract_phase import negotiate_contract
from unittest.mock import patch
import json

executor_json = json.dumps({'plan_steps': ['write /outbox/1.json'], 'expected_outcome': 'done', 'required_tools': ['write'], 'open_questions': [], 'agreed': True})
evaluator_json = json.dumps({'success_criteria': ['written'], 'failure_conditions': ['no write'], 'required_evidence': ['/outbox/1.json'], 'objections': [], 'counter_proposal': None, 'agreed': True})

with patch('agent.contract_phase.call_llm_raw', side_effect=[executor_json, evaluator_json]):
    c, _, _, _ = negotiate_contract(
        task_text='test', task_type='email',
        agents_md='', wiki_context='', graph_context='',
        vault_tree='├── outbox\n└── contacts',
        model='test', cfg={},
    )
    print('is_default:', c.is_default)
    print('plan_steps:', c.plan_steps)
" 2>&1
```

Expected output includes `is_default: False` and `plan_steps: ['write /outbox/1.json']`.

- [ ] **Step 3: Verify contract_monitor fires on unexpected write**

```bash
uv run python -c "
from agent.contract_monitor import check_step
from agent.contract_models import Contract
c = Contract(plan_steps=['write /outbox/'], success_criteria=[], required_evidence=[], failure_conditions=[], is_default=False, rounds_taken=1)
w = check_step(c, ['WRITTEN: /secrets/key.txt'], step_num=5)
print('warning:', w)
w2 = check_step(c, ['WRITTEN: /outbox/1.json'], step_num=5)
print('no warning:', w2)
"
```

Expected: first call prints a non-None warning, second prints `None`.

- [ ] **Step 4: Final commit (if any cleanup needed)**

```bash
git add -p  # review any uncommitted changes
git commit -m "chore(contract): final cleanup and integration verification"
```
