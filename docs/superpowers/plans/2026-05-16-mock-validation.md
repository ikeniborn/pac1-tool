---
review:
  plan_hash: e7da0bb808ee3f67
  spec_hash: 4b4c5f3126362277
  last_run: 2026-05-16
  phases:
    structure:     { status: passed }
    coverage:      { status: passed }
    dependencies:  { status: passed }
    verifiability: { status: passed }
    consistency:   { status: passed }
  section_hashes:
    "## File Map": 804b2497fb7d3f1e
    "### Task 1: MockScenario Pydantic model": af35a720ca3d45fd
    "### Task 2: MockVM": e29fb0961cf21b5b
    "### Task 3: pipeline.py — `max_cycles` and `injected_test_gen` params": cf670e8c2ad5edba
    "### Task 4: mock_gen.md prompt": de991a8e9f6d4d82
    "### Task 5: `_generate_mock_scenario` and `_MOCK_SCHEMA_DIGEST`": 42ace6c6a878f253
    "### Task 6: `validate_mock`": 7f44e9561fe71eec
    "### Task 7: `_merge_prompt`": f512f968be312df6
    "### Task 8: Modify `_write_rule` and `_write_security` to accept `verified` param": aa3e4a8f1cea4bc0
    "### Task 9: Rewrite `main()` to use `validate_mock`": 2660250820cc92bd
    "### Task 10: Remove dead code": 42b181bbd22bc8b6
    "## Self-Review Checklist": 5d0d227706f954cf
  findings:
    - id: F-001
      phase: verifiability
      severity: WARNING
      section: "### Task 1: MockScenario Pydantic model"
      section_hash: af35a720ca3d45fd
      text: "Step 1 is labeled «Write the failing test» but provides no failing test code — only runs existing tests as baseline; no new failing test exists before Step 2 implementation"
      verdict: fixed
      verdict_at: "2026-05-16"
---
# Mock Validation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace live-harness validation in `propose_optimizations.py` with offline mock validation that requires no API keys, runs entirely locally, and writes passing candidates as `verified: true`.

**Architecture:** `MockVM` duck-types `EcomRuntimeClientSync`; `run_pipeline` gets two new params (`max_cycles`, `injected_test_gen`) so mock validation can inject both; `validate_mock` runs two pipeline passes (baseline + candidate) and accepts only when candidate passes and baseline fails; `_merge_prompt` LLM-merges accepted prompt patches directly into `data/prompts/` rather than staging them in `optimized/`.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest, `agent.llm.call_llm_raw`, `agent.test_runner.run_tests`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `agent/mock_vm.py` | CREATE | `MockVM` + `_MockResult` duck-type for `EcomRuntimeClientSync` |
| `agent/models.py` | MODIFY | Add `MockScenario` Pydantic model |
| `agent/pipeline.py` | MODIFY | `max_cycles` + `injected_test_gen` params; `_use_tdd` flag replaces direct `_TDD_ENABLED` checks |
| `data/prompts/mock_gen.md` | CREATE | MOCK_GEN LLM prompt for `_generate_mock_scenario` |
| `scripts/propose_optimizations.py` | MODIFY | Add `_MOCK_SCHEMA_DIGEST`, `_generate_mock_scenario`, `validate_mock`, `_merge_prompt`; modify `_write_rule`/`_write_security` to accept `verified`; rewrite `main()`; remove harness code |
| `tests/test_mock_vm.py` | CREATE | Unit tests for `MockVM` |
| `tests/test_pipeline_mock.py` | CREATE | Tests for new `run_pipeline` params |
| `tests/test_propose_optimizations.py` | MODIFY | Remove harness tests; add tests for `validate_mock`, `_merge_prompt`, `main()` with mock validation |

---

### Task 1: MockScenario Pydantic model

**Files:**
- Modify: `agent/models.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_models_cleanup.py`:

```python
def test_mock_scenario_fields():
    from agent.models import MockScenario
    s = MockScenario(
        reasoning="r",
        mock_results=["sku,path\nLAP-001,/cat/lap"],
        answer_assertions="def test_answer(sql_results, answer): pass\n",
    )
    assert s.reasoning == "r"
    assert s.mock_results == ["sku,path\nLAP-001,/cat/lap"]
    assert "test_answer" in s.answer_assertions
```

Run to confirm failure (ImportError — `MockScenario` doesn't exist yet):

```bash
uv run pytest tests/test_models_cleanup.py::test_mock_scenario_fields -v
```

- [ ] **Step 2: Add `MockScenario` to `agent/models.py`**

Open `agent/models.py`. After the `TestGenOutput` class (line 59), add:

```python
class MockScenario(BaseModel):
    reasoning: str
    mock_results: list[str]
    answer_assertions: str
```

- [ ] **Step 3: Verify import works**

```bash
uv run python -c "from agent.models import MockScenario; print(MockScenario.model_fields.keys())"
```

Expected output: `dict_keys(['reasoning', 'mock_results', 'answer_assertions'])`

- [ ] **Step 4: Commit**

```bash
git add agent/models.py
git commit -m "feat(models): add MockScenario Pydantic model"
```

---

### Task 2: MockVM

**Files:**
- Create: `agent/mock_vm.py`
- Create: `tests/test_mock_vm.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_mock_vm.py`:

```python
import pytest
from unittest.mock import MagicMock
from agent.mock_vm import MockVM


def test_explain_always_returns_ok():
    vm = MockVM(["sku,path\nLAP-001,/cat/lap"])
    req = MagicMock()
    req.args = ["EXPLAIN SELECT sku FROM products"]
    result = vm.exec(req)
    assert result.stdout == "ok"


def test_exec_returns_first_mock_result():
    vm = MockVM(["sku,path\nLAP-001,/cat/lap", "sku,qty\nLAP-001,5"])
    req = MagicMock()
    req.args = ["SELECT sku FROM products"]
    result = vm.exec(req)
    assert result.stdout == "sku,path\nLAP-001,/cat/lap"


def test_exec_cycles_through_results():
    vm = MockVM(["row1", "row2"])
    req = MagicMock()
    req.args = ["SELECT 1"]
    vm.exec(req)  # first call → row1
    result = vm.exec(req)  # second call → row2
    assert result.stdout == "row2"


def test_exec_clamps_to_last_result():
    vm = MockVM(["row1", "row2"])
    req = MagicMock()
    req.args = ["SELECT 1"]
    vm.exec(req)
    vm.exec(req)
    result = vm.exec(req)  # third call → clamp to row2
    assert result.stdout == "row2"


def test_exec_empty_mock_results_returns_empty_string():
    vm = MockVM([])
    req = MagicMock()
    req.args = ["SELECT 1"]
    result = vm.exec(req)
    assert result.stdout == ""


def test_answer_captures_last_answer():
    vm = MockVM(["sku,path\nLAP-001,/cat/lap"])
    assert vm.last_answer is None
    req = MagicMock()
    vm.answer(req)
    assert vm.last_answer is req


def test_answer_does_not_raise():
    vm = MockVM([])
    vm.answer(MagicMock())  # no exception


def test_exec_explain_case_insensitive():
    vm = MockVM(["row1"])
    req = MagicMock()
    req.args = ["explain select 1"]
    result = vm.exec(req)
    assert result.stdout == "ok"


def test_exec_no_args_returns_mock_result():
    vm = MockVM(["row1"])
    req = MagicMock()
    req.args = []
    result = vm.exec(req)
    assert result.stdout == "row1"


def test_exec_none_args_returns_mock_result():
    vm = MockVM(["row1"])
    req = MagicMock()
    req.args = None
    result = vm.exec(req)
    assert result.stdout == "row1"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_mock_vm.py -v
```

Expected: `ImportError` — `agent/mock_vm.py` doesn't exist yet.

- [ ] **Step 3: Create `agent/mock_vm.py`**

```python
class _MockResult:
    def __init__(self, stdout: str):
        self.stdout = stdout


class MockVM:
    def __init__(self, mock_results: list[str]) -> None:
        self._results = mock_results
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

- [ ] **Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/test_mock_vm.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/mock_vm.py tests/test_mock_vm.py
git commit -m "feat(mock_vm): add MockVM duck-type for offline pipeline validation"
```

---

### Task 3: pipeline.py — `max_cycles` and `injected_test_gen` params

**Files:**
- Modify: `agent/pipeline.py`
- Create: `tests/test_pipeline_mock.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_pipeline_mock.py`:

```python
import json
from unittest.mock import MagicMock, patch
import pytest
from agent.mock_vm import MockVM
from agent.models import TestGenOutput
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult


def _pre():
    return PrephaseResult(
        agents_md_content="",
        agents_md_path="",
        db_schema="",
        schema_digest={"products": ["sku", "path"]},
    )


def _sql_json(queries=None):
    return json.dumps({
        "reasoning": "ok",
        "queries": queries or ["SELECT sku, path FROM products WHERE sku='LAP-001'"],
    })


def _answer_json():
    return json.dumps({
        "reasoning": "found",
        "message": "LAP-001 found",
        "outcome": "OUTCOME_OK",
        "grounding_refs": [],
        "completed_steps": [],
    })


def _test_gen():
    return TestGenOutput(
        reasoning="mock",
        sql_tests="def test_sql(results): pass\n",
        answer_tests="def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    )


def test_injected_test_gen_activates_tdd(tmp_path):
    """injected_test_gen activates TDD mode even when TDD_ENABLED=0."""
    mock_results = ["sku,path\nLAP-001,/cat/lap"]
    vm = MockVM(mock_results)
    pre = _pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    llm_responses = [_sql_json(), _answer_json()]
    call_count = [0]

    def fake_llm(system, user_msg, model, cfg, **kwargs):
        idx = min(call_count[0], len(llm_responses) - 1)
        call_count[0] += 1
        return llm_responses[idx]

    with patch("agent.pipeline.call_llm_raw", side_effect=fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._TDD_ENABLED", False):
        stats, _ = run_pipeline(
            vm, "test-model", "find LAP-001", pre, {},
            injected_test_gen=_test_gen(),
        )

    # vm.answer() called only via TDD path (MockVM.answer captures it)
    assert vm.last_answer is not None


def test_max_cycles_overrides_default(tmp_path):
    """max_cycles=1 stops after one cycle."""
    vm = MockVM([])
    pre = _pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_count = [0]

    def fake_llm(system, user_msg, model, cfg, **kwargs):
        call_count[0] += 1
        return json.dumps({"reasoning": "ok", "queries": ["SELECT 1"]})

    with patch("agent.pipeline.call_llm_raw", side_effect=fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._TDD_ENABLED", False):
        stats, _ = run_pipeline(
            vm, "test-model", "count products", pre, {},
            max_cycles=1,
        )

    assert stats["cycles_used"] <= 1


def test_injected_test_gen_skips_test_gen_llm_call(tmp_path):
    """When injected_test_gen is set, _run_test_gen LLM is not called."""
    vm = MockVM(["sku,path\nLAP-001,/cat/lap"])
    pre = _pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    with patch("agent.pipeline.call_llm_raw", return_value=_sql_json()) as mock_llm, \
         patch("agent.pipeline._run_test_gen") as mock_test_gen, \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._TDD_ENABLED", False):
        run_pipeline(
            vm, "test-model", "find LAP-001", pre, {},
            injected_test_gen=_test_gen(),
        )

    mock_test_gen.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_pipeline_mock.py -v
```

Expected: FAIL — `run_pipeline` doesn't accept `max_cycles` or `injected_test_gen` yet.

- [ ] **Step 3: Modify `agent/pipeline.py` — add params to `run_pipeline`**

Locate `run_pipeline` signature at line 365. Replace:

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
) -> tuple[dict, threading.Thread | None]:
```

With:

```python
def run_pipeline(
    vm,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
    task_id: str = "",
    injected_session_rules: list[str] | None = None,
    injected_prompt_addendum: str = "",
    injected_security_gates: list[dict] | None = None,
    max_cycles: int | None = None,
    injected_test_gen: "TestGenOutput | None" = None,
) -> tuple[dict, threading.Thread | None]:
```

- [ ] **Step 4: Add `_cycle_limit` and `_use_tdd` early in function body**

Find the line `rules_loader = _get_rules_loader()` (first line of function body, ~line 377). Insert before it:

```python
    _cycle_limit = max_cycles if max_cycles is not None else _MAX_CYCLES
    _use_tdd = _TDD_ENABLED or (injected_test_gen is not None)
```

- [ ] **Step 5: Replace TDD_ENABLED references and MAX_CYCLES references**

**5a.** Replace the test_gen block (~lines 401-422):

Old:
```python
    test_gen_out: TestGenOutput | None = None
    if _TDD_ENABLED:
        test_gen_out = _run_test_gen(model, cfg, task_text, pre.db_schema, pre.agents_md_content)
        if test_gen_out is None:
```

New:
```python
    test_gen_out: TestGenOutput | None = injected_test_gen
    if _use_tdd and test_gen_out is None:
        test_gen_out = _run_test_gen(model, cfg, task_text, pre.db_schema, pre.agents_md_content)
        if test_gen_out is None:
```

**5b.** Replace `for cycle in range(_MAX_CYCLES):` with `for cycle in range(_cycle_limit):`

**5c.** Replace print line `cycle + 1}/{_MAX_CYCLES}` with `cycle + 1}/{_cycle_limit}`

**5d.** Replace `if _TDD_ENABLED and test_gen_out:` with `if _use_tdd and test_gen_out:`

**5e.** Replace `if not _TDD_ENABLED:` (the `success = True; break` path) with `if not _use_tdd:`

**5f.** Replace `if _TDD_ENABLED:` (ANSWER inside loop) with `if _use_tdd:`

**5g.** Replace `All {_MAX_CYCLES} cycles exhausted` with `All {_cycle_limit} cycles exhausted`

**5h.** Replace `elif not _TDD_ENABLED:` (ANSWER outside loop) with `elif not _use_tdd:`

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_pipeline_mock.py tests/test_pipeline_tdd.py -v
```

Expected: all PASS.

- [ ] **Step 7: Run full test suite to check regressions**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: no new failures.

- [ ] **Step 8: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline_mock.py
git commit -m "feat(pipeline): add max_cycles and injected_test_gen params"
```

---

### Task 4: mock_gen.md prompt

**Files:**
- Create: `data/prompts/mock_gen.md`

- [ ] **Step 1: Create the prompt file**

Create `data/prompts/mock_gen.md`:

```markdown
# PHASE: mock_gen

You are generating mock data for offline pipeline validation.

Given a task description and the known ECOM database schema, produce:

1. `mock_results`: 1–5 CSV strings, one per expected query the pipeline will run.
   - Each string must have a header row + at least one data row.
   - Include columns that directly answer the task (e.g. `sku,path,name,price` for product lookups; `sku,quantity` for inventory checks).
   - At least one row must contain a non-trivial, task-relevant value: a real-looking SKU (e.g. `LAP-001`), a non-zero price or quantity, a non-empty path.

2. `answer_assertions`: A Python function `def test_answer(sql_results, answer): ...` that asserts:
   - `answer["outcome"] == "OUTCOME_OK"`
   - At least one task-specific identifier or numeric result is present in `answer["message"]` via an `in` check.
   - Do NOT assert on exact phrasing. Do NOT hardcode the literal task text verbatim.

Known tables and columns:
- `products`: sku, kind_id, path
- `product_properties`: product_id, key, value
- `inventory`: sku, store_id, quantity
- `kinds`: id, name
- `carts`: id, customer_id
- `cart_items`: cart_id, sku, quantity

`answer` in the test function is a dict with keys: `reasoning`, `message`, `outcome` (string literal, e.g. `"OUTCOME_OK"`), `grounding_refs`, `completed_steps`.

## Output format

Return a single JSON object:

```json
{
  "reasoning": "<why these mock results and assertions match the task>",
  "mock_results": ["header,cols\nval1,val2", "..."],
  "answer_assertions": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n    assert 'LAP-001' in answer['message']\n"
}
```
```

- [ ] **Step 2: Verify file is loadable by `agent.prompt.load_prompt`**

```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('mock_gen'); assert 'mock_gen' in p; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add data/prompts/mock_gen.md
git commit -m "feat(prompts): add mock_gen phase prompt for offline validation"
```

---

### Task 5: `_generate_mock_scenario` and `_MOCK_SCHEMA_DIGEST`

**Files:**
- Modify: `scripts/propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_propose_optimizations.py`, append at the end:

```python
def test_generate_mock_scenario_returns_mock_scenario(tmp_path):
    """Valid LLM response → MockScenario."""
    import json
    response = json.dumps({
        "reasoning": "task needs product lookup",
        "mock_results": ["sku,path\nLAP-001,/cat/lap"],
        "answer_assertions": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })
    with patch("scripts.propose_optimizations.call_llm_raw", return_value=response):
        result = po._generate_mock_scenario("Find laptop LAP-001", "test-model", {})
    from agent.models import MockScenario
    assert isinstance(result, MockScenario)
    assert result.mock_results == ["sku,path\nLAP-001,/cat/lap"]


def test_generate_mock_scenario_returns_none_on_llm_failure():
    """LLM returns None → None."""
    with patch("scripts.propose_optimizations.call_llm_raw", return_value=None):
        result = po._generate_mock_scenario("Find X", "test-model", {})
    assert result is None


def test_generate_mock_scenario_returns_none_on_invalid_json():
    """LLM returns non-JSON → None."""
    with patch("scripts.propose_optimizations.call_llm_raw", return_value="not json"):
        result = po._generate_mock_scenario("Find X", "test-model", {})
    assert result is None


def test_generate_mock_scenario_returns_none_on_invalid_schema():
    """LLM returns JSON missing required fields → None."""
    import json
    with patch("scripts.propose_optimizations.call_llm_raw",
               return_value=json.dumps({"reasoning": "x"})):
        result = po._generate_mock_scenario("Find X", "test-model", {})
    assert result is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_propose_optimizations.py::test_generate_mock_scenario_returns_mock_scenario -v
```

Expected: `AttributeError: module 'scripts.propose_optimizations' has no attribute '_generate_mock_scenario'`

- [ ] **Step 3: Add `_MOCK_SCHEMA_DIGEST` and `_generate_mock_scenario` to `propose_optimizations.py`**

After the `_LOGS_DIR` constant (line 35) add the schema digest. After `_synthesize_prompt_patch` (before `_write_rule`), add the generate function.

At top of file (after `_LOGS_DIR = ...`):

```python
_MOCK_SCHEMA_DIGEST: dict[str, list[str]] = {
    "products": ["sku", "kind_id", "path"],
    "product_properties": ["product_id", "key", "value"],
    "inventory": ["sku", "store_id", "quantity"],
    "kinds": ["id", "name"],
    "carts": ["id", "customer_id"],
    "cart_items": ["cart_id", "sku", "quantity"],
}
```

After `_synthesize_prompt_patch` function (before `_write_rule` at line ~319):

```python
def _generate_mock_scenario(task_text: str, model: str, cfg: dict):
    from agent.models import MockScenario
    from agent.prompt import load_prompt
    from agent.json_extract import _extract_json_from_text

    guide = load_prompt("mock_gen")
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

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_propose_optimizations.py -k "generate_mock" -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py
git commit -m "feat(propose): add _MOCK_SCHEMA_DIGEST and _generate_mock_scenario"
```

---

### Task 6: `validate_mock`

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_propose_optimizations.py`:

```python
def _mock_scenario():
    from agent.models import MockScenario
    return MockScenario(
        reasoning="task needs product lookup",
        mock_results=["sku,path\nLAP-001,/cat/lap"],
        answer_assertions="def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    )


def _mock_entry():
    return {
        "task_text": "Find laptop LAP-001",
        "task_id": "t01",
        "score": 0.8,
        "rule_optimization": ["Always use WHERE sku = :sku"],
    }


def test_validate_mock_fail_open_when_scenario_none():
    """_generate_mock_scenario returns None → score=1.0 (fail-open)."""
    with patch.object(po, "_generate_mock_scenario", return_value=None):
        score, reason = po.validate_mock(
            _mock_entry(), model="test-model", cfg={},
        )
    assert score == 1.0
    assert "fail open" in reason


def test_validate_mock_candidate_passes_baseline_fails():
    """candidate passes + baseline fails → score=1.0."""
    from agent.mock_vm import MockVM

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kwargs):
        if isinstance(vm, MockVM) and vm._results:
            # candidate vm gets rules injected and succeeds
            if kwargs.get("injected_session_rules"):
                vm.last_answer = MagicMock()
            # baseline vm has no rules and fails (last_answer stays None)
        return {}, None

    with patch.object(po, "_generate_mock_scenario", return_value=_mock_scenario()), \
         patch("scripts.propose_optimizations.run_pipeline", side_effect=fake_run_pipeline):
        score, reason = po.validate_mock(
            _mock_entry(),
            injected_session_rules=["Always use WHERE sku = :sku"],
            model="test-model", cfg={},
        )
    assert score == 1.0
    assert reason == "ok"


def test_validate_mock_candidate_fails():
    """candidate pipeline produces no answer → score=0.0."""
    from agent.mock_vm import MockVM

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kwargs):
        # neither vm gets last_answer set
        return {}, None

    with patch.object(po, "_generate_mock_scenario", return_value=_mock_scenario()), \
         patch("scripts.propose_optimizations.run_pipeline", side_effect=fake_run_pipeline):
        score, reason = po.validate_mock(
            _mock_entry(),
            injected_session_rules=["Always use WHERE sku = :sku"],
            model="test-model", cfg={},
        )
    assert score == 0.0
    assert "no answer" in reason


def test_validate_mock_baseline_also_passes():
    """Both baseline and candidate pass → score=0.0 (assertions too weak)."""
    from agent.mock_vm import MockVM

    def fake_run_pipeline(vm, model, task_text, pre, cfg, **kwargs):
        vm.last_answer = MagicMock()  # both pass
        return {}, None

    with patch.object(po, "_generate_mock_scenario", return_value=_mock_scenario()), \
         patch("scripts.propose_optimizations.run_pipeline", side_effect=fake_run_pipeline):
        score, reason = po.validate_mock(
            _mock_entry(),
            injected_session_rules=["Always use WHERE sku = :sku"],
            model="test-model", cfg={},
        )
    assert score == 0.0
    assert "baseline" in reason
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_propose_optimizations.py -k "validate_mock" -v
```

Expected: `AttributeError` — `validate_mock` not in module.

- [ ] **Step 3: Add `validate_mock` to `propose_optimizations.py`**

Add the import block and constant at the top-of-file level (after `_MOCK_SCHEMA_DIGEST`):

```python
# Top-level import for validate_mock — lazy imported inside function to avoid circular
```

Add the function after `_generate_mock_scenario`:

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
    from agent.mock_vm import MockVM
    from agent.models import TestGenOutput
    from agent.pipeline import run_pipeline
    from agent.prephase import PrephaseResult

    task_text = entry["task_text"]
    scenario = _generate_mock_scenario(task_text, model, cfg)
    if scenario is None:
        return 1.0, "mock_gen failed — fail open"

    pre = PrephaseResult(
        db_schema="", agents_md_content="", agents_md_index={},
        schema_digest=_MOCK_SCHEMA_DIGEST, agent_id="", current_date="",
    )
    test_gen = TestGenOutput(
        reasoning="mock validation",
        sql_tests="def test_sql(results): pass\n",
        answer_tests=scenario.answer_assertions,
    )

    baseline_vm = MockVM(scenario.mock_results)
    run_pipeline(
        baseline_vm, model, task_text, pre, cfg,
        injected_session_rules=[],
        injected_prompt_addendum="",
        injected_security_gates=[],
        max_cycles=15,
        injected_test_gen=test_gen,
    )
    baseline_pass = baseline_vm.last_answer is not None

    candidate_vm = MockVM(scenario.mock_results)
    run_pipeline(
        candidate_vm, model, task_text, pre, cfg,
        injected_session_rules=injected_session_rules or [],
        injected_prompt_addendum=injected_prompt_addendum,
        injected_security_gates=injected_security_gates or [],
        max_cycles=15,
        injected_test_gen=test_gen,
    )
    candidate_pass = candidate_vm.last_answer is not None

    if not candidate_pass:
        return 0.0, "pipeline produced no answer with candidate"
    if baseline_pass:
        return 0.0, "assertions too weak — baseline also passes without candidate"
    return 1.0, "ok"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_propose_optimizations.py -k "validate_mock" -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add validate_mock with dual-run baseline/candidate check"
```

---

### Task 7: `_merge_prompt`

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_propose_optimizations.py`:

```python
def test_merge_prompt_writes_merged_content(tmp_path):
    """LLM merge succeeds → merged file written to data/prompts/<target>."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    target = prompts_dir / "answer.md"
    target.write_text("# Answer\n\nOld rule.\n", encoding="utf-8")

    patch_result = {"target_file": "answer.md", "content": "## New Rule\nAlways include SKU."}
    merged = "# Answer\n\nOld rule.\n\n## New Rule\nAlways include SKU.\n"

    with patch.object(po, "_PROMPTS_DIR", prompts_dir), \
         patch("scripts.propose_optimizations.call_llm_raw", return_value=merged):
        dest = po._merge_prompt(patch_result, "test-model", {})

    assert dest == target
    assert "New Rule" in target.read_text()


def test_merge_prompt_creates_bak_before_overwrite(tmp_path):
    """Existing file → .bak created before overwrite."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    target = prompts_dir / "answer.md"
    original_content = "# Answer\n\nOriginal.\n"
    target.write_text(original_content, encoding="utf-8")

    patch_result = {"target_file": "answer.md", "content": "## Patch\nNew."}
    with patch.object(po, "_PROMPTS_DIR", prompts_dir), \
         patch("scripts.propose_optimizations.call_llm_raw", return_value="# Answer\nNew.\n"):
        po._merge_prompt(patch_result, "test-model", {})

    bak = target.with_suffix(target.suffix + ".bak")
    assert bak.exists()
    assert bak.read_text() == original_content


def test_merge_prompt_fallback_appends_when_llm_fails(tmp_path):
    """LLM returns None → fallback appends patch if not already present."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    target = prompts_dir / "answer.md"
    target.write_text("# Answer\n\nOld.\n", encoding="utf-8")

    patch_result = {"target_file": "answer.md", "content": "## New Rule\nAlways include SKU."}
    with patch.object(po, "_PROMPTS_DIR", prompts_dir), \
         patch("scripts.propose_optimizations.call_llm_raw", return_value=None):
        po._merge_prompt(patch_result, "test-model", {})

    content = target.read_text()
    assert "New Rule" in content


def test_merge_prompt_fallback_skips_duplicate(tmp_path):
    """Fallback: patch already present → file unchanged."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    target = prompts_dir / "answer.md"
    existing = "# Answer\n\n## New Rule\nAlways include SKU.\n"
    target.write_text(existing, encoding="utf-8")

    patch_result = {"target_file": "answer.md", "content": "## New Rule\nAlways include SKU."}
    with patch.object(po, "_PROMPTS_DIR", prompts_dir), \
         patch("scripts.propose_optimizations.call_llm_raw", return_value=None):
        po._merge_prompt(patch_result, "test-model", {})

    assert target.read_text() == existing


def test_merge_prompt_creates_file_when_not_exists(tmp_path):
    """Target file doesn't exist → created with patch content."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    patch_result = {"target_file": "new.md", "content": "## Rule\nDo X."}
    with patch.object(po, "_PROMPTS_DIR", prompts_dir), \
         patch("scripts.propose_optimizations.call_llm_raw", return_value="## Rule\nDo X.\n"):
        dest = po._merge_prompt(patch_result, "test-model", {})

    assert dest.exists()
    assert "Do X." in dest.read_text()
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_propose_optimizations.py -k "merge_prompt" -v
```

Expected: `AttributeError` — `_merge_prompt` not in module.

- [ ] **Step 3: Add `_merge_prompt` to `propose_optimizations.py`**

Add after `validate_mock`:

```python
def _merge_prompt(patch_result: dict, model: str, cfg: dict) -> Path:
    target = _PROMPTS_DIR / patch_result["target_file"]
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if existing:
        target.with_suffix(target.suffix + ".bak").write_text(existing, encoding="utf-8")
    system = (
        "Merge the patch section into the existing prompt file. "
        "Remove content that covers the same topic as the patch but with less specificity or older guidance. "
        "Remove exact or near-exact duplicate sentences. Keep all other content intact. "
        "Return only the merged file content, no extra text."
    )
    user_msg = f"EXISTING:\n{existing}\n\nPATCH:\n{patch_result['content']}"
    merged = call_llm_raw(system, user_msg, model, cfg, max_tokens=4096, plain_text=True)
    if not merged:
        if patch_result["content"].strip()[:80] not in existing:
            merged = existing.rstrip() + "\n\n" + patch_result["content"] + "\n"
        else:
            merged = existing
    target.write_text(merged, encoding="utf-8")
    return target
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_propose_optimizations.py -k "merge_prompt" -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add _merge_prompt for in-place prompt patch merging"
```

---

### Task 8: Modify `_write_rule` and `_write_security` to accept `verified` param

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Update `_write_rule` signature and body**

Locate `_write_rule` in `propose_optimizations.py` (~line 319). Replace:

```python
def _write_rule(num: int, content: str, entry: dict, raw_rec: str) -> Path:
    rule_id = f"sql-{num:03d}"
    dest = _RULES_DIR / f"{rule_id}.yaml"
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump({
            "id": rule_id, "phase": "sql_plan", "verified": False, "source": "eval",
            "content": content, "created": date.today().isoformat(),
            "eval_score": entry.get("score"),
            "raw_recommendation": raw_rec,
        }, f, allow_unicode=True, default_flow_style=False)
    return dest
```

With:

```python
def _write_rule(num: int, content: str, entry: dict, raw_rec: str, verified: bool = False) -> Path:
    rule_id = f"sql-{num:03d}"
    dest = _RULES_DIR / f"{rule_id}.yaml"
    record: dict = {
        "id": rule_id, "phase": "sql_plan", "verified": verified, "source": "eval",
        "content": content, "created": date.today().isoformat(),
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_rec,
    }
    if verified:
        record["mock_validated"] = date.today().isoformat()
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(record, f, allow_unicode=True, default_flow_style=False)
    return dest
```

- [ ] **Step 2: Update `_write_security` signature and body**

Locate `_write_security` (~line 332). Replace:

```python
def _write_security(num: int, gate_spec: dict, entry: dict, raw_rec: str) -> Path:
    gate_id = f"sec-{num:03d}"
    dest = _SECURITY_DIR / f"{gate_id}.yaml"
    record: dict = {
        "id": gate_id, "action": "block", "message": gate_spec["message"],
        "verified": False, "source": "eval", "created": date.today().isoformat(),
        "task_text": entry["task_text"][:120],
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_rec,
    }
    if gate_spec.get("pattern"):
        record["pattern"] = gate_spec["pattern"]
    if gate_spec.get("check"):
        record["check"] = gate_spec["check"]
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(record, f, allow_unicode=True, default_flow_style=False)
    return dest
```

With:

```python
def _write_security(num: int, gate_spec: dict, entry: dict, raw_rec: str, verified: bool = False) -> Path:
    gate_id = f"sec-{num:03d}"
    dest = _SECURITY_DIR / f"{gate_id}.yaml"
    record: dict = {
        "id": gate_id, "action": "block", "message": gate_spec["message"],
        "verified": verified, "source": "eval", "created": date.today().isoformat(),
        "task_text": entry["task_text"][:120],
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_rec,
    }
    if verified:
        record["mock_validated"] = date.today().isoformat()
    if gate_spec.get("pattern"):
        record["pattern"] = gate_spec["pattern"]
    if gate_spec.get("check"):
        record["check"] = gate_spec["check"]
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(record, f, allow_unicode=True, default_flow_style=False)
    return dest
```

- [ ] **Step 3: Run existing writer tests**

```bash
uv run pytest tests/test_propose_optimizations.py::test_writes_rule_yaml tests/test_propose_optimizations.py::test_writes_security_yaml -v
```

Expected: both PASS (default `verified=False` keeps old behavior).

- [ ] **Step 4: Add tests for verified=True**

Append to `tests/test_propose_optimizations.py`:

```python
def test_write_rule_verified_true_adds_mock_validated(tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    with patch.object(po, "_RULES_DIR", rules_dir):
        dest = po._write_rule(1, "Never X.", {"task_text": "t", "score": 1.0}, "raw", verified=True)
    rule = yaml.safe_load(dest.read_text())
    assert rule["verified"] is True
    assert "mock_validated" in rule


def test_write_security_verified_true_adds_mock_validated(tmp_path):
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    gate_spec = {"pattern": "DROP", "check": None, "message": "no drop"}
    with patch.object(po, "_SECURITY_DIR", security_dir):
        dest = po._write_security(1, gate_spec, {"task_text": "t", "score": 1.0}, "raw", verified=True)
    gate = yaml.safe_load(dest.read_text())
    assert gate["verified"] is True
    assert "mock_validated" in gate
```

- [ ] **Step 5: Run new tests**

```bash
uv run pytest tests/test_propose_optimizations.py -k "verified" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): add verified param to _write_rule and _write_security"
```

---

### Task 9: Rewrite `main()` to use `validate_mock`

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Rewrite `main()` in `propose_optimizations.py`**

Replace the three channel processing blocks inside `main()` (lines ~436–561) with mock-validation versions.

**Rule channel** — replace:

```python
    for raw_rec, entry, all_hashes in rule_clusters:
        task_id = entry.get("task_id", "")
        print(f"[rule] {raw_rec[:80]}...")
        content = _synthesize_rule(raw_rec, rules_md, model, cfg)
        if content is None:
            new_processed.update(all_hashes)
            print("  → skip (null/duplicate)")
            continue
        conflict = _check_contradiction(content, rules_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_RULES_DIR, "sql-")
        if dry_run:
            print(f"  → [DRY RUN] sql-{num:03d}.yaml: {content[:100]}")
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

With:

```python
    for raw_rec, entry, all_hashes in rule_clusters:
        print(f"[rule] {raw_rec[:80]}...")
        content = _synthesize_rule(raw_rec, rules_md, model, cfg)
        if content is None:
            new_processed.update(all_hashes)
            print("  → skip (null/duplicate)")
            continue
        conflict = _check_contradiction(content, rules_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_RULES_DIR, "sql-")
        if dry_run:
            print(f"  → [DRY RUN] sql-{num:03d}.yaml: {content[:100]}")
        else:
            mock_score, reason = validate_mock(
                entry,
                injected_session_rules=[raw_rec],
                injected_prompt_addendum="",
                injected_security_gates=[],
                model=model, cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED ({reason})")
                dest = _write_rule(num, content, entry, raw_rec, verified=True)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                rules_md = knowledge_loader.existing_rules_text()
            else:
                print(f"  → REJECTED ({reason})")
```

**Security channel** — replace:

```python
    for raw_rec, entry, all_hashes in security_clusters:
        task_id = entry.get("task_id", "")
        print(f"[security] {raw_rec[:80]}...")
        gate_spec = _synthesize_security_gate(raw_rec, security_md, model, cfg)
        if gate_spec is None:
            new_processed.update(all_hashes)
            print("  → skip (null/not-applicable)")
            continue
        conflict = _check_contradiction(gate_spec.get("message", ""), security_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_SECURITY_DIR, "sec-")
        if dry_run:
            print(f"  → [DRY RUN] sec-{num:03d}.yaml: {gate_spec.get('message', '')}")
        else:
            injected_gate = {
                "id": f"val-{num:03d}", "pattern": gate_spec.get("pattern", ""),
                "check_name": gate_spec.get("check", ""),
                "message": gate_spec["message"], "verified": True,
            }
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

With:

```python
    for raw_rec, entry, all_hashes in security_clusters:
        print(f"[security] {raw_rec[:80]}...")
        gate_spec = _synthesize_security_gate(raw_rec, security_md, model, cfg)
        if gate_spec is None:
            new_processed.update(all_hashes)
            print("  → skip (null/not-applicable)")
            continue
        conflict = _check_contradiction(gate_spec.get("message", ""), security_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        num = _next_num(_SECURITY_DIR, "sec-")
        if dry_run:
            print(f"  → [DRY RUN] sec-{num:03d}.yaml: {gate_spec.get('message', '')}")
        else:
            injected_gate = {
                "id": f"val-{num:03d}", "pattern": gate_spec.get("pattern", ""),
                "check_name": gate_spec.get("check", ""),
                "message": gate_spec["message"], "verified": True,
            }
            mock_score, reason = validate_mock(
                entry,
                injected_session_rules=[],
                injected_prompt_addendum="",
                injected_security_gates=[injected_gate],
                model=model, cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED ({reason})")
                dest = _write_security(num, gate_spec, entry, raw_rec, verified=True)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                security_md = knowledge_loader.existing_security_text()
            else:
                print(f"  → REJECTED ({reason})")
```

**Prompt channel** — replace:

```python
    for raw_rec, entry, all_hashes in prompt_clusters:
        task_id = entry.get("task_id", "")
        print(f"[prompt] {raw_rec[:80]}...")
        patch_result = _synthesize_prompt_patch(raw_rec, prompts_md, model, cfg)
        if patch_result is None:
            new_processed.update(all_hashes)
            print("  → skip (null/vague)")
            continue
        conflict = _check_contradiction(patch_result.get("content", ""), prompts_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        if dry_run:
            print(f"  → [DRY RUN] {patch_result['target_file']}: {patch_result['content'][:80]}")
        else:
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

With:

```python
    for raw_rec, entry, all_hashes in prompt_clusters:
        print(f"[prompt] {raw_rec[:80]}...")
        patch_result = _synthesize_prompt_patch(raw_rec, prompts_md, model, cfg)
        if patch_result is None:
            new_processed.update(all_hashes)
            print("  → skip (null/vague)")
            continue
        conflict = _check_contradiction(patch_result.get("content", ""), prompts_md, model, cfg)
        if conflict:
            print(f"  → skip (contradiction: {conflict})")
            continue
        if dry_run:
            print(f"  → [DRY RUN] {patch_result['target_file']}: {patch_result['content'][:80]}")
        else:
            mock_score, reason = validate_mock(
                entry,
                injected_session_rules=[],
                injected_prompt_addendum=raw_rec,
                injected_security_gates=[],
                model=model, cfg=cfg,
            )
            if mock_score >= 1.0:
                print(f"  → ACCEPTED ({reason})")
                dest = _merge_prompt(patch_result, model, cfg)
                print(f"  → {dest.name}")
                new_processed.update(all_hashes)
                written += 1
                prompts_md = knowledge_loader.existing_prompts_text()
            else:
                print(f"  → REJECTED ({reason})")
```

- [ ] **Step 2: Update existing main() tests in `tests/test_propose_optimizations.py`**

The tests that patch `validate_recommendation` must be updated to patch `validate_mock` instead.
Also, `test_writes_prompt_md` expects a file in `optimized/` — this must change to expect a file in `prompts_dir` directly (via `_merge_prompt`).

**Update `test_writes_rule_yaml`** — replace `patch.object(po, "validate_recommendation", ...)` with:
```python
patch.object(po, "validate_mock", return_value=(1.0, "ok")):
```
Also assert `rule["verified"] is True` (was `False`).

**Update `test_writes_security_yaml`** — same: patch `validate_mock` returning `(1.0, "ok")`. Assert `gate["verified"] is True`.

**Update `test_writes_prompt_md`** — patch `validate_mock` returning `(1.0, "ok")`. Patch `_merge_prompt` to write directly to `prompts_dir / "answer.md"`. Assert file exists in `prompts_dir` (not `prom_dir`).

**Update `test_validation_gates_file_write_accepted`** — patch `validate_mock` instead, check `mock_val` called once with correct args.

**Update `test_validation_gates_file_write_rejected`** — patch `validate_mock` returning `(0.0, "pipeline produced no answer")`.

**Update `test_dry_run_skips_validation`** — patch `validate_mock`, assert not called.

**Update `test_no_baseline_score_writes_with_warning`** — remove this test (no longer applicable: mock validation doesn't have a "no baseline" path; fail-open returns 1.0 instead).

**Remove tests for deleted functions:** `test_read_original_score_found`, `test_read_original_score_excludes_validate_dirs`, `test_read_original_score_not_found_returns_none`, `test_read_original_score_no_logs_dir`, `test_validate_recommendation_accepted`, `test_validate_recommendation_rejected`, `test_validate_recommendation_task_not_in_trials`, `test_validate_recommendation_no_baseline`.

- [ ] **Step 3: Run updated tests**

```bash
uv run pytest tests/test_propose_optimizations.py -v --tb=short
```

Expected: all PASS (the new tests from Tasks 5-8 plus updated old tests).

- [ ] **Step 4: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat(propose): rewrite main() to use validate_mock; replace harness validation"
```

---

### Task 10: Remove dead code

**Files:**
- Modify: `scripts/propose_optimizations.py`

- [ ] **Step 1: Remove dead functions and imports**

Remove from `propose_optimizations.py`:
- `read_original_score` function (lines ~41–63)
- `validate_recommendation` function (lines ~66–116)
- `_write_prompt` function (lines ~351–362)
- `_LOGS_DIR` constant (line 35)
- `_PROMPTS_OPTIMIZED_DIR` constant (line 29) — no longer used by `_merge_prompt`
- The `for _d in ...` loop that creates `_PROMPTS_OPTIMIZED_DIR` (lines ~37–38)
- `_BITGN_URL`, `_BITGN_API_KEY`, `_BENCHMARK_ID` constants (lines ~32–34) — only used by `validate_recommendation`

Keep `_PROMPTS_OPTIMIZED_DIR` creation only if `knowledge_loader.existing_prompts_text()` still reads from it (check: yes — the knowledge_loader reads optimized/ for existing prompt context). So keep `_PROMPTS_OPTIMIZED_DIR` constant and its mkdir. Remove only `_LOGS_DIR`, `_BITGN_URL`, `_BITGN_API_KEY`, `_BENCHMARK_ID`.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: no failures. Any `ImportError` for removed functions means a test still references them — fix the test.

- [ ] **Step 3: Verify dry-run still works end-to-end**

```bash
MODEL_EVALUATOR=anthropic/claude-haiku-4-5-20251001 uv run python scripts/propose_optimizations.py --dry-run
```

Expected: prints summary with no errors. (If no entries in eval_log: "No eval log at..." or "0 entry(ies) would be processed".)

- [ ] **Step 4: Commit**

```bash
git add scripts/propose_optimizations.py
git commit -m "refactor(propose): remove validate_recommendation, read_original_score, _write_prompt, harness constants"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Task(s) |
|---|---|
| MockVM duck-type | Task 2 |
| MockScenario model | Task 1 |
| run_pipeline new params | Task 3 |
| MOCK_GEN prompt | Task 4 |
| _generate_mock_scenario | Task 5 |
| validate_mock (dual-run, fail-open) | Task 6 |
| _merge_prompt (backup, fallback) | Task 7 |
| _write_rule verified=True + mock_validated | Task 8 |
| _write_security verified=True + mock_validated | Task 8 |
| main() rewrite (all 3 channels) | Task 9 |
| Remove harness code | Task 10 |
| _MOCK_SCHEMA_DIGEST | Task 5 |
| answer dict format in test assertions | Task 6 (validate_mock uses model_dump()) |

### Type Consistency

- `validate_mock` returns `tuple[float, str]` — used as `mock_score, reason = validate_mock(...)` ✓
- `_merge_prompt(patch_result, model, cfg)` signature matches call site ✓
- `_write_rule(num, content, entry, raw_rec, verified=True)` — default False preserves old tests ✓
- `MockVM.exec(req)` returns `_MockResult` with `.stdout` — matches `_exec_result_text()` in pipeline which uses `getattr(result, "stdout", "")` ✓
- `run_pipeline` type annotation for `vm` changed from `EcomRuntimeClientSync` to bare `vm` (duck-typing) ✓
