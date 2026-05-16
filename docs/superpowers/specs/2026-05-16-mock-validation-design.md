# Mock Validation Pipeline — Design Spec

**Date:** 2026-05-16  
**Status:** Approved

## Problem

`propose_optimizations.py` validates optimization candidates (rules, security gates, prompt patches)
by re-running the originating task through the live BitGN harness with `validate_recommendation`.
This requires `BITGN_API_KEY`, `BENCHMARK_HOST`, `BENCHMARK_ID` — not available offline —
and adds network latency to every candidate.

## Goal

Replace `validate_recommendation` with offline mock validation:
- No VM, no harness, no API keys required
- Binary score: `1.0` (assertions passed) or `0.0` (failed)
- If `1.0` → write candidate file; if `0.0` → reject

## Scope

Only `propose_optimizations.py` and its `validate_recommendation` call sites.
`run_pipeline` production code is **unchanged** (MockVM is duck-type compatible).

---

## Design

### Flow

```
eval_log entry {task_text, ...}
   ↓
_generate_mock_scenario(task_text, model, cfg)    [LLM: MOCK_GEN phase]
   ↓ MockScenario {mock_results: [CSV...], answer_assertions: "def test_answer(...)"}
   ↓
MockVM(mock_results)
   ↓
run_pipeline(mock_vm, model, task_text, pre, cfg, injected_candidate)
   MAX_STEPS=15, LEARN active, full cycle loop
   → SQL_PLAN → SECURITY → SCHEMA → VALIDATE(EXPLAIN→"ok") → EXECUTE(→mock CSV) → ANSWER
   ↓
run_tests(answer_assertions, "test_answer", {sql_results, answer})
   ↓
score = 1.0 (passed) | 0.0 (failed)
```

### MockVM (agent/mock_vm.py)

Duck-type replacement for `EcomRuntimeClientSync`. Implements `.exec()` and `.answer()`.

- `exec(ExecRequest)` with EXPLAIN query → returns `_MockResult("ok")`
- `exec(ExecRequest)` with data query → returns `_MockResult(mock_results[i])`, cycles through list
- `answer(AnswerRequest)` → captures to `self.last_answer` (no network call)

```python
class _MockResult:
    def __init__(self, stdout: str):
        self.stdout = stdout

class MockVM:
    def __init__(self, mock_results: list[str]):
        self._results = mock_results
        self._exec_count = 0
        self.last_answer = None  # AnswerRequest | None

    def exec(self, req):
        args = list(req.args or [])
        if args and args[0].upper().startswith("EXPLAIN"):
            return _MockResult("ok")
        idx = min(self._exec_count, max(len(self._results) - 1, 0))
        result = self._results[idx] if self._results else ""
        self._exec_count += 1
        return _MockResult(result)

    def answer(self, req):
        self.last_answer = req
```

### MockScenario (agent/models.py addition)

```python
class MockScenario(BaseModel):
    reasoning: str
    mock_results: list[str]     # plausible CSV rows per expected query
    answer_assertions: str      # Python def test_answer(sql_results, answer): ...
```

### MOCK_GEN Phase (data/prompts/mock_gen.md)

LLM prompt that receives `task_text` + known schema tables
(`products`, `product_properties`, `inventory`, `kinds`, `carts`, `cart_items`)
and generates:

- `mock_results`: list of plausible CSV strings with realistic e-commerce data
  (sku, path, name, price columns as appropriate for the task)
- `answer_assertions`: Python function body asserting the answer is semantically correct
  (e.g., `assert "Drill" in answer["message"]`, `assert answer["outcome"] == "OUTCOME_OK"`)

Output schema: `MockScenario` JSON.

### _generate_mock_scenario (propose_optimizations.py)

```python
def _generate_mock_scenario(
    task_text: str, model: str, cfg: dict
) -> MockScenario | None:
    guide = load_prompt("mock_gen")
    system = guide or "# PHASE: mock_gen\nGenerate mock_results and answer_assertions as JSON."
    user_msg = f"TASK: {task_text}"
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=1024)
    if not raw:
        return None
    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None
    try:
        return MockScenario.model_validate(parsed)
    except Exception:
        return None
```

### validate_mock (propose_optimizations.py)

Replaces `validate_recommendation`. Returns `(score: float, reason: str)`.

```python
def validate_mock(
    entry: dict,
    *,
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
    model: str,
    cfg: dict,
) -> tuple[float, str]:
    task_text = entry["task_text"]
    scenario = _generate_mock_scenario(task_text, model, cfg)
    if scenario is None:
        return 1.0, "mock_gen failed — fail open"

    mock_vm = MockVM(scenario.mock_results)
    pre = PrephaseResult(db_schema="", agents_md_content="", agents_md_index={},
                         schema_digest={}, agent_id="", current_date="")

    _orig_max = os.environ.get("MAX_STEPS")
    os.environ["MAX_STEPS"] = "15"
    try:
        run_pipeline(
            mock_vm, model, task_text, pre, cfg,
            injected_session_rules=injected_session_rules or [],
            injected_prompt_addendum=injected_prompt_addendum,
            injected_security_gates=injected_security_gates or [],
        )
    finally:
        if _orig_max is None:
            os.environ.pop("MAX_STEPS", None)
        else:
            os.environ["MAX_STEPS"] = _orig_max

    if mock_vm.last_answer is None:
        return 0.0, "pipeline produced no answer"

    answer_ctx = {
        "sql_results": scenario.mock_results,
        "answer": {"message": mock_vm.last_answer.message,
                   "outcome": mock_vm.last_answer.outcome},
    }
    passed, err, _ = run_tests(
        scenario.answer_assertions, "test_answer", answer_ctx, task_text=task_text
    )
    return (1.0, "ok") if passed else (0.0, err or "assertions failed")
```

### main() call sites (propose_optimizations.py)

Replace each `validate_recommendation(task_id, ...)` with `validate_mock(entry, ..., model=model, cfg=cfg)`.
Replace score comparison `validation >= original` with `mock_score >= 1.0`.
Remove `task_id` variable usage (no longer needed for validation).

---

## Files Changed

| File | Change |
|------|--------|
| `agent/mock_vm.py` | **NEW** — `MockVM` + `_MockResult` |
| `agent/models.py` | **ADD** — `MockScenario` Pydantic model |
| `data/prompts/mock_gen.md` | **NEW** — MOCK_GEN LLM prompt |
| `scripts/propose_optimizations.py` | **ADD** `_generate_mock_scenario`, `validate_mock`; **REMOVE** `validate_recommendation`, `read_original_score`, harness imports |

## Files Unchanged

- `agent/pipeline.py` — no changes; MockVM is duck-type compatible
- `agent/test_runner.py` — reused as-is via `run_tests`
- `agent/evaluator.py` — no changes

---

## Constraints & Edge Cases

- **mock_gen fail-open:** if LLM fails to generate `MockScenario`, return `score=1.0` (fail-open) to avoid blocking all candidates on infra failure
- **empty mock_results:** MockVM returns `""` for data queries → pipeline cycles through LEARN and retries; with `MAX_STEPS=15` there's sufficient budget to converge
- **EXPLAIN mock:** always returns `"ok"` — syntax validation is skipped in mock mode (no real SQLite available)
- **outcome proto enum:** `AnswerRequest.outcome` is a proto enum int, not the string `"OUTCOME_OK"`. In `validate_mock`, convert via `OUTCOME_BY_NAME` reverse map or pass the string outcome from `AnswerOutput` directly. Implementation: capture outcome string before `vm.answer()` call in pipeline, or reverse-map the int in MockVM.
- **MAX_STEPS thread-safety:** `os.environ["MAX_STEPS"]` is set/restored in `finally` block; `run_pipeline` reads it at call time via module-level `_MAX_CYCLES` — **this is a bug risk** since `_MAX_CYCLES` is computed at import time. Solution: pass `max_cycles` as a parameter OR reload it inside `validate_mock` by temporarily setting before import.

> **NOTE:** `_MAX_CYCLES` in `pipeline.py` is set at module import time (`int(os.environ.get("MAX_STEPS", "3"))`), so `os.environ` mutation won't affect it at runtime. `validate_mock` should call `run_pipeline` with a wrapper that patches `pipeline._MAX_CYCLES` directly, or `pipeline.py` should be modified to read `MAX_STEPS` per-call.

This is an implementation detail to resolve during execution — two options:
1. Modify `run_pipeline` to accept `max_cycles: int | None = None`
2. Patch `pipeline._MAX_CYCLES` temporarily in `validate_mock`

Option 1 is cleaner and adds a useful capability.

---

## Out of Scope

- Storing `db_schema` or `agents_md` in eval_log (MOCK_GEN generates plausible data from task_text alone)
- Modifying production pipeline behavior
- Changes to TDD (`TDD_ENABLED`) or evaluator paths
