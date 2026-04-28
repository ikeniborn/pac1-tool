# Contract DSPy Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect negotiated contract examples and use them to (A) optimize executor/evaluator negotiation prompts via DSPy, and (B) distill per-type default contracts from successful runs.

**Architecture:** Three independent components: (1) data collection — `contract_phase.py` returns per-round transcript, `main.py` writes `data/dspy_contract_examples.jsonl`; (2) prompt optimization — `scripts/optimize_prompts.py --target contract` compiles `ExecutorPropose` and `EvaluatorReview` signatures via COPRO; (3) default distillation — `scripts/distill_contracts.py` extracts frequency-ranked fields into `data/default_contracts/{task_type}.json`.

**Tech Stack:** Python 3.12, DSPy, Pydantic v2, existing `_run_target()` runner in `scripts/optimize_prompts.py`, existing `agent/optimization/` module structure.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `agent/contract_models.py` | Modify | Add `ContractRound` model |
| `agent/contract_phase.py` | Modify | 4-tuple return, MODEL_CONTRACT routing, load compiled programs |
| `agent/dspy_examples.py` | Modify | `record_contract_example()`, `get_contract_trainset()` |
| `agent/__init__.py` | Modify | Unpack 4-tuple, pass `contract_rounds` in stats |
| `main.py` | Modify | Replace stub CONTRACT_COLLECT_DSPY block |
| `agent/optimization/contract_modules.py` | Create | `ExecutorPropose`, `EvaluatorReview` signatures |
| `agent/optimization/metrics.py` | Modify | Add `contract_metric()` |
| `agent/optimization/feedback.py` | Modify | Add `build_contract_feedback()` |
| `scripts/optimize_prompts.py` | Modify | Add `optimize_contract()`, `--target contract` |
| `scripts/distill_contracts.py` | Create | Frequency-based default contract distillation |
| `.env.example` | Modify | `MODEL_CONTRACT`, `OPTIMIZER_CONTRACT` |
| `CHANGELOG.md` | Modify | Entry for this feature |
| `tests/test_contract_phase.py` | Modify | Update 3-tuple unpacking to 4-tuple |
| `tests/test_contract_dspy.py` | Create | Tests for collection, metric, trainset loader |
| `tests/test_distill_contracts.py` | Create | Tests for distillation logic |

---

## Task 1: ContractRound model + negotiate_contract 4-tuple + MODEL_CONTRACT routing

**Files:**
- Modify: `agent/contract_models.py`
- Modify: `agent/contract_phase.py`
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Write failing tests for the new 4-tuple signature**

Create `tests/test_contract_phase.py` additions (append after existing content):

```python
@patch("agent.contract_phase.call_llm_raw")
def test_negotiate_returns_rounds_transcript(mock_llm):
    """negotiate_contract returns 4-tuple with list[ContractRound]."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    result = negotiate_contract(
        task_text="Write email to bob@x.com",
        task_type="email",
        agents_md="", wiki_context="", graph_context="",
        model="test-model", cfg={}, max_rounds=3,
    )
    assert len(result) == 4
    contract, in_tok, out_tok, rounds = result
    assert len(rounds) == 1
    assert rounds[0]["round_num"] == 1
    assert "plan_steps" in rounds[0]["executor_proposal"]
    assert "success_criteria" in rounds[0]["evaluator_response"]


@patch("agent.contract_phase.call_llm_raw")
def test_default_fallback_returns_empty_rounds(mock_llm):
    """Default contract fallback returns empty rounds list."""
    from agent.contract_phase import negotiate_contract
    contract, in_tok, out_tok, rounds = negotiate_contract(
        task_text="task",
        task_type="email",
        agents_md="", wiki_context="", graph_context="",
        model="claude-code/opus",  # CC tier → default
        cfg={}, max_rounds=3,
    )
    assert rounds == []
    assert contract.is_default is True


def test_model_contract_env_used(monkeypatch, tmp_path):
    """MODEL_CONTRACT env is used instead of caller model for negotiation."""
    import agent.contract_phase as cp
    monkeypatch.setenv("MODEL_CONTRACT", "openrouter/anthropic/claude-3-5-haiku")
    # The module reads MODEL_CONTRACT at call time via os.getenv
    model_used = []

    original = cp.call_llm_raw
    def _capture(system, user, model, cfg, **kw):
        model_used.append(model)
        return original(system, user, model, cfg, **kw)

    # Just test the _effective_model() helper once implemented:
    effective = cp._effective_model("anthropic/claude-sonnet-4.6")
    assert effective == "openrouter/anthropic/claude-3-5-haiku"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run python -m pytest tests/test_contract_phase.py::test_negotiate_returns_rounds_transcript tests/test_contract_phase.py::test_default_fallback_returns_empty_rounds -v
```

Expected: FAIL — `ValueError: too many values to unpack`

- [ ] **Step 3: Add ContractRound to contract_models.py**

In `agent/contract_models.py`, append after existing imports:

```python
class ContractRound(BaseModel):
    round_num: int
    executor_proposal: dict
    evaluator_response: dict
```

- [ ] **Step 4: Update negotiate_contract to return 4-tuple with MODEL_CONTRACT routing**

In `agent/contract_phase.py`:

After the existing imports, add:

```python
import os
```

(already present — skip if so)

After `_LOG_LEVEL = ...` line, add:

```python
def _effective_model(caller_model: str) -> str:
    """Return MODEL_CONTRACT if set, else caller_model."""
    return os.environ.get("MODEL_CONTRACT") or caller_model
```

Change the function signature and all three early-return points from:
```python
) -> tuple[Contract, int, int]:
```
to:
```python
) -> tuple[Contract, int, int, list[dict]]:
```

Change the two early-return default fallbacks (missing prompts and CC tier):
```python
    if not executor_system or not evaluator_system:
        ...
        return _load_default_contract(task_type), 0, 0
```
to:
```python
    if not executor_system or not evaluator_system:
        ...
        return _load_default_contract(task_type), 0, 0, []
```

```python
    if model.startswith("claude-code/"):
        ...
        return _load_default_contract(task_type), 0, 0, []
```

After the CC-tier check, add MODEL_CONTRACT resolution:
```python
    negotiation_model = _effective_model(model)
```

Replace all `call_llm_raw(..., model, ...)` calls inside the loop with `negotiation_model` instead of `model`.

Add a `rounds_transcript: list[dict] = []` variable before the loop.

Inside the loop, after parsing both proposal and response, append:
```python
        from .contract_models import ContractRound
        rounds_transcript.append(ContractRound(
            round_num=round_num,
            executor_proposal=proposal.model_dump(),
            evaluator_response=response.model_dump(),
        ).model_dump())
```

Change the consensus return:
```python
            return contract, total_in, total_out
```
to:
```python
            return contract, total_in, total_out, rounds_transcript
```

Change all other early-return error fallbacks (LLM failure, parse error) inside the loop:
```python
            return _load_default_contract(task_type), total_in, total_out
```
to:
```python
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript
```

Change the final max-rounds fallback:
```python
    return _load_default_contract(task_type), total_in, total_out
```
to:
```python
    return _load_default_contract(task_type), total_in, total_out, rounds_transcript
```

The import of `ContractRound` should move to the top of the file alongside other model imports:
```python
from .contract_models import Contract, ContractRound, EvaluatorResponse, ExecutorProposal
```
Remove the inline `from .contract_models import ContractRound` inside the loop.

- [ ] **Step 5: Update existing tests that unpack 3-tuple**

In `tests/test_contract_phase.py`, find all lines like:
```python
contract, in_tok, out_tok = negotiate_contract(
```
Replace each with:
```python
contract, in_tok, out_tok, _rounds = negotiate_contract(
```

There are 6 test functions that call `negotiate_contract` directly — update all of them.

- [ ] **Step 6: Run all contract phase tests**

```bash
uv run python -m pytest tests/test_contract_phase.py -v
```

Expected: all tests PASS (including the 3 new ones)

- [ ] **Step 7: Commit**

```bash
git add agent/contract_models.py agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): 4-tuple negotiate_contract + ContractRound + MODEL_CONTRACT routing"
```

---

## Task 2: record_contract_example() + get_contract_trainset() in dspy_examples.py

**Files:**
- Modify: `agent/dspy_examples.py`
- Create: `tests/test_contract_dspy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_contract_dspy.py`:

```python
"""Tests for contract DSPy example collection and trainset loading."""
import json
import pytest


def _make_example(
    task_type="email",
    rounds=None,
    score=1.0,
    is_default=False,
    rounds_taken=2,
    stall_detected=False,
    write_scope_violations=False,
):
    if rounds is None:
        rounds = [
            {
                "round_num": 1,
                "executor_proposal": {"plan_steps": ["list /", "write /out/1.json"],
                                      "expected_outcome": "written", "required_tools": ["write"],
                                      "open_questions": [], "agreed": True},
                "evaluator_response": {"success_criteria": ["file written"],
                                       "failure_conditions": ["no file"], "required_evidence": ["/out/1.json"],
                                       "objections": [], "agreed": True},
            }
        ]
    return dict(
        task_text="Send email to alice",
        task_type=task_type,
        rounds=rounds,
        final_contract={"plan_steps": ["write /out/1.json"], "success_criteria": ["file written"],
                        "required_evidence": ["/out/1.json"], "failure_conditions": ["no file"],
                        "is_default": False, "rounds_taken": rounds_taken},
        is_default=is_default,
        rounds_taken=rounds_taken,
        score=score,
        stall_detected=stall_detected,
        write_scope_violations=write_scope_violations,
    )


def test_record_contract_example_writes_jsonl(tmp_path, monkeypatch):
    """record_contract_example appends one JSON line to dspy_contract_examples.jsonl."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    ex = _make_example()
    de.record_contract_example(**ex)

    lines = (tmp_path / "contract.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["task_type"] == "email"
    assert rec["rounds_taken"] == 2
    assert rec["score"] == 1.0
    assert len(rec["rounds"]) == 1


def test_record_contract_example_skips_default(tmp_path, monkeypatch):
    """is_default=True → nothing written."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    ex = _make_example(is_default=True)
    de.record_contract_example(**ex)

    assert not (tmp_path / "contract.jsonl").exists()


def test_get_contract_trainset_executor_role(tmp_path, monkeypatch):
    """role='executor' returns one dspy.Example per round with executor inputs."""
    import dspy
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    ex = _make_example()
    de.record_contract_example(**ex)

    trainset = de.get_contract_trainset(min_score=1.0, role="executor")
    assert len(trainset) == 1
    item = trainset[0]
    assert hasattr(item, "task_text")
    assert hasattr(item, "evaluator_feedback")
    assert hasattr(item, "plan_steps")
    assert item.score == 1.0


def test_get_contract_trainset_evaluator_role(tmp_path, monkeypatch):
    """role='evaluator' returns one dspy.Example per round with evaluator inputs."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    ex = _make_example()
    de.record_contract_example(**ex)

    trainset = de.get_contract_trainset(min_score=1.0, role="evaluator")
    assert len(trainset) == 1
    item = trainset[0]
    assert hasattr(item, "executor_proposal")
    assert hasattr(item, "success_criteria")


def test_get_contract_trainset_filters_low_score(tmp_path, monkeypatch):
    """Examples with score < min_score are excluded."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)

    de.record_contract_example(**_make_example(score=0.5))
    de.record_contract_example(**_make_example(score=1.0))

    trainset = de.get_contract_trainset(min_score=1.0, role="executor")
    assert len(trainset) == 1
    assert trainset[0].score == 1.0


def test_record_contract_example_threshold_hint(tmp_path, monkeypatch, capsys):
    """Prints hint when count first reaches 30."""
    import agent.dspy_examples as de
    monkeypatch.setattr(de, "_CONTRACT_EXAMPLES_PATH", tmp_path / "contract.jsonl")
    monkeypatch.setattr(de, "_DATA", tmp_path)
    monkeypatch.setattr(de, "_CONTRACT_THRESHOLD", 3)

    for _ in range(3):
        de.record_contract_example(**_make_example())

    captured = capsys.readouterr()
    assert "optimize_prompts.py --target contract" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run python -m pytest tests/test_contract_dspy.py -v
```

Expected: FAIL — `AttributeError: module 'agent.dspy_examples' has no attribute 'record_contract_example'`

- [ ] **Step 3: Implement record_contract_example and get_contract_trainset**

In `agent/dspy_examples.py`, after the existing `_EVAL_THRESHOLD` line, add:

```python
_CONTRACT_EXAMPLES_PATH = _DATA / "dspy_contract_examples.jsonl"
_CONTRACT_THRESHOLD = 30
```

At the end of the file, add:

```python
# ---------------------------------------------------------------------------
# Write — contract
# ---------------------------------------------------------------------------

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
) -> None:
    """Append one negotiated contract example to dspy_contract_examples.jsonl.

    Only negotiated contracts are recorded (is_default=False).
    Prints a hint to run the contract optimizer when count first reaches _CONTRACT_THRESHOLD.
    """
    if is_default:
        return
    _DATA.mkdir(parents=True, exist_ok=True)
    entry = {
        "task_text": task_text,
        "task_type": task_type,
        "rounds": rounds,
        "final_contract": final_contract,
        "is_default": is_default,
        "rounds_taken": rounds_taken,
        "score": score,
        "stall_detected": stall_detected,
        "write_scope_violations": write_scope_violations,
    }
    with _CONTRACT_EXAMPLES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    count = sum(1 for _ in _CONTRACT_EXAMPLES_PATH.open(encoding="utf-8"))
    if count == _CONTRACT_THRESHOLD:
        print(
            f"[dspy] {_CONTRACT_THRESHOLD} contract examples collected "
            "→ run: uv run python scripts/optimize_prompts.py --target contract"
        )


# ---------------------------------------------------------------------------
# Read — contract
# ---------------------------------------------------------------------------

def get_contract_trainset(
    min_score: float = 1.0,
    expand_rounds: bool = True,
    role: str = "executor",
) -> list:
    """Return DSPy Examples for contract optimization.

    role='executor': input=(task_text, task_type, evaluator_feedback), output=executor_proposal fields
    role='evaluator': input=(task_text, task_type, executor_proposal), output=evaluator_response fields
    expand_rounds=True: each round becomes a separate example.
    """
    import dspy

    if not _CONTRACT_EXAMPLES_PATH.exists():
        return []

    examples = []
    with _CONTRACT_EXAMPLES_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if float(rec.get("score", 0)) < min_score:
                continue
            if rec.get("is_default", True):
                continue

            labels = {
                "score": rec.get("score", 0.0),
                "rounds_taken": rec.get("rounds_taken", 3),
                "stall_detected": rec.get("stall_detected", False),
                "write_scope_violations": rec.get("write_scope_violations", False),
            }
            rounds = rec.get("rounds", []) if expand_rounds else rec.get("rounds", [])[:1]

            prev_eval_response = ""
            for rnd in rounds:
                ep = rnd.get("executor_proposal", {})
                er = rnd.get("evaluator_response", {})

                if role == "executor":
                    ex = dspy.Example(
                        task_text=rec["task_text"],
                        task_type=rec["task_type"],
                        evaluator_feedback=prev_eval_response,
                        plan_steps=ep.get("plan_steps", []),
                        expected_outcome=ep.get("expected_outcome", ""),
                        required_tools=ep.get("required_tools", []),
                        open_questions=ep.get("open_questions", []),
                        agreed=ep.get("agreed", False),
                        **labels,
                    ).with_inputs("task_text", "task_type", "evaluator_feedback")
                else:  # evaluator
                    ex = dspy.Example(
                        task_text=rec["task_text"],
                        task_type=rec["task_type"],
                        executor_proposal=json.dumps(ep),
                        success_criteria=er.get("success_criteria", []),
                        failure_conditions=er.get("failure_conditions", []),
                        required_evidence=er.get("required_evidence", []),
                        objections=er.get("objections", []),
                        agreed=er.get("agreed", False),
                        **labels,
                    ).with_inputs("task_text", "task_type", "executor_proposal")

                examples.append(ex)
                prev_eval_response = json.dumps(er)

    return examples
```

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest tests/test_contract_dspy.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/dspy_examples.py tests/test_contract_dspy.py
git commit -m "feat(contract): record_contract_example() + get_contract_trainset() in dspy_examples"
```

---

## Task 3: __init__.py unpack 4-tuple + main.py CONTRACT_COLLECT_DSPY hook

**Files:**
- Modify: `agent/__init__.py` (around line 200)
- Modify: `main.py` (lines 311–323)

- [ ] **Step 1: Update __init__.py to unpack 4-tuple and store rounds in stats**

In `agent/__init__.py`, find (around line 200):
```python
        contract, contract_in_tok, contract_out_tok = negotiate_contract(
```
Replace with:
```python
        contract, contract_in_tok, contract_out_tok, _rounds = negotiate_contract(
```

After the except block (around line 212), find:
```python
    stats["contract_rounds_taken"] = getattr(contract, "rounds_taken", 0) if contract else 0
    stats["contract_is_default"] = getattr(contract, "is_default", True) if contract else True
    stats["contract_in_tok"] = contract_in_tok
    stats["contract_out_tok"] = contract_out_tok
```
After `stats["contract_out_tok"] = ...`, add:
```python
    stats["contract_rounds"] = _rounds if contract is not None else []
```

Note: `_rounds` is defined in the `try` block above. If the `except` branch fires, `contract = None` and `_rounds` may be undefined. Guard this:

Actually, define `_rounds` before the try block:
```python
    _rounds: list[dict] = []
    if _CONTRACT_ENABLED:
        from .contract_phase import negotiate_contract
        try:
            contract, contract_in_tok, contract_out_tok, _rounds = negotiate_contract(
```

Then after the try/except, `_rounds` is always defined:
```python
    stats["contract_rounds"] = _rounds
```

- [ ] **Step 2: Replace the stub CONTRACT_COLLECT_DSPY block in main.py**

Find (lines 311–323):
```python
            if os.getenv("CONTRACT_COLLECT_DSPY", "0") == "1":
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

Replace with:
```python
            if os.getenv("CONTRACT_COLLECT_DSPY", "0") == "1":
                _contract_rounds = token_stats.get("contract_rounds", [])
                _is_default = token_stats.get("contract_is_default", True)
                if not _is_default and _contract_rounds:
                    from agent.dspy_examples import record_contract_example
                    _fc = None
                    if token_stats.get("contract_rounds_taken", 0) > 0:
                        from agent.contract_models import Contract
                        _fc_fields = {
                            "plan_steps": [],
                            "success_criteria": [],
                            "required_evidence": [],
                            "failure_conditions": [],
                            "is_default": False,
                            "rounds_taken": token_stats.get("contract_rounds_taken", 0),
                        }
                        _fc = _fc_fields
                    record_contract_example(
                        task_text=trial.instruction,
                        task_type=token_stats.get("task_type", "default"),
                        rounds=_contract_rounds,
                        final_contract=_fc or {},
                        is_default=_is_default,
                        rounds_taken=token_stats.get("contract_rounds_taken", 0),
                        score=_score_f,
                        stall_detected=bool(token_stats.get("stall_hints")),
                        write_scope_violations=bool(token_stats.get("write_scope_blocks")),
                    )
```

Wait — `final_contract` should come from the contract object itself. The contract is not directly available in `main.py`, only `token_stats`. We need to also serialize the final contract into stats in `__init__.py`. Add to `agent/__init__.py`:

```python
    stats["contract_final"] = contract.model_dump() if contract and not contract.is_default else {}
```

Then in `main.py`, use `token_stats.get("contract_final", {})` for the `final_contract` parameter.

The corrected replacement block in `main.py`:
```python
            if os.getenv("CONTRACT_COLLECT_DSPY", "0") == "1":
                _contract_rounds = token_stats.get("contract_rounds", [])
                _is_default = token_stats.get("contract_is_default", True)
                if not _is_default and _contract_rounds:
                    from agent.dspy_examples import record_contract_example
                    record_contract_example(
                        task_text=trial.instruction,
                        task_type=token_stats.get("task_type", "default"),
                        rounds=_contract_rounds,
                        final_contract=token_stats.get("contract_final", {}),
                        is_default=_is_default,
                        rounds_taken=token_stats.get("contract_rounds_taken", 0),
                        score=_score_f,
                        stall_detected=bool(token_stats.get("stall_hints")),
                        write_scope_violations=bool(token_stats.get("write_scope_blocks")),
                    )
```

- [ ] **Step 3: Run the existing test suite to catch regressions**

```bash
uv run python -m pytest tests/test_contract_phase.py tests/test_contract_dspy.py -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add agent/__init__.py main.py
git commit -m "feat(contract): wire rounds transcript through stats + update CONTRACT_COLLECT_DSPY hook"
```

---

## Task 4: contract_modules.py + contract_metric() + build_contract_feedback()

**Files:**
- Create: `agent/optimization/contract_modules.py`
- Modify: `agent/optimization/metrics.py`
- Modify: `agent/optimization/feedback.py`
- Add tests to: `tests/test_contract_dspy.py`

- [ ] **Step 1: Write failing tests for contract_metric**

Append to `tests/test_contract_dspy.py`:

```python
def test_contract_metric_perfect_score():
    """score=1.0, rounds=1, no stall, no scope violation → metric ≈ 0.933."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=1.0,
        rounds_taken=1,
        stall_detected=False,
        write_scope_violations=False,
    )
    pred = dspy.Prediction()
    result = contract_metric(example, pred)
    # 0.70*1.0 + 0.15*(2/3) + 0.10*1.0 + 0.05*1.0 = 0.70+0.10+0.10+0.05 = 0.95
    assert abs(result.score - 0.95) < 0.01


def test_contract_metric_failed_with_stall():
    """score=0.0, stall=True → metric = 0.0 + 0.0 + 0.0 + 0.05 = 0.05."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=0.0,
        rounds_taken=3,
        stall_detected=True,
        write_scope_violations=False,
    )
    pred = dspy.Prediction()
    result = contract_metric(example, pred)
    # 0.70*0 + 0.15*0 + 0.10*0 + 0.05*1 = 0.05
    assert abs(result.score - 0.05) < 0.01


def test_contract_metric_returns_prediction_with_feedback():
    """contract_metric returns dspy.Prediction with score and feedback fields."""
    import dspy
    from agent.optimization.metrics import contract_metric

    example = dspy.Example(
        score=1.0, rounds_taken=2, stall_detected=False, write_scope_violations=False,
        task_type="email",
    )
    result = contract_metric(example, dspy.Prediction())
    assert hasattr(result, "score")
    assert hasattr(result, "feedback")
    assert isinstance(result.feedback, str)
    assert len(result.feedback) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run python -m pytest tests/test_contract_dspy.py::test_contract_metric_perfect_score -v
```

Expected: FAIL — `ImportError` or `AttributeError`

- [ ] **Step 3: Create agent/optimization/contract_modules.py**

```python
"""DSPy Signatures for contract negotiation optimization."""
from __future__ import annotations

import dspy


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
    required_tools: list[str] = dspy.OutputField(
        desc="Tools from [list,read,write,delete,find,search,move,mkdir]"
    )
    open_questions: list[str] = dspy.OutputField(
        desc="Genuine ambiguities; [] if clear"
    )
    agreed: bool = dspy.OutputField(
        desc="True only after evaluator agrees with no objections"
    )


class EvaluatorReview(dspy.Signature):
    """Review an executor's plan and define verifiable success criteria."""

    task_text: str = dspy.InputField(desc="The task to execute")
    task_type: str = dspy.InputField(desc="Task category")
    executor_proposal: str = dspy.InputField(desc="Executor's plan as JSON string")
    success_criteria: list[str] = dspy.OutputField(desc="2-5 verifiable conditions")
    failure_conditions: list[str] = dspy.OutputField(
        desc="Explicit failure scenarios"
    )
    required_evidence: list[str] = dspy.OutputField(
        desc="Vault paths that MUST appear in grounding_refs"
    )
    objections: list[str] = dspy.OutputField(
        desc="Concerns about the plan; [] if acceptable"
    )
    agreed: bool = dspy.OutputField(desc="True when plan satisfies all criteria")
```

- [ ] **Step 4: Add build_contract_feedback to feedback.py**

In `agent/optimization/feedback.py`, append:

```python
def build_contract_feedback(example, prediction, score: float) -> str:
    """Return short feedback for contract_metric."""
    task_type = getattr(example, "task_type", "default")
    src_score = float(getattr(example, "score", 0.0))
    rounds = int(getattr(example, "rounds_taken", 3))
    stall = bool(getattr(example, "stall_detected", False))
    scope_bad = bool(getattr(example, "write_scope_violations", False))

    if src_score < 1.0:
        if stall:
            return (f"Contract failed (task stalled). Negotiation for {task_type} "
                    f"did not produce actionable plan steps — reduce ambiguity.")
        if scope_bad:
            hint = _TASK_TYPE_HINTS.get(task_type, _TASK_TYPE_HINTS["default"])
            return (f"Contract failed: write-scope violation for {task_type}. "
                    f"Evaluator should enforce: {hint}.")
        return (f"Contract failed for {task_type} after {rounds} round(s). "
                f"Tighten success criteria or reduce open_questions.")

    if rounds == 1:
        return f"Excellent: consensus on round 1 for {task_type} — keep concise proposals."
    if rounds == 2:
        return f"Good: consensus on round 2 for {task_type}."
    return (f"Slow convergence: {rounds} rounds needed for {task_type}. "
            f"Executor should address evaluator objections more directly.")
```

- [ ] **Step 5: Add contract_metric to metrics.py**

In `agent/optimization/metrics.py`, add import at top:
```python
from agent.optimization.feedback import (
    build_builder_feedback,
    build_evaluator_feedback,
    build_classifier_feedback,
    build_contract_feedback,
)
```

Append at the end:
```python
MAX_CONTRACT_ROUNDS = 3


def contract_metric(example: dspy.Example, prediction, trace=None) -> dspy.Prediction:
    """Score a contract negotiation round.

    Weighted: 70% task success, 15% convergence speed, 10% no stall, 5% no scope violation.
    """
    score = float(getattr(example, "score", 0))
    rounds = int(getattr(example, "rounds_taken", MAX_CONTRACT_ROUNDS))
    stall = bool(getattr(example, "stall_detected", False))
    scope_viol = bool(getattr(example, "write_scope_violations", False))

    convergence = (MAX_CONTRACT_ROUNDS - rounds) / MAX_CONTRACT_ROUNDS

    value = (
        0.70 * score
        + 0.15 * convergence
        + 0.10 * (0.0 if stall else 1.0)
        + 0.05 * (0.0 if scope_viol else 1.0)
    )
    return dspy.Prediction(
        score=value,
        feedback=build_contract_feedback(example, prediction, value),
    )
```

- [ ] **Step 6: Run all metric tests**

```bash
uv run python -m pytest tests/test_contract_dspy.py -v
```

Expected: all tests PASS including the 3 new metric tests

- [ ] **Step 7: Commit**

```bash
git add agent/optimization/contract_modules.py agent/optimization/metrics.py agent/optimization/feedback.py tests/test_contract_dspy.py
git commit -m "feat(contract): ExecutorPropose/EvaluatorReview signatures + contract_metric + feedback"
```

---

## Task 5: optimize_prompts.py --target contract + compiled program loading

**Files:**
- Modify: `scripts/optimize_prompts.py`
- Modify: `agent/contract_phase.py`

- [ ] **Step 1: Write failing test for optimize_contract integration**

Append to `tests/test_contract_dspy.py`:

```python
def test_optimize_contract_target_in_choices():
    """--target contract is a valid choice in optimize_prompts.py CLI."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "scripts/optimize_prompts.py", "--help"],
        capture_output=True, text=True, cwd="."
    )
    assert "contract" in result.stdout


def test_contract_phase_loads_compiled_programs(tmp_path, monkeypatch):
    """If compiled program files exist, contract_phase loads them (logged in DEBUG)."""
    import agent.contract_phase as cp
    # When both program files exist, _load_compiled_programs returns True
    executor_path = tmp_path / "contract_executor_program.json"
    evaluator_path = tmp_path / "contract_evaluator_program.json"
    executor_path.write_text("{}")
    evaluator_path.write_text("{}")
    monkeypatch.setattr(cp, "_EXECUTOR_PROGRAM_PATH", executor_path)
    monkeypatch.setattr(cp, "_EVALUATOR_PROGRAM_PATH", evaluator_path)
    # _load_compiled_programs is fail-open: bad JSON → returns False
    result = cp._load_compiled_programs()
    assert result is False  # {} is not a valid DSPy program — fail-open is correct
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run python -m pytest tests/test_contract_dspy.py::test_optimize_contract_target_in_choices -v
```

Expected: FAIL — `"contract" not in output`

- [ ] **Step 3: Add optimize_contract to optimize_prompts.py**

In `scripts/optimize_prompts.py`, after the existing imports, add:

```python
from agent.optimization.metrics import builder_metric, evaluator_metric, classifier_metric, contract_metric
```

Add paths after existing `_CLASSIFIER_PROGRAM_PATH`:
```python
_CONTRACT_EXECUTOR_PROGRAM_PATH = _BASE / "data" / "contract_executor_program.json"
_CONTRACT_EVALUATOR_PROGRAM_PATH = _BASE / "data" / "contract_evaluator_program.json"
```

Add import for contract modules after other agent imports:
```python
from agent.optimization.contract_modules import ExecutorPropose, EvaluatorReview
```

Add `get_contract_trainset` to the dspy_examples import line:
```python
from agent.dspy_examples import get_trainset, get_eval_trainset, get_classifier_trainset, get_contract_trainset
```

Add the `optimize_contract` function after `optimize_classifier`:

```python
def optimize_contract(model: str, cfg: dict) -> None:
    """Compile ExecutorPropose and EvaluatorReview using contract training examples."""
    env_override = os.environ.get("OPTIMIZER_CONTRACT")

    executor_trainset = [
        dspy.Example(**{k: getattr(ex, k) for k in ex._store}).with_inputs(
            "task_text", "task_type", "evaluator_feedback"
        )
        for ex in get_contract_trainset(min_score=1.0, role="executor")
    ]
    evaluator_trainset = [
        dspy.Example(**{k: getattr(ex, k) for k in ex._store}).with_inputs(
            "task_text", "task_type", "executor_proposal"
        )
        for ex in get_contract_trainset(min_score=1.0, role="evaluator")
    ]

    if not executor_trainset or not evaluator_trainset:
        print(
            "[optimize] No contract examples found. "
            "Run with CONTRACT_ENABLED=1 CONTRACT_COLLECT_DSPY=1 to collect them."
        )
        return

    print(
        f"[optimize] Contract executor trainset: {len(executor_trainset)} examples, "
        f"evaluator trainset: {len(evaluator_trainset)} examples"
    )

    if env_override:
        os.environ["OPTIMIZER_DEFAULT"] = env_override

    _run_target(
        lambda: dspy.Predict(ExecutorPropose),
        executor_trainset, contract_metric,
        _CONTRACT_EXECUTOR_PROGRAM_PATH, "contract/executor",
        model=model, cfg=cfg, task_max_tokens=800,
    )
    _run_target(
        lambda: dspy.Predict(EvaluatorReview),
        evaluator_trainset, contract_metric,
        _CONTRACT_EVALUATOR_PROGRAM_PATH, "contract/evaluator",
        model=model, cfg=cfg, task_max_tokens=800,
    )
```

In `main()`, update the argparse choices:
```python
    parser.add_argument(
        "--target",
        choices=["builder", "evaluator", "classifier", "contract", "all"],
        default="all",
        ...
    )
```

Add the contract branch in `main()`:
```python
        if args.target in ("contract", "all"):
            optimize_contract(model, cfg)
```

- [ ] **Step 4: Add compiled program loading to contract_phase.py**

In `agent/contract_phase.py`, after `_LOG_LEVEL` and `_FENCE_RE` definitions, add:

```python
_EXECUTOR_PROGRAM_PATH = _DATA / "contract_executor_program.json"
_EVALUATOR_PROGRAM_PATH = _DATA / "contract_evaluator_program.json"
_executor_predictor = None
_evaluator_predictor = None


def _load_compiled_programs() -> bool:
    """Load compiled DSPy programs at module startup. Returns True on success."""
    global _executor_predictor, _evaluator_predictor
    if not (_EXECUTOR_PROGRAM_PATH.exists() and _EVALUATOR_PROGRAM_PATH.exists()):
        return False
    try:
        import dspy
        from .optimization.contract_modules import ExecutorPropose, EvaluatorReview
        ep = dspy.Predict(ExecutorPropose)
        ep.load(str(_EXECUTOR_PROGRAM_PATH))
        evp = dspy.Predict(EvaluatorReview)
        evp.load(str(_EVALUATOR_PROGRAM_PATH))
        _executor_predictor = ep
        _evaluator_predictor = evp
        if _LOG_LEVEL == "DEBUG":
            print("[contract] Loaded compiled executor/evaluator programs")
        return True
    except Exception as exc:
        if _LOG_LEVEL == "DEBUG":
            print(f"[contract] Failed to load compiled programs: {exc}")
        return False


_load_compiled_programs()
```

- [ ] **Step 5: Run all tests**

```bash
uv run python -m pytest tests/test_contract_dspy.py tests/test_contract_phase.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/optimize_prompts.py agent/contract_phase.py tests/test_contract_dspy.py
git commit -m "feat(contract): --target contract in optimize_prompts + compiled program loading"
```

---

## Task 6: distill_contracts.py script

**Files:**
- Create: `scripts/distill_contracts.py`
- Create: `tests/test_distill_contracts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_distill_contracts.py`:

```python
"""Tests for contract distillation script."""
import json
import pytest
from pathlib import Path


def _write_examples(path: Path, examples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for ex in examples:
            fh.write(json.dumps(ex) + "\n")


def _make_email_example(plan_steps=None, success_criteria=None, score=1.0):
    return {
        "task_text": "Send email to alice",
        "task_type": "email",
        "rounds": [],
        "final_contract": {
            "plan_steps": plan_steps or ["search /contacts", "write /outbox/1.json"],
            "success_criteria": success_criteria or ["file written to /outbox/"],
            "required_evidence": ["/outbox/1.json"],
            "failure_conditions": ["no write to /outbox/"],
            "is_default": False,
            "rounds_taken": 1,
        },
        "is_default": False,
        "rounds_taken": 1,
        "score": score,
        "stall_detected": False,
        "write_scope_violations": False,
    }


def test_distill_selects_top_n_plan_steps(tmp_path):
    """Most frequent plan_steps are selected, up to 6."""
    from scripts.distill_contracts import distill_task_type

    common = ["search /contacts", "read /contacts/alice.json", "write /outbox/1.json"]
    rare = ["list /archive"]
    examples = [_make_email_example(plan_steps=common) for _ in range(5)]
    examples.append(_make_email_example(plan_steps=common + rare))

    result = distill_task_type(examples)
    assert "search /contacts" in result["plan_steps"]
    assert "write /outbox/1.json" in result["plan_steps"]
    assert len(result["plan_steps"]) <= 6


def test_distill_skips_low_score(tmp_path):
    """Examples with score < 1.0 are excluded."""
    from scripts.distill_contracts import distill_task_type

    examples = [
        _make_email_example(plan_steps=["step-good"], score=1.0),
        _make_email_example(plan_steps=["step-bad"], score=0.5),
    ]
    result = distill_task_type(examples)
    assert "step-good" in result["plan_steps"]
    assert not any("step-bad" in s for s in result["plan_steps"])


def test_distill_returns_none_below_min_examples(tmp_path):
    """Fewer than min_examples good examples → returns None (skip)."""
    from scripts.distill_contracts import distill_task_type

    examples = [_make_email_example() for _ in range(3)]
    result = distill_task_type(examples, min_examples=10)
    assert result is None


def test_distill_apply_writes_file(tmp_path):
    """--apply writes data/default_contracts/{task_type}.json."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.distill_contracts import run_distillation

    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()
    # Write existing default.json (must not be overwritten)
    (contracts_dir / "default.json").write_text('{"plan_steps":["default"]}')

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distillation(
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=True,
        min_examples=5,
        task_type_filter=None,
    )

    email_file = contracts_dir / "email.json"
    assert email_file.exists()
    data = json.loads(email_file.read_text())
    assert "plan_steps" in data
    assert "success_criteria" in data
    # default.json untouched
    default_data = json.loads((contracts_dir / "default.json").read_text())
    assert default_data["plan_steps"] == ["default"]


def test_distill_dry_run_no_files_written(tmp_path):
    """Without --apply, no files are written."""
    from scripts.distill_contracts import run_distillation

    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distillation(
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=False,
        min_examples=5,
        task_type_filter=None,
    )

    assert not (contracts_dir / "email.json").exists()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run python -m pytest tests/test_distill_contracts.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.distill_contracts'`

- [ ] **Step 3: Create scripts/distill_contracts.py**

```python
"""Distill per-type default contracts from successful negotiated examples.

Reads data/dspy_contract_examples.jsonl, groups by task_type, selects top-N
most frequent field elements from score=1.0 examples.

Usage:
    uv run python scripts/distill_contracts.py                   # dry-run: print results
    uv run python scripts/distill_contracts.py --apply           # write files
    uv run python scripts/distill_contracts.py --min-examples 5  # lower threshold
    uv run python scripts/distill_contracts.py --task-type email # single type
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_DEFAULT_EXAMPLES_PATH = _BASE / "data" / "dspy_contract_examples.jsonl"
_DEFAULT_CONTRACTS_DIR = _BASE / "data" / "default_contracts"

_TOP_N = {
    "plan_steps": 6,
    "success_criteria": 4,
    "required_evidence": 3,
    "failure_conditions": 4,
}


def _normalize(text: str) -> str:
    return text.lower().strip()


def distill_task_type(
    examples: list[dict],
    min_examples: int = 10,
) -> dict | None:
    """Distill a single task_type's examples into a default contract dict.

    Returns None if fewer than min_examples pass score filter.
    """
    good = [
        ex for ex in examples
        if float(ex.get("score", 0)) >= 1.0 and not ex.get("is_default", True)
    ]
    if len(good) < min_examples:
        return None

    result = {}
    for field, top_n in _TOP_N.items():
        counter: Counter = Counter()
        for ex in good:
            fc = ex.get("final_contract", {})
            for item in fc.get(field, []):
                counter[_normalize(str(item))] += 1
        result[field] = [item for item, _ in counter.most_common(top_n)]

    return result


def run_distillation(
    examples_path: Path,
    contracts_dir: Path,
    apply: bool,
    min_examples: int,
    task_type_filter: str | None,
) -> None:
    if not examples_path.exists():
        print(f"[distill] {examples_path} not found — nothing to do")
        return

    all_examples: dict[str, list[dict]] = {}
    with examples_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tt = rec.get("task_type", "default")
            all_examples.setdefault(tt, []).append(rec)

    types_to_process = (
        [task_type_filter] if task_type_filter else sorted(all_examples.keys())
    )

    for tt in types_to_process:
        examples = all_examples.get(tt, [])
        result = distill_task_type(examples, min_examples=min_examples)
        if result is None:
            good_count = sum(
                1 for ex in examples
                if float(ex.get("score", 0)) >= 1.0 and not ex.get("is_default", True)
            )
            print(f"[distill] {tt}: {good_count} good examples < {min_examples} — skipping")
            continue

        print(f"[distill] {tt}: {len(examples)} total → distilled")
        for field, items in result.items():
            print(f"  {field}: {items}")

        if apply:
            out_path = contracts_dir / f"{tt}.json"
            out_path.write_text(
                json.dumps({**result, "is_default": True, "rounds_taken": 0},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  → written to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distill per-type default contracts from collected examples."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Write files (default: dry-run)")
    parser.add_argument("--min-examples", type=int, default=10,
                        dest="min_examples",
                        help="Minimum score=1.0 examples per type (default: 10)")
    parser.add_argument("--task-type", default=None, dest="task_type",
                        help="Process single task type only")
    args = parser.parse_args()

    run_distillation(
        examples_path=_DEFAULT_EXAMPLES_PATH,
        contracts_dir=_DEFAULT_CONTRACTS_DIR,
        apply=args.apply,
        min_examples=args.min_examples,
        task_type_filter=args.task_type,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest tests/test_distill_contracts.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Verify CLI works**

```bash
uv run python scripts/distill_contracts.py --help
```

Expected: shows `--apply`, `--min-examples`, `--task-type` options

- [ ] **Step 6: Commit**

```bash
git add scripts/distill_contracts.py tests/test_distill_contracts.py
git commit -m "feat(contract): distill_contracts.py — frequency-based per-type default contract distillation"
```

---

## Task 7: .env.example + CHANGELOG

**Files:**
- Modify: `.env.example`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add MODEL_CONTRACT and OPTIMIZER_CONTRACT to .env.example**

Find the contract section (search for `CONTRACT_ENABLED`). After those lines, add:

```
# MODEL_CONTRACT=openrouter/anthropic/claude-3-5-haiku  # cheap model for negotiation; falls back to MODEL_DEFAULT
OPTIMIZER_CONTRACT=copro                 # DSPy backend for contract optimization (copro|gepa)
```

The MODEL_CONTRACT line must be commented out (it's optional; absence means fall back to MODEL_DEFAULT).

- [ ] **Step 2: Add CHANGELOG entry**

In `CHANGELOG.md`, prepend a new entry at the top (after the first heading):

```markdown
## [Unreleased]

### Added
- **Contract DSPy optimization pipeline** (FIX-401):
  - `ContractRound` model in `contract_models.py` for per-round transcript
  - `negotiate_contract()` returns 4-tuple `(Contract, int, int, list[ContractRound])`
  - `MODEL_CONTRACT` env var — separate model routing for negotiation (falls back to `MODEL_DEFAULT`)
  - `record_contract_example()` / `get_contract_trainset()` in `dspy_examples.py`
  - `agent/optimization/contract_modules.py` — `ExecutorPropose` and `EvaluatorReview` DSPy signatures
  - `contract_metric()` in `metrics.py` — weighted score (70% task, 15% convergence, 10% stall, 5% scope)
  - `build_contract_feedback()` in `feedback.py`
  - `scripts/optimize_prompts.py --target contract` — compiles both programs
  - Compiled program loading in `contract_phase.py` at module startup (fail-open)
  - `scripts/distill_contracts.py` — frequency-based distillation into `data/default_contracts/{type}.json`
  - `OPTIMIZER_CONTRACT` env var (default `copro`)
```

- [ ] **Step 3: Run the full test suite to verify no regressions**

```bash
uv run python -m pytest tests/ -v --ignore=tests/test_purge_script.py -x
```

Expected: all tests PASS except the 3 pre-existing failures in `test_purge_script.py` and `test_t33_no_false_positive`

- [ ] **Step 4: Commit**

```bash
git add .env.example CHANGELOG.md
git commit -m "docs: MODEL_CONTRACT + OPTIMIZER_CONTRACT in .env.example; CHANGELOG FIX-401"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `ContractRound` model | Task 1 |
| `negotiate_contract()` 4-tuple return | Task 1 |
| `MODEL_CONTRACT` env routing (falls back to `MODEL_DEFAULT`) | Task 1 |
| CC tier returns `[]` for rounds | Task 1 |
| `record_contract_example()` in `dspy_examples.py` | Task 2 |
| `get_contract_trainset(role=...)` | Task 2 |
| Threshold hint at 30 examples | Task 2 |
| `expand_rounds=True` multiplies into per-round examples | Task 2 |
| `contract_rounds` passed through stats in `__init__.py` | Task 3 |
| `CONTRACT_COLLECT_DSPY` block updated in `main.py` | Task 3 |
| `ExecutorPropose` signature | Task 4 |
| `EvaluatorReview` signature | Task 4 |
| `contract_metric()` with weighted formula | Task 4 |
| `build_contract_feedback()` | Task 4 |
| `--target contract` in `optimize_prompts.py` | Task 5 |
| Compiled program loading in `contract_phase.py` (fail-open) | Task 5 |
| `OPTIMIZER_CONTRACT` env respected | Task 5 |
| `distill_contracts.py` script | Task 6 |
| Dry-run / `--apply` / `--min-examples` / `--task-type` CLI | Task 6 |
| `default.json` never overwritten | Task 6 |
| `.env.example` entries | Task 7 |
| CHANGELOG entry | Task 7 |
| Existing tests pass | Tasks 1, 5 |
| New tests: collection, metric, distillation | Tasks 2, 4, 6 |

All spec requirements are covered. No gaps found.

**Type consistency check:**
- `ContractRound.model_dump()` → `dict` → stored in `stats["contract_rounds"]` as `list[dict]` ✓
- `record_contract_example(rounds=list[dict], ...)` matches what `__init__.py` passes ✓
- `get_contract_trainset()` returns `list[dspy.Example]` — same pattern as `get_trainset()` ✓
- `contract_metric(example, pred, trace=None) -> dspy.Prediction` matches `builder_metric` signature ✓
- `distill_task_type(examples: list[dict]) -> dict | None` ✓
- `run_distillation(...)` used by both `main()` and tests ✓

**Placeholder scan:** No TBD, TODO, or placeholder text found. All code blocks are complete.
