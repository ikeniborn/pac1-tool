# Mock Validation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `validate_recommendation` (BitGN harness) with offline `validate_mock` that uses a MockVM + LLM-generated mock scenario to verify optimization candidates without network access.

**Architecture:** New `MockVM` class duck-type-replaces `EcomRuntimeClientSync` for `run_pipeline`. A `MOCK_GEN` LLM phase generates plausible CSV results and Python answer-assertions from `task_text`. `validate_mock` runs the full pipeline (LEARN active, `max_cycles=15`) through MockVM, then verifies the answer via `run_tests`.

**Tech Stack:** Python, Pydantic, pytest, existing `run_pipeline` / `run_tests` / `call_llm_raw`.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `agent/mock_vm.py` | **CREATE** | `MockVM` + `_MockResult` — duck-type VM replacement |
| `agent/models.py` | **MODIFY** | Add `MockScenario` Pydantic model |
| `agent/pipeline.py` | **MODIFY** | Add `max_cycles: int \| None = None` parameter to `run_pipeline` |
| `data/prompts/mock_gen.md` | **CREATE** | MOCK_GEN LLM prompt |
| `scripts/propose_optimizations.py` | **MODIFY** | Add `_generate_mock_scenario`, `validate_mock`; remove `validate_recommendation`, `read_original_score` |
| `tests/test_mock_vm.py` | **CREATE** | Tests for MockVM |
| `tests/test_propose_optimizations.py` | **MODIFY** | Replace `validate_recommendation` patches with `validate_mock`; remove `read_original_score` tests; add `validate_mock` + `_generate_mock_scenario` tests |

---

## Task 1: MockScenario model

**Files:**
- Modify: `agent/models.py`
- Test: `tests/test_pipeline_models.py` (add one test)

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline_models.py`:

```python
def test_mock_scenario_validates():
    from agent.models import MockScenario
    s = MockScenario(
        reasoning="test",
        mock_results=["sku,path\nSKU-1,/proc/catalog/SKU-1.json\n"],
        answer_assertions="def test_answer(sql_results, answer): assert answer['outcome'] == 'OUTCOME_OK'",
    )
    assert s.mock_results[0].startswith("sku,path")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /path/to/ecom1-agent && uv run pytest tests/test_pipeline_models.py::test_mock_scenario_validates -v
```

Expected: `ImportError` or `AttributeError` (MockScenario doesn't exist yet).

- [ ] **Step 3: Add MockScenario to agent/models.py**

Append after `TestGenOutput` (line 59):

```python


class MockScenario(BaseModel):
    reasoning: str
    mock_results: list[str]
    answer_assertions: str
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_pipeline_models.py::test_mock_scenario_validates -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/models.py tests/test_pipeline_models.py
git commit -m "feat(models): add MockScenario for offline mock validation"
```

---

## Task 2: MockVM

**Files:**
- Create: `agent/mock_vm.py`
- Create: `tests/test_mock_vm.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mock_vm.py`:

```python
import pytest
from unittest.mock import MagicMock


def _make_req(args):
    req = MagicMock()
    req.args = args
    return req


def test_explain_returns_ok():
    from agent.mock_vm import MockVM
    vm = MockVM(["sku,path\nSKU-1,/a.json\n"])
    result = vm.exec(_make_req(["EXPLAIN SELECT sku FROM products"]))
    assert result.stdout == "ok"


def test_explain_case_insensitive():
    from agent.mock_vm import MockVM
    vm = MockVM(["row1"])
    result = vm.exec(_make_req(["explain select 1"]))
    assert result.stdout == "ok"


def test_data_query_returns_mock_result():
    from agent.mock_vm import MockVM
    vm = MockVM(["sku,path\nSKU-1,/a.json\n", "count\n42\n"])
    r1 = vm.exec(_make_req(["SELECT sku FROM products"]))
    r2 = vm.exec(_make_req(["SELECT COUNT(*) FROM products"]))
    assert r1.stdout == "sku,path\nSKU-1,/a.json\n"
    assert r2.stdout == "count\n42\n"


def test_cycles_last_result_when_exhausted():
    from agent.mock_vm import MockVM
    vm = MockVM(["only-result"])
    vm.exec(_make_req(["SELECT 1"]))  # consume first
    r = vm.exec(_make_req(["SELECT 2"]))  # should return last (index 0 clamped)
    assert r.stdout == "only-result"


def test_empty_mock_results_returns_empty_string():
    from agent.mock_vm import MockVM
    vm = MockVM([])
    r = vm.exec(_make_req(["SELECT 1"]))
    assert r.stdout == ""


def test_answer_captures_request():
    from agent.mock_vm import MockVM
    vm = MockVM([])
    req = MagicMock()
    req.message = "Found 3 items"
    vm.answer(req)
    assert vm.last_answer is req
    assert vm.last_answer.message == "Found 3 items"


def test_last_answer_none_initially():
    from agent.mock_vm import MockVM
    vm = MockVM(["data"])
    assert vm.last_answer is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_mock_vm.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.mock_vm'`.

- [ ] **Step 3: Create agent/mock_vm.py**

```python
"""MockVM — duck-type replacement for EcomRuntimeClientSync used in offline validation."""
from __future__ import annotations


class _MockResult:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


class MockVM:
    """Offline VM: returns pre-generated CSV results, captures the answer call."""

    def __init__(self, mock_results: list[str]) -> None:
        self._results = list(mock_results)
        self._exec_count = 0
        self.last_answer = None

    def exec(self, req) -> _MockResult:
        args = list(req.args or [])
        if args and args[0].upper().startswith("EXPLAIN"):
            return _MockResult("ok")
        idx = min(self._exec_count, max(len(self._results) - 1, 0))
        result = self._results[idx] if self._results else ""
        self._exec_count += 1
        return _MockResult(result)

    def answer(self, req) -> None:
        self.last_answer = req
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_mock_vm.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/mock_vm.py tests/test_mock_vm.py
git commit -m "feat(mock_vm): add MockVM for offline pipeline validation"
```

---

## Task 3: max_cycles parameter in run_pipeline

**Files:**
- Modify: `agent/pipeline.py` (lines 365, 449)
- Test: `tests/test_pipeline.py` (add one test)

The problem: `_MAX_CYCLES = int(os.environ.get("MAX_STEPS", "3"))` is set at **import time** (line 39). Mutating `os.environ` after import has no effect. `validate_mock` needs `max_cycles=15`. Solution: add `max_cycles: int | None = None` parameter to `run_pipeline`; use it inside the loop.

- [ ] **Step 1: Write failing test**

Open `tests/test_pipeline.py` and find an existing fixture for a mocked VM. Add at the end:

```python
def test_run_pipeline_respects_max_cycles_param(tmp_path):
    """run_pipeline stops after max_cycles even if _MAX_CYCLES is larger."""
    from agent.pipeline import run_pipeline
    from agent.prephase import PrephaseResult
    from agent.mock_vm import MockVM
    from unittest.mock import patch

    call_counts = []

    def counting_llm(system, user_msg, model, cfg, **kw):
        call_counts.append(1)
        return None  # force every cycle to fail → triggers LEARN → next cycle

    pre = PrephaseResult(db_schema="", agents_md_content="", agents_md_index={},
                         schema_digest={}, agent_id="", current_date="")
    mock_vm = MockVM([])

    with patch("agent.pipeline.call_llm_raw", side_effect=counting_llm), \
         patch("agent.pipeline._MAX_CYCLES", 10):
        run_pipeline(mock_vm, "test-model", "How many items?", pre, {}, max_cycles=2)

    # max_cycles=2 → at most 2 SQL_PLAN calls (+ LEARN calls, but LEARN also fails → no extra SQL_PLAN)
    sql_plan_calls = len(call_counts)
    assert sql_plan_calls <= 4  # 2 cycles × (sql_plan + learn) = 4 max
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py::test_run_pipeline_respects_max_cycles_param -v
```

Expected: `TypeError: run_pipeline() got an unexpected keyword argument 'max_cycles'`.

- [ ] **Step 3: Modify agent/pipeline.py**

In `run_pipeline` signature (line 365), add `max_cycles: int | None = None,`:

```python
def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
    task_id: str = "",
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
    max_cycles: int | None = None,
) -> tuple[dict, threading.Thread | None]:
```

At line 385 (after `highlighted_vault_rules: list[str] = []`), add:

```python
    _cycle_limit = max_cycles if max_cycles is not None else _MAX_CYCLES
```

At line 449, change `for cycle in range(_MAX_CYCLES):` to:

```python
        for cycle in range(_cycle_limit):
```

And at line 740, change the print to use `_cycle_limit`:

```python
            print(f"{CLI_RED}[pipeline] All {_cycle_limit} cycles exhausted — clarification{CLI_CLR}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_pipeline.py::test_run_pipeline_respects_max_cycles_param -v
```

Expected: PASS.

- [ ] **Step 5: Run full pipeline tests to confirm no regression**

```bash
uv run pytest tests/test_pipeline.py tests/test_pipeline_tdd.py -v
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): add max_cycles parameter to run_pipeline"
```

---

## Task 4: MOCK_GEN prompt

**Files:**
- Create: `data/prompts/mock_gen.md`

No tests needed — prompt content is tested indirectly via `_generate_mock_scenario` integration.

- [ ] **Step 1: Create data/prompts/mock_gen.md**

```markdown
# PHASE: mock_gen

You are generating test fixtures for offline pipeline validation.

Given a task description, produce a `MockScenario` JSON object with:
- `reasoning`: brief explanation of the mock data choices
- `mock_results`: list of plausible CSV strings (one per expected SQL query), using realistic e-commerce data. Known tables: `products` (sku, kind_id, path), `product_properties` (product_id, key, value), `inventory` (sku, store_id, quantity), `kinds` (id, name), `carts` (id, customer_id), `cart_items` (cart_id, sku, quantity). Include a header row. Use `/proc/catalog/{sku}.json` as path.
- `answer_assertions`: a single Python function `def test_answer(sql_results, answer): ...` that asserts the answer `message` (string) is semantically correct for the task. Check that key entities from the task (product names, counts, etc.) appear in the message. Check `answer["outcome"] == "OUTCOME_OK"` for successful lookups. Use `assert ... in answer["message"]` style. Do NOT assert exact strings from the task text verbatim — check semantic correctness.

Example output for task "How many drills do we have in stock?":
```json
{
  "reasoning": "Task asks for drill inventory count. Mock result has a COUNT aggregate. Answer should mention the count.",
  "mock_results": [
    "count\n5\n"
  ],
  "answer_assertions": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n    assert any(c.isdigit() for c in answer['message'])\n"
}
```

Return only valid JSON matching the schema above. No markdown fences, no extra text.
```

- [ ] **Step 2: Verify load_prompt finds the file**

```bash
uv run python -c "
from agent.prompt import load_prompt
p = load_prompt('mock_gen')
assert p and 'PHASE: mock_gen' in p, f'Got: {p!r}'
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add data/prompts/mock_gen.md
git commit -m "feat(prompts): add mock_gen prompt for offline validation fixture generation"
```

---

## Task 5: _generate_mock_scenario

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Test: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_propose_optimizations.py`:

```python
def test_generate_mock_scenario_parses_llm_output():
    from agent.models import MockScenario
    llm_response = json.dumps({
        "reasoning": "product count task",
        "mock_results": ["count\n3\n"],
        "answer_assertions": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })
    with patch("scripts.propose_optimizations.call_llm_raw", return_value=llm_response):
        result = po._generate_mock_scenario("How many drills?", "test-model", {})
    assert isinstance(result, MockScenario)
    assert result.mock_results == ["count\n3\n"]


def test_generate_mock_scenario_returns_none_on_llm_failure():
    with patch("scripts.propose_optimizations.call_llm_raw", return_value=None):
        result = po._generate_mock_scenario("task", "test-model", {})
    assert result is None


def test_generate_mock_scenario_returns_none_on_invalid_json():
    with patch("scripts.propose_optimizations.call_llm_raw", return_value="not json at all"):
        result = po._generate_mock_scenario("task", "test-model", {})
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_generate_mock_scenario_parses_llm_output tests/test_propose_optimizations.py::test_generate_mock_scenario_returns_none_on_llm_failure tests/test_propose_optimizations.py::test_generate_mock_scenario_returns_none_on_invalid_json -v
```

Expected: `AttributeError: module 'scripts.propose_optimizations' has no attribute '_generate_mock_scenario'`.

- [ ] **Step 3: Add _generate_mock_scenario to propose_optimizations.py**

Add at the end of the imports section (after `call_llm_raw_cluster = call_llm_raw` on line 22):

```python
from agent.json_extract import _extract_json_from_text
from agent.models import MockScenario
from agent.prompt import load_prompt as _load_prompt
```

Add the function before `_load_model_cfg` (around line 119):

```python
def _generate_mock_scenario(task_text: str, model: str, cfg: dict) -> MockScenario | None:
    guide = _load_prompt("mock_gen")
    system = guide or "# PHASE: mock_gen\nGenerate mock_results and answer_assertions as JSON."
    raw = call_llm_raw(system, f"TASK: {task_text}", model, cfg, max_tokens=1024)
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_propose_optimizations.py::test_generate_mock_scenario_parses_llm_output tests/test_propose_optimizations.py::test_generate_mock_scenario_returns_none_on_llm_failure tests/test_propose_optimizations.py::test_generate_mock_scenario_returns_none_on_invalid_json -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add _generate_mock_scenario for LLM-based mock fixture generation"
```

---

## Task 6: validate_mock

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Test: `tests/test_propose_optimizations.py`

`validate_mock` runs the full pipeline via `MockVM` and verifies answer assertions. Returns `(1.0, "ok")` on pass, `(0.0, reason)` on fail. Fail-open on `MockScenario` generation failure.

For `outcome` in the answer context: `AnswerRequest.outcome` is a proto enum int. Convert back to string using reverse of `OUTCOME_BY_NAME`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_propose_optimizations.py`:

```python
def _make_mock_scenario(mock_results=None, assertions=None):
    from agent.models import MockScenario
    return MockScenario(
        reasoning="test",
        mock_results=mock_results or ["sku,path\nSKU-1,/proc/catalog/SKU-1.json\n"],
        answer_assertions=assertions or (
            "def test_answer(sql_results, answer):\n"
            "    assert answer['outcome'] == 'OUTCOME_OK'\n"
        ),
    )


def test_validate_mock_pass(tmp_path):
    """validate_mock returns 1.0 when assertions pass."""
    from agent.mock_vm import MockVM

    captured_vm = []

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kw):
        captured_vm.append(vm)
        req = MagicMock()
        req.message = "Found SKU-1"
        from agent.llm import OUTCOME_BY_NAME
        req.outcome = OUTCOME_BY_NAME["OUTCOME_OK"]
        vm.answer(req)
        return {}, None

    scenario = _make_mock_scenario(
        assertions=(
            "def test_answer(sql_results, answer):\n"
            "    assert answer['outcome'] == 'OUTCOME_OK'\n"
        )
    )

    with patch.object(po, "_generate_mock_scenario", return_value=scenario), \
         patch("scripts.propose_optimizations.run_pipeline", fake_run_pipeline):
        score, reason = po.validate_mock(
            {"task_text": "Find SKU-1"},
            injected_session_rules=["Never use SELECT *"],
            injected_prompt_addendum="",
            injected_security_gates=[],
            model="test-model",
            cfg={},
        )
    assert score == pytest.approx(1.0)
    assert reason == "ok"
    assert isinstance(captured_vm[0], MockVM)


def test_validate_mock_fail_when_assertions_fail():
    """validate_mock returns 0.0 when answer assertions raise AssertionError."""
    from agent.llm import OUTCOME_BY_NAME

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kw):
        req = MagicMock()
        req.message = "No data found"
        req.outcome = OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"]
        vm.answer(req)
        return {}, None

    scenario = _make_mock_scenario(
        assertions=(
            "def test_answer(sql_results, answer):\n"
            "    assert answer['outcome'] == 'OUTCOME_OK'\n"  # will fail
        )
    )

    with patch.object(po, "_generate_mock_scenario", return_value=scenario), \
         patch("scripts.propose_optimizations.run_pipeline", fake_run_pipeline):
        score, reason = po.validate_mock(
            {"task_text": "Find item"},
            injected_session_rules=[],
            injected_prompt_addendum="",
            injected_security_gates=[],
            model="test-model",
            cfg={},
        )
    assert score == pytest.approx(0.0)
    assert reason != "ok"


def test_validate_mock_fail_when_no_answer():
    """validate_mock returns 0.0 when pipeline produces no answer."""
    def fake_run_pipeline(vm, *a, **kw):
        return {}, None  # no vm.answer() call

    scenario = _make_mock_scenario()

    with patch.object(po, "_generate_mock_scenario", return_value=scenario), \
         patch("scripts.propose_optimizations.run_pipeline", fake_run_pipeline):
        score, reason = po.validate_mock(
            {"task_text": "task"},
            injected_session_rules=[],
            injected_prompt_addendum="",
            injected_security_gates=[],
            model="test-model",
            cfg={},
        )
    assert score == pytest.approx(0.0)
    assert "no answer" in reason


def test_validate_mock_fail_open_on_mock_gen_failure():
    """validate_mock returns 1.0 (fail-open) when _generate_mock_scenario returns None."""
    with patch.object(po, "_generate_mock_scenario", return_value=None):
        score, reason = po.validate_mock(
            {"task_text": "task"},
            injected_session_rules=[],
            injected_prompt_addendum="",
            injected_security_gates=[],
            model="test-model",
            cfg={},
        )
    assert score == pytest.approx(1.0)
    assert "fail open" in reason


def test_validate_mock_passes_max_cycles_15():
    """validate_mock calls run_pipeline with max_cycles=15."""
    from agent.llm import OUTCOME_BY_NAME

    captured_kw = {}

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kw):
        captured_kw.update(kw)
        req = MagicMock()
        req.message = "ok"
        req.outcome = OUTCOME_BY_NAME["OUTCOME_OK"]
        vm.answer(req)
        return {}, None

    scenario = _make_mock_scenario(
        assertions="def test_answer(sql_results, answer): pass\n"
    )

    with patch.object(po, "_generate_mock_scenario", return_value=scenario), \
         patch("scripts.propose_optimizations.run_pipeline", fake_run_pipeline):
        po.validate_mock(
            {"task_text": "task"},
            injected_session_rules=[],
            injected_prompt_addendum="",
            injected_security_gates=[],
            model="test-model",
            cfg={},
        )
    assert captured_kw.get("max_cycles") == 15
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_validate_mock_pass tests/test_propose_optimizations.py::test_validate_mock_fail_when_assertions_fail tests/test_propose_optimizations.py::test_validate_mock_fail_when_no_answer tests/test_propose_optimizations.py::test_validate_mock_fail_open_on_mock_gen_failure tests/test_propose_optimizations.py::test_validate_mock_passes_max_cycles_15 -v
```

Expected: `AttributeError: module 'scripts.propose_optimizations' has no attribute 'validate_mock'`.

- [ ] **Step 3: Add validate_mock to propose_optimizations.py**

Add at module top (near other imports, around line 19):

```python
from agent.llm import OUTCOME_BY_NAME as _OUTCOME_BY_NAME
_OUTCOME_BY_VALUE: dict = {v: k for k, v in _OUTCOME_BY_NAME.items()}
```

Add the function after `_generate_mock_scenario` (before `_load_model_cfg`):

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
    """Offline validation: returns (1.0, 'ok') on pass, (0.0, reason) on fail."""
    from agent.mock_vm import MockVM
    from agent.pipeline import run_pipeline
    from agent.prephase import PrephaseResult
    from agent.test_runner import run_tests

    task_text = entry["task_text"]
    scenario = _generate_mock_scenario(task_text, model, cfg)
    if scenario is None:
        return 1.0, "mock_gen failed — fail open"

    mock_vm = MockVM(scenario.mock_results)
    pre = PrephaseResult(
        db_schema="",
        agents_md_content="",
        agents_md_index={},
        schema_digest={},
        agent_id="",
        current_date="",
    )

    run_pipeline(
        mock_vm, model, task_text, pre, cfg,
        injected_session_rules=injected_session_rules or [],
        injected_prompt_addendum=injected_prompt_addendum,
        injected_security_gates=injected_security_gates or [],
        max_cycles=15,
    )

    if mock_vm.last_answer is None:
        return 0.0, "pipeline produced no answer"

    outcome_str = _OUTCOME_BY_VALUE.get(mock_vm.last_answer.outcome, "UNKNOWN")
    answer_ctx = {
        "sql_results": scenario.mock_results,
        "answer": {
            "message": mock_vm.last_answer.message,
            "outcome": outcome_str,
        },
    }
    passed, err, _ = run_tests(
        scenario.answer_assertions, "test_answer", answer_ctx, task_text=task_text
    )
    return (1.0, "ok") if passed else (0.0, err or "assertions failed")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_propose_optimizations.py::test_validate_mock_pass tests/test_propose_optimizations.py::test_validate_mock_fail_when_assertions_fail tests/test_propose_optimizations.py::test_validate_mock_fail_when_no_answer tests/test_propose_optimizations.py::test_validate_mock_fail_open_on_mock_gen_failure tests/test_propose_optimizations.py::test_validate_mock_passes_max_cycles_15 -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add validate_mock for offline candidate validation"
```

---

## Task 7: Replace validate_recommendation in main() and update tests

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

Remove `validate_recommendation`, `read_original_score`, harness imports. Replace 3 call sites in `main()` with `validate_mock`. Update existing tests.

- [ ] **Step 1: Update existing tests to patch validate_mock instead of validate_recommendation**

In `tests/test_propose_optimizations.py`, make the following replacements (there are many occurrences):

**Replace every** `patch.object(po, "validate_recommendation", return_value=(0.8, 0.9))` **with** `patch.object(po, "validate_mock", return_value=(1.0, "ok"))`.

**Replace** `patch.object(po, "validate_recommendation", return_value=(0.7, 0.9))` **with** `patch.object(po, "validate_mock", return_value=(1.0, "ok"))`.

**Replace** `patch.object(po, "validate_recommendation", return_value=(1.0, 0.5))` **with** `patch.object(po, "validate_mock", return_value=(0.0, "score dropped"))` (this is the rejection test).

**Replace** `patch.object(po, "validate_recommendation", return_value=(None, 0.8))` **with** `patch.object(po, "validate_mock", return_value=(1.0, "ok"))` (no-baseline case → still accept).

**In `test_validation_gates_file_write_accepted`**, update the `mock_val.assert_called_once_with` call:

```python
    mock_val.assert_called_once_with(
        {"task_text": "Do you have product X with attr Y=3?", "task_id": "t01", "cycles": 2,
         "final_outcome": "OUTCOME_NONE_CLARIFICATION", "score": 1,
         "rule_optimization": ["Never use SELECT *"], "security_optimization": [], "prompt_optimization": []},
        injected_session_rules=["Never use SELECT *"],
        injected_prompt_addendum="",
        injected_security_gates=[],
        model="test-model",
        cfg={},
    )
```

**Replace** `patch.object(po, "validate_recommendation") as mock_val:` in `test_dry_run_skips_validation` **with** `patch.object(po, "validate_mock") as mock_val:` (the assertion `mock_val.assert_not_called()` stays unchanged).

**Remove these tests entirely** (they test BitGN harness behavior which is gone):
- `test_read_original_score_found`
- `test_read_original_score_excludes_validate_dirs`
- `test_read_original_score_not_found_returns_none`
- `test_read_original_score_no_logs_dir`
- `test_validate_recommendation_accepted`
- `test_validate_recommendation_rejected`
- `test_validate_recommendation_task_not_in_trials`
- `test_validate_recommendation_no_baseline`

Also remove `import time` and `from unittest.mock import MagicMock` if they become unused (check first).

**In `test_no_baseline_score_writes_with_warning`**: this test now uses `validate_mock` returning `(1.0, "ok")`. The "no baseline" concept is gone — `validate_mock` always returns a score. Rename and simplify:

```python
def test_validate_mock_accepted_writes_file(tmp_path):
    """validate_mock score=1.0 → file written."""
    eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed = _setup(tmp_path)
    entry = _eval_entry(rule_opts=["Never use SELECT *"])
    entry["task_id"] = "t01"
    _write_eval_log(eval_log, [entry])

    def passthrough_cluster(items, *a, **k):
        return [(rec, ent, [h]) for rec, ent, h in items]

    patches = _base_patches(eval_log, rules_dir, security_dir, prompts_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], patches[8], \
         patch.object(po, "_cluster_recs", side_effect=passthrough_cluster), \
         patch.object(po, "_synthesize_rule", return_value="Never use SELECT *"), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None), \
         patch.object(po, "_check_contradiction", return_value=None), \
         patch.object(po, "validate_mock", return_value=(1.0, "ok")):
        po.main(dry_run=False)

    assert len(list(rules_dir.glob("*.yaml"))) == 1
```

Also update `test_content_hash_dedup_per_task`: change `mock_val.call_count == 1` assertion — it now checks `validate_mock` is called once for the deduplicated cluster.

- [ ] **Step 2: Run existing tests to verify they FAIL (since main() still calls validate_recommendation)**

```bash
uv run pytest tests/test_propose_optimizations.py -v 2>&1 | tail -20
```

Some tests will now fail because `validate_mock` doesn't exist in module scope yet as a patchable attribute (it does — we added it in Task 6). The `validate_recommendation` call in `main()` is what needs changing.

- [ ] **Step 3: Update main() in propose_optimizations.py**

**Remove** the `validate_recommendation` function (lines 66–116 including the docstring).
**Remove** `read_original_score` function (lines 41–63).
**Remove** unused module-level variables: `_BITGN_URL`, `_BENCHMARK_ID`, `_BITGN_API_KEY`, `_LOGS_DIR`.

In `main()`, replace the three validation blocks (one per channel). 

**Rule channel** — replace:
```python
        else:
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[raw_rec],
                injected_prompt_addendum="",
                injected_security_gates=[],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
```

**With:**
```python
        else:
            mock_score, mock_reason = validate_mock(
                entry,
                injected_session_rules=[raw_rec],
                injected_prompt_addendum="",
                injected_security_gates=[],
                model=model,
                cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED: mock_score=1.0")
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            else:
                print(f"  → REJECTED: {mock_reason}")
```

**Security channel** — replace:
```python
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[],
                injected_prompt_addendum="",
                injected_security_gates=[injected_gate],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
```

**With:**
```python
            mock_score, mock_reason = validate_mock(
                entry,
                injected_session_rules=[],
                injected_prompt_addendum="",
                injected_security_gates=[injected_gate],
                model=model,
                cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED: mock_score=1.0")
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            else:
                print(f"  → REJECTED: {mock_reason}")
```

**Prompt channel** — replace:
```python
            original, validation = validate_recommendation(
                task_id,
                injected_session_rules=[],
                injected_prompt_addendum=raw_rec,
                injected_security_gates=[],
            )
            if original is None:
                print(f"  → WARNING: no baseline score for {task_id!r} — writing anyway")
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name} (unvalidated)")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            elif validation is None:
                print(f"  → skip (task not in trials)")
            elif validation >= original:
                print(f"  → ACCEPTED: score {original:.2f} → {validation:.2f}")
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            else:
                print(f"  → REJECTED: score {original:.2f} → {validation:.2f}")
```

**With:**
```python
            mock_score, mock_reason = validate_mock(
                entry,
                injected_session_rules=[],
                injected_prompt_addendum=raw_rec,
                injected_security_gates=[],
                model=model,
                cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED: mock_score=1.0")
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            else:
                print(f"  → REJECTED: {mock_reason}")
```

Also remove `task_id = entry.get("task_id", "")` lines in each channel loop (no longer needed).

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all tests pass. If any fail due to stale `task_id` references or `_LOGS_DIR` patches, remove those patches from failing tests.

- [ ] **Step 5: Run the complete test suite**

```bash
uv run pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "refactor(propose): replace validate_recommendation with validate_mock

Remove BitGN harness dependency from optimization validation.
Offline MockVM-based validation: 1.0=pass, 0.0=fail.
Remove read_original_score, validate_recommendation, harness imports."
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|-----------------|-----------|
| MockVM duck-type (.exec, .answer) | Task 2 |
| MockScenario Pydantic model | Task 1 |
| _MockResult with .stdout | Task 2 |
| EXPLAIN queries → "ok" | Task 2 |
| Data queries → mock_results[i] | Task 2 |
| Cycle through mock_results, clamp to last | Task 2 |
| Empty mock_results → "" | Task 2 |
| answer captured in last_answer | Task 2 |
| max_cycles parameter in run_pipeline | Task 3 |
| mock_gen.md prompt | Task 4 |
| _generate_mock_scenario LLM call | Task 5 |
| fail-open on mock_gen failure | Task 6 |
| validate_mock returns (float, str) | Task 6 |
| max_cycles=15 in validate_mock | Task 6 |
| outcome proto → string reverse map | Task 6 |
| Replace validate_recommendation in main() | Task 7 |
| Remove read_original_score | Task 7 |
| Update tests | Task 7 |

### Gaps / Issues Fixed

1. **_BITGN_URL, _BENCHMARK_ID, _BITGN_API_KEY, _LOGS_DIR**: removed in Task 7 since only `validate_recommendation` used them.
2. **task_id variable in main() loops**: removed in Task 7 (no longer passed to validation).
3. **`import time` in test file**: check if needed after removing `read_original_score` tests (it was only used in `test_read_original_score_excludes_validate_dirs`). Remove if unused.
4. **`_make_harness_mocks` helper in tests**: remove entirely in Task 7 (only used by `test_validate_recommendation_*` tests).
5. **Type consistency**: `validate_mock` returns `tuple[float, str]`; all call sites check `mock_score >= 1.0` — consistent throughout.
