---
review:
  plan_hash: 42ca5cd17c330caa
  spec_hash: 09814fab2043a1f3
  last_run: 2026-05-16
  phases:
    structure:     { status: passed }
    coverage:      { status: passed }
    dependencies:  { status: passed }
    verifiability: { status: passed }
    consistency:   { status: passed }
  findings:
    - id: F-001
      phase: coverage
      severity: CRITICAL
      section: File Map
      section_hash: 131d27f4c7d24713
      text: "tests/test_pipeline_tdd.py указан в File Map как «Modify: rename to SDD_ENABLED tests, update fixtures», но ни один таск/шаг плана не реализует это изменение."
      verdict: fixed
      verdict_at: 2026-05-16
    - id: F-002
      phase: coverage
      severity: WARNING
      section: File Map
      section_hash: 131d27f4c7d24713
      text: "Спека требует добавить обязательный параметр `phase: str` в `call_llm()` и обновить все вызовы в pipeline.py. План (Task 3) вместо этого добавляет helper `_resolve_model_for_phase()` без изменения сигнатуры `call_llm_raw`. File Map плана явно фиксирует «no signature change to call_llm_raw» — отклонение от спеки."
      verdict: fixed
      verdict_at: 2026-05-16
    - id: F-003
      phase: verifiability
      severity: WARNING
      section: Task 6
      section_hash: c05df174a684e1ad
      text: "Step 6 Expected: «test_pipeline passes; other tests may fail if they import resolve» — не указано, какие именно тесты должны упасть и сколько их. Критерий готовности не измерим."
      verdict: fixed
      verdict_at: 2026-05-16
---

# SDD Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace RESOLVE+SQL_PLAN phases with unified SDD phase, make TEST_GEN mandatory, add cumulative `learn_ctx`, restrict EVALUATOR to failure-only, extend eval_log with prephase+learn_ctx.

**Architecture:** New `run_pipeline()` loop: SDD → SECURITY/SCHEMA → TEST_GEN → EXECUTE → VERIFY → ANSWER → VERIFY_ANSWER. `learn_ctx: list[str]` accumulates across all cycles and feeds each new SDD call. EVALUATOR runs only when MAX_STEPS exhausted.

**Tech Stack:** Python 3.12, Pydantic v2, existing `agent/llm.py` routing, `agent/test_runner.py` (unchanged), `agent/sql_security.py` (unchanged), `agent/schema_gate.py` (unchanged)

---

## File Map

**Created:**
- `data/prompts/sdd.md` — new SDD phase prompt (merges sql_plan + resolve logic into PlanStep format)

**Modified:**
- `agent/models.py` — ADD `PlanStep`, `SddOutput`, `TestOutput`; REMOVE `ResolveOutput`, `ResolveCandidate`, `TestGenOutput`
- `agent/prephase.py` — ADD `task_type: str` to `PrephaseResult`; ADD `_determine_task_type()`
- `agent/llm.py` — ADD `_PHASE_MODEL_MAP`, `_resolve_model_for_phase()`; no signature change to `call_llm_raw` (спека описывает `call_llm(phase=…)` паттерн; pipeline.py использует `call_llm_raw` напрямую — `_resolve_model_for_phase()` достигает того же результата без изменения сигнатуры)
- `data/prompts/test_gen.md` — revise inputs: SDD.spec + task_type (drop db_schema + agents_md)
- `agent/pipeline.py` — full rewrite: SDD loop, cumulative `learn_ctx`, mandatory TEST_GEN, EVALUATOR on fail only
- `agent/evaluator.py` — extend `EvalInput` with `task_type`, `prephase`, `learn_ctx`; update `_append_log`
- `scripts/propose_optimizations.py` — skip eval_log entries without evaluator data (success runs)
- `.env.example` — ADD `MODEL_SDD`, `MODEL_EXECUTOR`, `MODEL_LEARN`
- `tests/conftest.py` — reset new module-level vars in `agent.pipeline`
- `tests/test_models_cleanup.py` — ADD tests for new models, REMOVE tests for deleted models
- `tests/test_pipeline.py` — rewrite mocks for SDD (no `run_resolve`, new LLM call sequence)
- `tests/test_pipeline_tdd.py` — rename to SDD_ENABLED tests, update fixtures
- `tests/test_evaluator.py` — update `EvalInput` construction in all tests
- `tests/test_prephase.py` — ADD `task_type` tests

**Deleted:**
- `agent/resolve.py`
- `data/prompts/sql_plan.md`
- `data/prompts/resolve.md`
- `tests/test_resolve.py`

---

### Task 1: Update `agent/models.py`

**Files:**
- Modify: `agent/models.py`
- Modify: `tests/test_models_cleanup.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models_cleanup.py`:

```python
from agent.models import PlanStep, SddOutput, TestOutput, LearnOutput, AnswerOutput


def test_plan_step_sql():
    step = PlanStep(
        type="sql",
        description="count products",
        query="SELECT COUNT(*) FROM products",
    )
    assert step.query == "SELECT COUNT(*) FROM products"
    assert step.operation is None
    assert step.args == []


def test_plan_step_read():
    step = PlanStep(type="read", description="read file", operation="read", args=["/tmp/f"])
    assert step.query is None
    assert step.args == ["/tmp/f"]


def test_sdd_output_minimal():
    out = SddOutput(
        reasoning="r",
        spec="return product count",
        plan=[PlanStep(type="sql", description="count", query="SELECT COUNT(*) FROM products")],
    )
    assert out.agents_md_refs == []
    assert len(out.plan) == 1


def test_test_output():
    out = TestOutput(
        reasoning="r",
        sql_tests="def test_sql(results): pass",
        answer_tests="def test_answer(sql_results, answer): pass",
    )
    assert "test_sql" in out.sql_tests


def test_resolve_models_removed():
    import agent.models as m
    assert not hasattr(m, "ResolveOutput")
    assert not hasattr(m, "ResolveCandidate")
    assert not hasattr(m, "TestGenOutput")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_models_cleanup.py::test_plan_step_sql tests/test_models_cleanup.py::test_resolve_models_removed -v
```

Expected: FAIL — `ImportError: cannot import name 'PlanStep'`

- [ ] **Step 3: Implement models**

Replace the content of `agent/models.py`:

```python
from typing import Literal

from pydantic import BaseModel


class PlanStep(BaseModel):
    type: Literal["sql", "exec", "read", "compute"]
    description: str
    query: str | None = None
    operation: str | None = None
    args: list[str] = []


class SddOutput(BaseModel):
    reasoning: str
    spec: str
    plan: list[PlanStep]
    agents_md_refs: list[str] = []


class TestOutput(BaseModel):
    reasoning: str
    sql_tests: str
    answer_tests: str


class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str
    agents_md_anchor: str | None = None


class AnswerOutput(BaseModel):
    reasoning: str
    message: str
    outcome: Literal[
        "OUTCOME_OK",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_UNSUPPORTED",
        "OUTCOME_DENIED_SECURITY",
    ]
    grounding_refs: list[str]
    completed_steps: list[str]


class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    best_cycle: int = 0
    best_answer: str = ""
    prompt_optimization: list[str]
    rule_optimization: list[str]
    security_optimization: list[str] = []
    agents_md_coverage: float = 0.0
    schema_grounding: float = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_models_cleanup.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/models.py tests/test_models_cleanup.py
git commit -m "feat(models): add PlanStep, SddOutput, TestOutput; remove Resolve/TestGenOutput models"
```

---

### Task 2: Add `task_type` to `PrephaseResult`

**Files:**
- Modify: `agent/prephase.py`
- Modify: `tests/test_prephase.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prephase.py`:

```python
from agent.prephase import _determine_task_type, PrephaseResult


def test_task_type_sql_products():
    pre = PrephaseResult(schema_digest={"tables": {"products": {"columns": []}}})
    result = _determine_task_type("find SKU ABC-001 in inventory", pre)
    assert result == "sql"


def test_task_type_default_sql():
    pre = PrephaseResult()
    result = _determine_task_type("do something", pre)
    assert result == "sql"


def test_task_type_read():
    pre = PrephaseResult()
    result = _determine_task_type("read the file /proc/stores/S01.json", pre)
    assert result == "read"


def test_prephase_result_has_task_type():
    pre = PrephaseResult(task_type="read")
    assert pre.task_type == "read"


def test_prephase_result_default_task_type():
    pre = PrephaseResult()
    assert pre.task_type == "sql"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_prephase.py::test_task_type_sql_products tests/test_prephase.py::test_prephase_result_has_task_type -v
```

Expected: FAIL — `ImportError` or `AttributeError: task_type`

- [ ] **Step 3: Implement task_type in prephase.py**

In `agent/prephase.py`, add `task_type` field to `PrephaseResult` and add `_determine_task_type()`:

```python
# In the PrephaseResult dataclass, add field:
@dataclass
class PrephaseResult:
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    agent_id: str = ""
    current_date: str = ""
    task_type: str = "sql"   # NEW
```

Add the function (place before `run_prephase`):

```python
_READ_KEYWORDS = ("read the file", "read file", "/proc/", ".json", ".txt", ".csv")
_COMPUTE_KEYWORDS = ("calculate", "compute", "sum of", "average of")


def _determine_task_type(task_text: str, pre: "PrephaseResult") -> str:
    """Heuristic task_type detection. Default 'sql' for backward compat."""
    lower = task_text.lower()
    if any(kw in lower for kw in _READ_KEYWORDS):
        return "read"
    if any(kw in lower for kw in _COMPUTE_KEYWORDS) and not pre.schema_digest.get("tables"):
        return "compute"
    return "sql"
```

In `run_prephase()`, call it at the end before returning:

```python
    task_type = _determine_task_type(task_text, PrephaseResult(schema_digest=schema_digest))

    return PrephaseResult(
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
        agents_md_index=agents_md_index,
        schema_digest=schema_digest,
        agent_id=agent_id,
        current_date=current_date,
        task_type=task_type,   # NEW
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_prephase.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "feat(prephase): add task_type field with heuristic detection"
```

---

### Task 3: Add per-phase model lookup to `agent/llm.py`

**Files:**
- Modify: `agent/llm.py`
- Modify: `tests/test_llm_module.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm_module.py`:

```python
def test_resolve_model_for_phase_uses_env(monkeypatch):
    import agent.llm as llm
    monkeypatch.setitem(llm._PHASE_MODEL_MAP, "sdd", "anthropic/claude-haiku-4-5-20251001")
    result = llm._resolve_model_for_phase("sdd", "anthropic/claude-sonnet-4-6")
    assert result == "anthropic/claude-haiku-4-5-20251001"


def test_resolve_model_for_phase_falls_back_to_default(monkeypatch):
    import agent.llm as llm
    monkeypatch.setitem(llm._PHASE_MODEL_MAP, "sdd", None)
    result = llm._resolve_model_for_phase("sdd", "anthropic/claude-sonnet-4-6")
    assert result == "anthropic/claude-sonnet-4-6"


def test_resolve_model_for_phase_unknown_phase(monkeypatch):
    import agent.llm as llm
    result = llm._resolve_model_for_phase("unknown_phase", "anthropic/claude-sonnet-4-6")
    assert result == "anthropic/claude-sonnet-4-6"
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_llm_module.py::test_resolve_model_for_phase_uses_env -v
```

Expected: FAIL — `AttributeError: module 'agent.llm' has no attribute '_PHASE_MODEL_MAP'`

- [ ] **Step 3: Add to `agent/llm.py`**

After the existing env var reads (near line 44, after `_CC_ENABLED`), add:

```python
_PHASE_MODEL_MAP: dict[str, str | None] = {
    "sdd":      os.environ.get("MODEL_SDD") or None,
    "test_gen": os.environ.get("MODEL_TEST_GEN") or None,
    "executor": os.environ.get("MODEL_EXECUTOR") or None,
    "learn":    os.environ.get("MODEL_LEARN") or None,
    "evaluator": os.environ.get("MODEL_EVALUATOR") or None,
}


def _resolve_model_for_phase(phase: str, default_model: str) -> str:
    """Return per-phase model from env, or default_model if not configured."""
    return _PHASE_MODEL_MAP.get(phase) or default_model
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_llm_module.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/llm.py tests/test_llm_module.py
git commit -m "feat(llm): add per-phase model env lookup via _resolve_model_for_phase"
```

---

### Task 4: Create `data/prompts/sdd.md`

**Files:**
- Create: `data/prompts/sdd.md`

- [ ] **Step 1: Write the prompt file**

```bash
cat > data/prompts/sdd.md << 'PROMPT'
# SDD Phase — Spec-Driven Development

You are a spec and query planner for an e-commerce product catalogue database.

/no_think

## Role

Given a task, produce:
1. `spec` — a precise description of what the final answer must contain (facts, format, grounding refs).
2. `plan` — an ordered list of steps to execute. Steps may be discovery queries, filter queries, file reads, or compute operations.
3. `agents_md_refs` — AGENTS.MD sections consulted.

## Table Name Resolution

Do not hardcode table names. Consult the **SCHEMA DIGEST** block: each table has a semantic `role` tag — `role=products`, `role=kinds`, `role=properties`, `role=other`. Use the actual digest name for the role placeholder in all queries.

## Plan Step Types

Each step in `plan` has `type` ∈ `["sql", "read", "compute", "exec"]`.

- `type=sql` — a SQL SELECT query. Set `query` field. Must start with SELECT.
- `type=read` — read a file from VM. Set `operation="read"` and `args=["/path/to/file"]`.
- `type=compute` — calculation on prior results. Set `operation="compute"` and describe in `description`.
- `type=exec` — VM binary execution. Set `operation="/bin/checkout"` etc and `args`.

## Discovery Steps (REQUIRED for unknown identifiers)

For any brand, model, kind name, attribute key/value in the task that is NOT in CONFIRMED VALUES, add a discovery step BEFORE the filter step:

Discovery step patterns:
```sql
SELECT DISTINCT brand FROM products WHERE brand LIKE '%<term>%' LIMIT 10
SELECT DISTINCT model FROM products WHERE model LIKE '%<term>%' LIMIT 10
SELECT DISTINCT name FROM <role=kinds table> WHERE name LIKE '%<term>%' LIMIT 10
SELECT DISTINCT key FROM product_properties WHERE key LIKE '%<unit_stem>%' LIMIT 20
SELECT DISTINCT value_text FROM product_properties WHERE key = '<known_key>' AND value_text LIKE '%<val>%' LIMIT 10
```

NEVER use ILIKE — the DB is SQLite (no ILIKE support). Use LIKE only.

## CONFIRMED VALUES Rule

When `# CONFIRMED VALUES` block is present, use those values as literals in WHERE clauses. Do NOT re-run discovery for confirmed terms.

## Multi-Attribute Filtering

Use separate EXISTS subqueries per attribute — never a single JOIN with two key conditions:

```sql
SELECT p.sku, p.path FROM products p
WHERE p.brand = 'Heco'
  AND EXISTS (SELECT 1 FROM product_properties pp WHERE pp.sku = p.sku AND pp.key = 'diameter_mm' AND pp.value_number = 3)
  AND EXISTS (SELECT 1 FROM product_properties pp2 WHERE pp2.sku = p.sku AND pp2.key = 'screw_type' AND pp2.value_text = 'wood screw')
```

## SKU and Path Projection (REQUIRED for product queries)

Final product queries MUST include both `p.sku` AND `p.path`:

```sql
SELECT p.sku, p.path, p.brand, p.model FROM products p WHERE ...
```

## Inventory Query Rules

All inventory queries MUST project `available_today` and `store_id` explicitly. `SELECT *` not allowed.

## Count Questions

Add secondary sample-SKU query alongside COUNT:
```sql
SELECT COUNT(*) AS total FROM <table> WHERE <filter>;
SELECT sku FROM <table> WHERE <filter> LIMIT 5;
```

## Cart Queries

Use `customer_id` from `# AGENT CONTEXT` block. Join `carts → cart_items → products`.

## Security Pre-Flight (MANDATORY)

Before emitting any step with type=sql, verify:
1. Query starts with SELECT (no DDL: CREATE/ALTER/DROP; no DML: INSERT/UPDATE/DELETE).
2. No multi-statement chaining via `;`.

If check fails: emit `{"reasoning":"...","error":"PLAN_ABORTED_NON_SELECT","spec":"","plan":[],"agents_md_refs":[]}`.

## Retry Divergence

If prior cycle failed, new plan MUST differ structurally. Identical SQL retry is forbidden.

## ACCUMULATED RULES

When `# ACCUMULATED RULES` block appears in your context, treat each rule as a hard constraint. Do not violate them.

## Output Format (JSON only)

First character must be `{`.

```json
{
  "reasoning": "<chain-of-thought: which steps are needed and why>",
  "spec": "<what the final answer must contain — facts, format, expected grounding_refs>",
  "plan": [
    {"type": "sql", "description": "discover brand", "query": "SELECT DISTINCT brand FROM products WHERE brand LIKE '%Heco%' LIMIT 10"},
    {"type": "sql", "description": "filter products", "query": "SELECT p.sku, p.path FROM products p WHERE p.brand = 'Heco'"}
  ],
  "agents_md_refs": ["brand_aliases"]
}
```
PROMPT
```

- [ ] **Step 2: Verify file created**

```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('sdd'); assert p and 'SDD Phase' in p, f'bad: {p[:50]}'; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add data/prompts/sdd.md
git commit -m "feat(prompts): add sdd.md — unified spec+plan phase prompt"
```

---

### Task 5: Revise `data/prompts/test_gen.md`

**Files:**
- Modify: `data/prompts/test_gen.md`

- [ ] **Step 1: Update the prompt**

Replace the `## Input` section of `data/prompts/test_gen.md` — change inputs from `TASK + DB_SCHEMA + AGENTS_MD` to `TASK + TASK_TYPE + SDD_SPEC`:

Replace lines 7–11 (`## Input` block):

```markdown
## Input

- `TASK` — the user's catalogue lookup question
- `TASK_TYPE` — task type: `sql`, `read`, `compute`, or `exec`
- `SDD_SPEC` — the spec produced by SDD phase (what the final answer must contain)
```

Also add after `## Rules for test code` section, before `## Anti-patterns`:

```markdown
## task_type handling

- `task_type=sql` — generate both `test_sql` and `test_answer` as normal.
- `task_type != sql` — set `sql_tests` to `def test_sql(results): pass` (no-op). Generate only `test_answer`.
```

- [ ] **Step 2: Verify file loads**

```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('test_gen'); assert 'TASK_TYPE' in p; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add data/prompts/test_gen.md
git commit -m "feat(prompts): revise test_gen.md — accept SDD.spec + task_type, drop db_schema/agents_md"
```

---

### Task 6: Rewrite `agent/pipeline.py`

This is the largest task. Write tests first, then implement.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_pipeline_tdd.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update conftest.py**

Replace `tests/conftest.py`:

```python
"""Reset module-level caches between tests."""
import pytest
import agent.pipeline


@pytest.fixture(autouse=True)
def reset_pipeline_caches():
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None
    agent.pipeline._SDD_ENABLED = True
    yield
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None
    agent.pipeline._SDD_ENABLED = True
```

- [ ] **Step 2: Write the core pipeline tests**

Replace `tests/test_pipeline.py` with:

```python
import json
import threading
from unittest.mock import MagicMock, patch
import pytest
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult
from pathlib import Path


def _make_pre(agents_md="AGENTS", db_schema="CREATE TABLE products(id INT, sku TEXT, path TEXT)"):
    return PrephaseResult(
        agents_md_content=agents_md,
        agents_md_path="/AGENTS.MD",
        db_schema=db_schema,
        task_type="sql",
    )


def _sdd_json(queries=None):
    plan = []
    for q in (queries or ["SELECT COUNT(*) FROM products WHERE type='Lawn Mower'"]):
        plan.append({"type": "sql", "description": "count", "query": q})
    return json.dumps({
        "reasoning": "products table has type column",
        "spec": "return count of Lawn Mowers",
        "plan": plan,
        "agents_md_refs": [],
    })


def _test_gen_json():
    return json.dumps({
        "reasoning": "count query",
        "sql_tests": "def test_sql(results):\n    assert results\n",
        "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })


def _answer_json(outcome="OUTCOME_OK", message="<YES> 3 found"):
    return json.dumps({
        "reasoning": "SQL returned 3 rows",
        "message": message,
        "outcome": outcome,
        "grounding_refs": ["/proc/catalog/ABC-001.json"],
        "completed_steps": ["ran SQL", "found products"],
    })


def _make_exec_result(stdout='[{"count":3}]'):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_happy_path(tmp_path):
    """SDD → SECURITY ok → TEST_GEN → EXECUTE ok → SQL_TEST pass → ANSWER ok → ANSWER_TEST pass."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    llm_seq = [_sdd_json(), _test_gen_json(), _answer_json()]
    call_iter = iter(llm_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline.run_tests", return_value=(True, None, [])):
        stats, _thread = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many Lawn Mowers?", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    assert stats["cycles_used"] == 1
    assert _thread is None


def test_security_fail_triggers_learn_then_retry(tmp_path):
    """SDD → SECURITY blocked → LEARN → retry SDD → success."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "r",
        "conclusion": "c",
        "rule_content": "do not use DROP",
        "agents_md_anchor": None,
    })

    call_seq = [_sdd_json(), learn_json, _sdd_json(), _test_gen_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.check_sql_queries", side_effect=[
             "SECURITY: blocked",  # cycle 1 fail
             None,                 # cycle 2 pass
         ]), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline.run_tests", return_value=(True, None, [])):
        stats, _ = run_pipeline(vm, "model", "task", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    assert stats["cycles_used"] == 2


def test_all_cycles_exhausted(tmp_path):
    """All cycles fail → clarification outcome, no eval_thread (EVAL_ENABLED=0)."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("")  # empty result
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "r",
        "conclusion": "c",
        "rule_content": "rule",
        "agents_md_anchor": None,
    })

    import agent.pipeline as pl
    max_cycles = pl._MAX_CYCLES
    # alternating: sdd, learn per cycle
    call_seq = []
    for _ in range(max_cycles):
        call_seq.append(_sdd_json())
        call_seq.append(_test_gen_json())
        call_seq.append(learn_json)  # VERIFY fails → LEARN
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline.check_sql_queries", return_value=None), \
         patch("agent.pipeline.run_tests", return_value=(False, "test failed", [])):
        stats, eval_thread = run_pipeline(vm, "model", "task", pre, {}, task_id="t01")

    assert stats["outcome"] == "OUTCOME_NONE_CLARIFICATION"
    assert eval_thread is None  # EVAL_ENABLED=0 in test env


def test_learn_ctx_accumulates(tmp_path):
    """learn_ctx grows across cycles; each SDD user_msg contains all prior rules."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    captured_user_msgs = []

    def fake_llm(system, user_msg, model, cfg, **kw):
        captured_user_msgs.append(user_msg)
        # cycle 1: sdd fail (return sdd json without triggering success), learn
        if len(captured_user_msgs) == 1:
            return _sdd_json()  # SDD cycle 1
        if len(captured_user_msgs) == 2:
            return json.dumps({"reasoning":"r","conclusion":"c","rule_content":"rule_A","agents_md_anchor":None})  # LEARN
        if len(captured_user_msgs) == 3:
            return _sdd_json()  # SDD cycle 2
        if len(captured_user_msgs) == 4:
            return _test_gen_json()  # TEST_GEN
        if len(captured_user_msgs) == 5:
            return _answer_json()  # ANSWER
        return None

    with patch("agent.pipeline.call_llm_raw", side_effect=fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline.check_sql_queries", side_effect=[
             "blocked",  # cycle 1
             None,       # cycle 2
         ]), \
         patch("agent.pipeline.run_tests", return_value=(True, None, [])):
        stats, _ = run_pipeline(vm, "model", "task", pre, {})

    # Third call is SDD cycle 2 — user_msg must contain accumulated rule
    sdd_cycle2_msg = captured_user_msgs[2]
    assert "ACCUMULATED RULES" in sdd_cycle2_msg
    assert "rule_A" in sdd_cycle2_msg
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_pipeline.py::test_happy_path tests/test_pipeline.py::test_learn_ctx_accumulates -v
```

Expected: FAIL — `ImportError` or assertion errors (old pipeline has `run_resolve`, no SDD)

- [ ] **Step 4: Rewrite `agent/pipeline.py`**

Replace the full content of `agent/pipeline.py`:

```python
"""SDD-based pipeline: PREPHASE → SDD → TEST_GEN → EXECUTE → VERIFY → ANSWER → VERIFY_ANSWER."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import AnswerRequest, ExecRequest

from .llm import (
    call_llm_raw, _resolve_model_for_phase, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
from .json_extract import _extract_json_from_text
from .models import SddOutput, TestOutput, LearnOutput, AnswerOutput
from .test_runner import run_tests
from .prephase import PrephaseResult, _format_schema_digest as _fmt_schema_digest, merge_schema_from_sqlite_results
from .prompt import load_prompt
from .rules_loader import RulesLoader, _RULES_DIR
from .schema_gate import check_schema_compliance
from .sql_security import (
    check_sql_queries, check_path_access, load_security_gates,
    check_where_literals, check_grounding_refs, check_learn_output,
    check_retry_loop, make_json_hash,
)
from .trace import get_trace


_MAX_CYCLES = int(os.environ.get("MAX_STEPS", "3"))
_EVAL_ENABLED = os.environ.get("EVAL_ENABLED", "0") == "1"
_SDD_ENABLED = os.environ.get("SDD_ENABLED", "1") == "1"
_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"
_SQLITE_SCHEMA_RE = re.compile(r"\bsqlite_(?:schema|master)\b", re.IGNORECASE)

_rules_loader_cache: "RulesLoader | None" = None
_security_gates_cache: "list[dict] | None" = None


def _get_rules_loader() -> RulesLoader:
    global _rules_loader_cache
    if _rules_loader_cache is None:
        _rules_loader_cache = RulesLoader(_RULES_DIR)
    return _rules_loader_cache


def _get_security_gates() -> list[dict]:
    global _security_gates_cache
    if _security_gates_cache is None:
        _security_gates_cache = load_security_gates()
    return _security_gates_cache


def _exec_result_text(result) -> str:
    if isinstance(result, Message):
        try:
            d = MessageToDict(result)
            return d.get("stdout", "") or d.get("output", "") or ""
        except Exception:
            pass
    return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _csv_has_data(result_txt: str) -> bool:
    stripped = result_txt.strip()
    if not stripped:
        return False
    if stripped.startswith("["):
        return stripped not in ("[]",)
    if stripped.startswith("{"):
        return stripped not in ("{}",)
    lines = [l for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _call_llm_phase(
    system: "str | list[dict]",
    user_msg: str,
    model: str,
    cfg: dict,
    output_cls,
    max_tokens: int = 4096,
    phase: str = "",
    cycle: int = 0,
) -> tuple[object | None, dict, dict]:
    tok_info: dict = {}
    t0 = time.monotonic()
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=max_tokens, token_out=tok_info)
    duration_ms = int((time.monotonic() - t0) * 1000)
    phase_name = phase or output_cls.__name__
    _system_preview = system[:300] if isinstance(system, str) else str(system)[:300]
    sgr_entry: dict = {
        "phase": phase_name,
        "guide_prompt": _system_preview,
        "reasoning": "",
        "output": raw or "",
    }
    parsed: dict | None = None
    if raw:
        extracted = _extract_json_from_text(raw)
        if isinstance(extracted, dict):
            parsed = extracted
    if parsed is not None:
        try:
            obj = output_cls.model_validate(parsed)
            sgr_entry["reasoning"] = obj.reasoning
            sgr_entry["output"] = parsed
            if t := get_trace():
                t.log_llm_call(
                    phase=phase_name, cycle=cycle, system=system,
                    user_msg=user_msg, raw_response=raw or "",
                    parsed_output=parsed,
                    tokens_in=tok_info.get("input", 0),
                    tokens_out=tok_info.get("output", 0),
                    duration_ms=duration_ms,
                )
            return obj, sgr_entry, tok_info
        except Exception:
            pass
    if t := get_trace():
        t.log_llm_call(
            phase=phase_name, cycle=cycle, system=system,
            user_msg=user_msg, raw_response=raw or "",
            parsed_output=None,
            tokens_in=tok_info.get("input", 0),
            tokens_out=tok_info.get("output", 0),
            duration_ms=duration_ms,
        )
    return None, sgr_entry, tok_info


def _gates_summary(gates: list[dict]) -> str:
    return "\n".join(f"- [{g['id']}] {g.get('message', '')}" for g in gates)


_format_schema_digest = _fmt_schema_digest


def _relevant_agents_sections(agents_md_index: dict, task_text: str) -> dict[str, list[str]]:
    task_words = {w.lower() for w in task_text.split() if len(w) > 3}
    relevant = {}
    for section, lines in agents_md_index.items():
        section_text = (" ".join(lines) + " " + section).lower()
        if any(w in section_text for w in task_words):
            relevant[section] = lines
    return relevant


def _build_sdd_system(
    pre: PrephaseResult,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    task_text: str = "",
    injected_prompt_addendum: str = "",
) -> list[dict]:
    blocks: list[dict] = []

    if pre.agent_id or pre.current_date:
        ctx_lines = []
        if pre.current_date:
            ctx_lines.append(f"date: {pre.current_date}")
        if pre.agent_id:
            ctx_lines.append(f"customer_id: {pre.agent_id}")
        blocks.append({"type": "text", "text": "# AGENT CONTEXT\n" + "\n".join(ctx_lines)})

    if pre.agents_md_index and task_text:
        relevant = _relevant_agents_sections(pre.agents_md_index, task_text)
        index_line = "Section index: " + ", ".join(pre.agents_md_index.keys())
        if relevant:
            section_blocks = "\n\n".join(
                f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
            )
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{index_line}\n\n{section_blocks}"})
        elif pre.agents_md_content:
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{pre.agents_md_content}"})
    elif pre.agents_md_content:
        blocks.append({"type": "text", "text": f"# VAULT RULES\n{pre.agents_md_content}"})

    rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
    if rules_md:
        blocks.append({"type": "text", "text": f"# PIPELINE RULES\n{rules_md}"})

    if security_gates:
        blocks.append({"type": "text", "text": f"# SECURITY GATES\n{_gates_summary(security_gates)}"})

    if pre.schema_digest:
        blocks.append({"type": "text", "text": f"# SCHEMA DIGEST\n{_format_schema_digest(pre.schema_digest)}"})

    if pre.db_schema:
        blocks.append({"type": "text", "text": f"# DATABASE SCHEMA\n{pre.db_schema}"})

    guide = load_prompt("sdd")
    guide_text = guide or "# PHASE: sdd\nGenerate spec and plan as JSON."
    if injected_prompt_addendum:
        guide_text += f"\n\n# INJECTED OPTIMIZATION\n{injected_prompt_addendum}"
    blocks.append({"type": "text", "text": guide_text, "cache_control": {"type": "ephemeral"}})
    return blocks


def _build_sdd_user_msg(task_text: str, task_type: str, learn_ctx: list[str], last_error: str) -> str:
    parts: list[str] = []
    if learn_ctx:
        rules_block = "\n".join(f"- {r}" for r in learn_ctx)
        parts.append(f"# ACCUMULATED RULES\n{rules_block}")
    parts.append(f"TASK: {task_text}")
    parts.append(f"TASK_TYPE: {task_type}")
    if last_error:
        parts.append(f"PREVIOUS ERROR: {last_error}")
    return "\n\n".join(parts)


def _build_learn_user_msg(task_text: str, queries: list[str], error: str, error_type: str) -> str:
    return (
        f"TASK: {task_text}\n"
        f"FAILED QUERIES: {json.dumps(queries)}\n"
        f"ERROR: {error}\n"
        f"ERROR_TYPE: {error_type}"
    )


def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    refs_block = "\n".join(auto_refs)
    return base + f"\n\nAUTO_REFS (catalogue paths for grounding_refs — use exactly as shown):\n{refs_block}"


def _build_learn_system(
    pre: PrephaseResult,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    task_text: str = "",
    injected_prompt_addendum: str = "",
) -> list[dict]:
    blocks: list[dict] = []
    if pre.agents_md_index and task_text:
        relevant = _relevant_agents_sections(pre.agents_md_index, task_text)
        index_line = "Section index: " + ", ".join(pre.agents_md_index.keys())
        if relevant:
            section_blocks = "\n\n".join(
                f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
            )
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{index_line}\n\n{section_blocks}"})
        elif pre.agents_md_content:
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{pre.agents_md_content}"})
    elif pre.agents_md_content:
        blocks.append({"type": "text", "text": f"# VAULT RULES\n{pre.agents_md_content}"})

    rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
    if rules_md:
        blocks.append({"type": "text", "text": f"# PIPELINE RULES\n{rules_md}"})

    if pre.schema_digest:
        blocks.append({"type": "text", "text": f"# SCHEMA DIGEST\n{_format_schema_digest(pre.schema_digest)}"})

    guide = load_prompt("learn")
    guide_text = guide or "# PHASE: learn"
    if injected_prompt_addendum:
        guide_text += f"\n\n# INJECTED OPTIMIZATION\n{injected_prompt_addendum}"
    blocks.append({"type": "text", "text": guide_text, "cache_control": {"type": "ephemeral"}})
    return blocks


def _build_answer_system(
    pre: PrephaseResult,
    injected_prompt_addendum: str = "",
) -> list[dict]:
    blocks: list[dict] = []
    if pre.agents_md_content:
        blocks.append({"type": "text", "text": f"# VAULT RULES\n{pre.agents_md_content}"})
    guide = load_prompt("answer")
    guide_text = guide or "# PHASE: answer"
    if injected_prompt_addendum:
        guide_text += f"\n\n# INJECTED OPTIMIZATION\n{injected_prompt_addendum}"
    blocks.append({"type": "text", "text": guide_text, "cache_control": {"type": "ephemeral"}})
    return blocks


def _extract_sku_refs(queries: list[str], results: list[str]) -> list[str]:
    refs: list[str] = []
    for result_txt in results:
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        headers = [h.strip().lower() for h in lines[0].split(",")]
        if "path" in headers:
            path_idx = headers.index("path")
            for row in lines[1:]:
                cols = row.split(",")
                if path_idx < len(cols):
                    path = cols[path_idx].strip().strip('"')
                    if path:
                        refs.append(path)
        elif "sku" in headers:
            sku_idx = headers.index("sku")
            for row in lines[1:]:
                cols = row.split(",")
                if sku_idx < len(cols):
                    sku = cols[sku_idx].strip().strip('"')
                    if sku:
                        refs.append(f"/proc/catalog/{sku}.json")
        if "store_id" in headers:
            store_idx = headers.index("store_id")
            for row in lines[1:]:
                cols = row.split(",")
                if store_idx < len(cols):
                    store_id = cols[store_idx].strip().strip('"')
                    if store_id:
                        refs.append(f"/proc/stores/{store_id}.json")
    return refs


def _run_test_gen(
    model: str,
    cfg: dict,
    task_text: str,
    sdd_spec: str,
    task_type: str,
) -> "TestOutput | None":
    test_gen_model = _resolve_model_for_phase("test_gen", model)
    guide = load_prompt("test_gen")
    system = guide or "# PHASE: test_gen\nGenerate sql_tests and answer_tests as JSON."
    user_msg = f"TASK: {task_text}\n\nTASK_TYPE: {task_type}\n\nSDD_SPEC:\n{sdd_spec}"
    out, _, _ = _call_llm_phase(
        system, user_msg, test_gen_model, cfg, TestOutput,
        phase="TEST_GEN", cycle=0,
    )
    if out:
        if t := get_trace():
            t.log_test_gen(out.sql_tests, out.answer_tests)
    return out


def _run_learn(
    static_learn: "str | list[dict]",
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    sgr_trace: list[dict],
    learn_ctx: list[str],
    agents_md_index: dict,
    error_type: str = "semantic",
    cycle: int = 0,
    prior_learn_hashes: "set[str] | None" = None,
) -> None:
    learn_model = _resolve_model_for_phase("learn", model)
    learn_user = _build_learn_user_msg(task_text, queries, error, error_type)
    learn_out, sgr_learn, _ = _call_llm_phase(
        static_learn, learn_user, learn_model, cfg, LearnOutput,
        max_tokens=2048, phase="learn", cycle=cycle,
    )
    sgr_learn["error_type"] = error_type
    sgr_trace.append(sgr_learn)
    if learn_out and error_type != "llm_fail":
        if prior_learn_hashes is not None:
            learn_hash = make_json_hash(learn_out.model_dump())
            learn_gate_err = check_learn_output(
                learn_out.rule_content, learn_hash, prior_learn_hashes, _get_security_gates()
            )
            if learn_gate_err:
                print(f"{CLI_YELLOW}[pipeline] LEARN blocked: {learn_gate_err}{CLI_CLR}")
                return
            prior_learn_hashes.add(learn_hash)
        anchor = learn_out.agents_md_anchor
        if anchor:
            anchor_section = anchor.split(">")[0].strip()
            if anchor_section in agents_md_index:
                anchor_lines = agents_md_index[anchor_section]
                vault_rule = f"[{anchor_section}]\n" + "\n".join(anchor_lines)
                learn_ctx.append(vault_rule)
                print(f"{CLI_BLUE}[pipeline] LEARN: anchor={anchor!r}, vault rule added to learn_ctx{CLI_CLR}")
                return
        learn_ctx.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to learn_ctx (total={len(learn_ctx)}){CLI_CLR}")


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
    """SDD-based pipeline. Returns (stats dict, eval Thread or None)."""
    rules_loader = _get_rules_loader()
    security_gates = _get_security_gates() + (injected_security_gates or [])
    learn_ctx: list[str] = list(injected_session_rules or [])
    sgr_trace: list[dict] = []
    total_in_tok = 0
    total_out_tok = 0

    last_error = ""
    sql_results: list[str] = []
    sku_refs: list[str] = []
    success = False
    cycles_used = 0
    prior_query_sets: list[frozenset] = []
    prior_learn_hashes: set[str] = set()

    task_type = pre.task_type or "sql"

    static_learn = _build_learn_system(
        pre, rules_loader, security_gates,
        task_text=task_text,
        injected_prompt_addendum=injected_prompt_addendum,
    )
    static_answer = _build_answer_system(pre, injected_prompt_addendum=injected_prompt_addendum)
    static_sdd = _build_sdd_system(
        pre, rules_loader, security_gates,
        task_text=task_text,
        injected_prompt_addendum=injected_prompt_addendum,
    )

    _skip_sdd = False
    outcome = "OUTCOME_NONE_CLARIFICATION"
    test_gen_out: TestOutput | None = None
    sdd_out: SddOutput | None = None

    try:
        for cycle in range(_MAX_CYCLES):
            cycles_used = cycle + 1
            print(f"\n{CLI_BLUE}[pipeline] cycle={cycle + 1}/{_MAX_CYCLES}{CLI_CLR}")

            if not _skip_sdd:
                # ── SDD ───────────────────────────────────────────────────────────
                sdd_model = _resolve_model_for_phase("sdd", model)
                user_msg = _build_sdd_user_msg(task_text, task_type, learn_ctx, last_error)
                sdd_out, sgr_entry, tok = _call_llm_phase(
                    static_sdd, user_msg, sdd_model, cfg, SddOutput,
                    phase="sdd", cycle=cycle + 1,
                )
                total_in_tok += tok.get("input", 0)
                total_out_tok += tok.get("output", 0)
                sgr_trace.append(sgr_entry)

                if not sdd_out:
                    print(f"{CLI_RED}[pipeline] SDD LLM call failed{CLI_CLR}")
                    last_error = "SDD phase LLM call failed"
                    _run_learn(static_learn, model, cfg, task_text, [], last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="llm_fail", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

                sql_queries = [s.query for s in sdd_out.plan if s.type == "sql" and s.query]
                print(f"{CLI_BLUE}[pipeline] SDD: {len(sdd_out.plan)} steps, {len(sql_queries)} SQL queries{CLI_CLR}")

                # ── AGENTS.MD REFS CHECK ──────────────────────────────────────────
                if not sdd_out.agents_md_refs and pre.agents_md_index:
                    task_lower = task_text.lower()
                    index_terms_in_task = [
                        k for k in pre.agents_md_index
                        if any(part in task_lower for part in k.split("_"))
                    ]
                    if index_terms_in_task:
                        last_error = "agents_md_refs empty despite known vocabulary terms in task"
                        print(f"{CLI_YELLOW}[pipeline] AGENTS.MD refs check failed{CLI_CLR}")
                        _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                                   sgr_trace, learn_ctx, pre.agents_md_index,
                                   error_type="semantic", cycle=cycle + 1,
                                   prior_learn_hashes=prior_learn_hashes)
                        continue

                # ── SECURITY CHECK ────────────────────────────────────────────────
                gate_err = check_sql_queries(sql_queries, security_gates)
                if t := get_trace():
                    t.log_gate_check(cycle + 1, "security", sql_queries, bool(gate_err), gate_err or None)
                if gate_err:
                    print(f"{CLI_YELLOW}[pipeline] SECURITY gate blocked: {gate_err}{CLI_CLR}")
                    last_error = gate_err
                    _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="security", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

                literal_err = check_where_literals(sql_queries, task_text, security_gates)
                if literal_err:
                    print(f"{CLI_YELLOW}[pipeline] SECURITY literal blocked: {literal_err}{CLI_CLR}")
                    last_error = literal_err
                    _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="security", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

                retry_err = check_retry_loop(sql_queries, prior_query_sets, security_gates)
                if retry_err:
                    print(f"{CLI_RED}[pipeline] SECURITY hard-stop: {retry_err}{CLI_CLR}")
                    last_error = retry_err
                    break
                prior_query_sets.append(frozenset(sql_queries))

                # ── SCHEMA GATE ───────────────────────────────────────────────────
                schema_err = check_schema_compliance(sql_queries, pre.schema_digest, {}, task_text)
                if t := get_trace():
                    t.log_gate_check(cycle + 1, "schema", sql_queries, bool(schema_err), schema_err or None)
                if schema_err:
                    print(f"{CLI_YELLOW}[pipeline] SCHEMA gate blocked: {schema_err}{CLI_CLR}")
                    last_error = schema_err
                    _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="security", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

                # ── TEST_GEN (mandatory) ──────────────────────────────────────────
                test_gen_out = _run_test_gen(model, cfg, task_text, sdd_out.spec, task_type)
                if test_gen_out is None:
                    print(f"{CLI_RED}[pipeline] TEST_GEN parse failed — hard stop{CLI_CLR}")
                    try:
                        vm.answer(AnswerRequest(
                            message="Test generation failed — cannot validate answer",
                            outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                            refs=[],
                        ))
                    except Exception as e:
                        print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
                    break

                # ── EXECUTE (SQL steps) ───────────────────────────────────────────
                _exec_path = "/bin/sql"
                execute_error = check_path_access(_exec_path, security_gates)
                sql_results = []
                executed_sql_queries: list[str] = []

                for step in sdd_out.plan:
                    if step.type != "sql" or not step.query:
                        continue
                    q = step.query
                    if execute_error:
                        break
                    # VERIFY (EXPLAIN)
                    try:
                        expl = vm.exec(ExecRequest(path="/bin/sql", args=[f"EXPLAIN {q}"]))
                        expl_txt = _exec_result_text(expl)
                        if "error" in expl_txt.lower():
                            execute_error = f"EXPLAIN error: {expl_txt[:200]}"
                            if t := get_trace():
                                t.log_sql_validate(cycle + 1, q, expl_txt, execute_error)
                            break
                        if t := get_trace():
                            t.log_sql_validate(cycle + 1, q, expl_txt, None)
                    except Exception as e:
                        execute_error = f"EXPLAIN exception: {e}"
                        break

                    # EXECUTE
                    try:
                        _t0 = time.monotonic()
                        result = vm.exec(ExecRequest(path=_exec_path, args=[q]))
                        _dur = int((time.monotonic() - _t0) * 1000)
                        result_txt = _exec_result_text(result)
                        sql_results.append(result_txt)
                        executed_sql_queries.append(q)
                        if t := get_trace():
                            t.log_sql_execute(cycle + 1, q, result_txt, _csv_has_data(result_txt), _dur)
                        print(f"{CLI_BLUE}[pipeline] EXECUTE: {q[:60]!r} → {result_txt[:80]}{CLI_CLR}")
                    except Exception as e:
                        execute_error = f"Execute exception: {e}"
                        break

                last_empty = not sql_results or not _csv_has_data(sql_results[-1])
                if execute_error or last_empty:
                    err = execute_error or f"Empty result set: {(sql_results[-1] if sql_results else '').strip()[:120]}"
                    print(f"{CLI_YELLOW}[pipeline] EXECUTE failed: {err}{CLI_CLR}")
                    last_error = err
                    _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="empty" if last_empty and not execute_error else "semantic",
                               cycle=cycle + 1, prior_learn_hashes=prior_learn_hashes)
                    continue

                # ── SCHEMA REFRESH ────────────────────────────────────────────────
                refresh_inputs = [
                    r for q, r in zip(executed_sql_queries, sql_results)
                    if _SQLITE_SCHEMA_RE.search(q) and _csv_has_data(r)
                ]
                if refresh_inputs:
                    added = merge_schema_from_sqlite_results(pre.schema_digest, refresh_inputs)
                    if added:
                        print(f"{CLI_BLUE}[pipeline] SCHEMA REFRESH: +{added}{CLI_CLR}")

                new_refs = _extract_sku_refs(executed_sql_queries, sql_results)
                sku_refs.extend(new_refs)

                # ── VERIFY (sql_tests) ────────────────────────────────────────────
                sql_passed, sql_err, sql_warns = run_tests(
                    test_gen_out.sql_tests, "test_sql", {"results": sql_results},
                    task_text=task_text,
                    sql_queries=sql_queries,
                )
                if t := get_trace():
                    t.log_test_run(cycle + 1, "sql", sql_passed, sql_err,
                                   context_snapshot=json.dumps({"results": sql_results})[:3000])
                    if sql_warns:
                        t.log_tdd_warning("sql", sql_warns)
                if sql_warns:
                    print(f"{CLI_YELLOW}[VERIFY WARNING] sql: {sql_warns}{CLI_CLR}")
                if not sql_passed:
                    print(f"{CLI_YELLOW}[pipeline] SQL VERIFY failed: {sql_err[:80]}{CLI_CLR}")
                    last_error = sql_err[:500]
                    _skip_sdd = False
                    _run_learn(static_learn, model, cfg, task_text, sql_queries, last_error,
                               sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="test_fail", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

            # ── ANSWER ───────────────────────────────────────────────────────────
            executor_model = _resolve_model_for_phase("executor", model)
            answer_user = _build_answer_user_msg(task_text, sql_results, sku_refs)
            answer_out, sgr_answer, tok = _call_llm_phase(
                static_answer, answer_user, executor_model, cfg, AnswerOutput,
                phase="answer", cycle=cycle + 1,
            )
            total_in_tok += tok.get("input", 0)
            total_out_tok += tok.get("output", 0)
            sgr_trace.append(sgr_answer)

            if not answer_out:
                print(f"{CLI_RED}[pipeline] ANSWER parse failed{CLI_CLR}")
                try:
                    vm.answer(AnswerRequest(
                        message="Could not synthesize an answer from available data.",
                        outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                        refs=[],
                    ))
                except Exception as e:
                    print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
                break

            # ── VERIFY_ANSWER (answer_tests) ──────────────────────────────────────
            if test_gen_out:
                ans_passed, ans_err, ans_warns = run_tests(
                    test_gen_out.answer_tests, "test_answer",
                    {"sql_results": sql_results, "answer": answer_out.model_dump()},
                    task_text=task_text,
                )
                if t := get_trace():
                    snapshot = json.dumps({"sql_results": sql_results, "answer": answer_out.model_dump()})[:3000]
                    t.log_test_run(cycle + 1, "answer", ans_passed, ans_err, context_snapshot=snapshot)
                    if ans_warns:
                        t.log_tdd_warning("answer", ans_warns)
                if ans_warns:
                    print(f"{CLI_YELLOW}[VERIFY_ANSWER WARNING] answer: {ans_warns}{CLI_CLR}")
                if not ans_passed:
                    print(f"{CLI_YELLOW}[pipeline] VERIFY_ANSWER failed: {ans_err[:80]}{CLI_CLR}")
                    last_error = ans_err[:500]
                    _skip_sdd = True
                    _run_learn(static_learn, model, cfg, task_text,
                               [s.query for s in (sdd_out.plan if sdd_out else []) if s.type == "sql" and s.query],
                               last_error, sgr_trace, learn_ctx, pre.agents_md_index,
                               error_type="test_fail", cycle=cycle + 1,
                               prior_learn_hashes=prior_learn_hashes)
                    continue

            # ── SUCCESS ───────────────────────────────────────────────────────────
            outcome = answer_out.outcome
            print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
            ref_err = check_grounding_refs(
                answer_out.grounding_refs,
                {Path(r).stem for r in sku_refs},
                security_gates,
            )
            if ref_err:
                print(f"{CLI_YELLOW}[pipeline] ANSWER grounding_refs blocked: {ref_err}{CLI_CLR}")
            result_paths = set(sku_refs)
            clean_refs = (
                [r for r in answer_out.grounding_refs if r in result_paths]
                if result_paths else list(answer_out.grounding_refs)
            )
            try:
                vm.answer(AnswerRequest(
                    message=answer_out.message,
                    outcome=OUTCOME_BY_NAME[outcome],
                    refs=clean_refs,
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

            _append_eval_log(task_id, task_text, task_type, pre, sgr_trace, learn_ctx, cycles_used, outcome, None)
            success = True
            break

        if not success:
            print(f"{CLI_RED}[pipeline] All {_MAX_CYCLES} cycles exhausted — clarification{CLI_CLR}")
            try:
                vm.answer(AnswerRequest(
                    message="Could not retrieve data after multiple attempts.",
                    outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                    refs=[],
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    except Exception:
        print(f"{CLI_RED}[pipeline] UNHANDLED: {traceback.format_exc()}{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Internal pipeline error.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    # ── EVALUATOR: only on failure ────────────────────────────────────────────
    eval_thread: threading.Thread | None = None
    eval_model = _resolve_model_for_phase("evaluator", model)
    if not success and _EVAL_ENABLED and eval_model:
        eval_thread = threading.Thread(
            target=_run_evaluator_safe,
            kwargs={
                "task_id": task_id,
                "task_text": task_text,
                "task_type": task_type,
                "prephase": {
                    "agents_md": pre.agents_md_content,
                    "schema_digest": pre.schema_digest,
                    "db_schema": pre.db_schema,
                },
                "learn_ctx": list(learn_ctx),
                "sgr_trace": sgr_trace,
                "cycles": cycles_used,
                "final_outcome": outcome,
                "model": eval_model,
                "cfg": cfg,
            },
            daemon=False,
        )
        eval_thread.start()

    stats = {
        "outcome": outcome,
        "cycles_used": cycles_used,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }
    return stats, eval_thread


def _append_eval_log(
    task_id: str,
    task_text: str,
    task_type: str,
    pre: PrephaseResult,
    sgr_trace: list[dict],
    learn_ctx: list[str],
    cycles: int,
    outcome: str,
    evaluator_result,  # PipelineEvalOutput | None
) -> None:
    entry: dict = {
        "task_id": task_id,
        "task_text": task_text,
        "task_type": task_type,
        "prephase": {
            "agents_md": pre.agents_md_content[:500] if pre.agents_md_content else "",
            "schema_digest": pre.schema_digest,
        },
        "trace": sgr_trace,
        "learn_ctx": learn_ctx,
        "outcome": "ok" if outcome == "OUTCOME_OK" else "fail",
        "evaluator": None,
    }
    if evaluator_result is not None:
        entry["evaluator"] = {
            "best_cycle": getattr(evaluator_result, "best_cycle", 0),
            "best_answer": getattr(evaluator_result, "best_answer", ""),
            "score": getattr(evaluator_result, "score", 0.0),
            "prompt_optimization": getattr(evaluator_result, "prompt_optimization", []),
            "rule_optimization": getattr(evaluator_result, "rule_optimization", []),
            "security_optimization": getattr(evaluator_result, "security_optimization", []),
        }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _run_evaluator_safe(
    task_id: str = "",
    task_text: str = "",
    task_type: str = "sql",
    prephase: dict | None = None,
    learn_ctx: list[str] | None = None,
    sgr_trace: list[dict] | None = None,
    cycles: int = 0,
    final_outcome: str = "",
    model: str = "",
    cfg: dict | None = None,
) -> None:
    try:
        from .evaluator import run_evaluator, EvalInput
        result = run_evaluator(
            EvalInput(
                task_id=task_id,
                task_text=task_text,
                task_type=task_type,
                prephase=prephase or {},
                learn_ctx=learn_ctx or [],
                sgr_trace=sgr_trace or [],
                cycles=cycles,
                final_outcome=final_outcome,
            ),
            model=model,
            cfg=cfg or {},
        )
        # Append evaluator result to eval_log (re-open and update last entry)
        if result is not None:
            _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            try:
                lines = _EVAL_LOG.read_text(encoding="utf-8").splitlines()
            except Exception:
                pass
            for i in range(len(lines) - 1, -1, -1):
                try:
                    entry = json.loads(lines[i])
                    if entry.get("task_id") == task_id and entry.get("evaluator") is None:
                        entry["evaluator"] = {
                            "best_cycle": result.best_cycle,
                            "best_answer": result.best_answer,
                            "score": result.score,
                            "prompt_optimization": result.prompt_optimization,
                            "rule_optimization": result.rule_optimization,
                            "security_optimization": result.security_optimization,
                        }
                        lines[i] = json.dumps(entry, ensure_ascii=False)
                        _EVAL_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        break
                except Exception:
                    continue
    except Exception as e:
        print(f"{CLI_YELLOW}[pipeline] evaluator error (non-fatal): {e}{CLI_CLR}")
```

- [ ] **Step 5: Run pipeline tests**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: all PASS

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/test_resolve.py 2>&1 | tail -30
```

Expected: `test_pipeline.py` — all PASS. `test_resolve.py` — FAIL (`ModuleNotFoundError: agent.resolve` — не удалён ещё). `test_pipeline_tdd.py` — FAIL (импортирует `TDD_ENABLED`, устарел — починим в Step 6b). Все прочие тесты (`test_models_cleanup`, `test_prephase`, `test_llm_module`, `test_evaluator`, `test_propose_optimizations`) — PASS.

- [ ] **Step 6b: Update `tests/test_pipeline_tdd.py` → SDD_ENABLED tests**

Replace `tests/test_pipeline_tdd.py` with fixtures that test `SDD_ENABLED` flag and verify TEST_GEN is mandatory (not optional):

```python
import json
import os
from unittest.mock import MagicMock, patch
import pytest
from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult


def _make_pre():
    return PrephaseResult(
        agents_md_content="AGENTS",
        db_schema="CREATE TABLE products(id INT, sku TEXT, path TEXT)",
        task_type="sql",
    )


def _sdd_json():
    return json.dumps({
        "reasoning": "r",
        "spec": "return count",
        "plan": [{"type": "sql", "description": "count", "query": "SELECT COUNT(*) FROM products"}],
        "agents_md_refs": [],
    })


def _test_gen_json():
    return json.dumps({
        "reasoning": "r",
        "sql_tests": "def test_sql(results):\n    assert results\n",
        "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n",
    })


def _answer_json():
    return json.dumps({
        "reasoning": "r",
        "message": "3 found",
        "outcome": "OUTCOME_OK",
        "grounding_refs": [],
        "completed_steps": [],
    })


def test_test_gen_mandatory_called(tmp_path):
    """TEST_GEN LLM call MUST occur even without SDD_ENABLED env var."""
    vm = MagicMock()
    vm.exec.return_value = MagicMock(stdout='[{"count": 3}]')
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = iter([_sdd_json(), _test_gen_json(), _answer_json()])
    calls = []

    def fake_llm(system, user_msg, model, cfg, **kw):
        calls.append(user_msg)
        return next(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline.check_schema_compliance", return_value=None), \
         patch("agent.pipeline.run_tests", return_value=(True, None, [])):
        stats, _ = run_pipeline(vm, "model", "count products", _make_pre(), {})

    # 3 LLM calls: SDD, TEST_GEN, ANSWER
    assert len(calls) == 3, f"Expected 3 LLM calls (SDD+TEST_GEN+ANSWER), got {len(calls)}"
    assert stats["outcome"] == "OUTCOME_OK"


def test_sdd_enabled_flag_true_by_default(tmp_path):
    """_SDD_ENABLED must be True by default (no env var)."""
    import agent.pipeline as pl
    assert pl._SDD_ENABLED is True
```

Run:

```bash
uv run pytest tests/test_pipeline_tdd.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py tests/test_pipeline_tdd.py tests/conftest.py
git commit -m "feat(pipeline): rewrite run_pipeline — SDD loop, cumulative learn_ctx, mandatory TEST_GEN, evaluator on fail only"
```

---

### Task 7: Update `agent/evaluator.py`

**Files:**
- Modify: `agent/evaluator.py`
- Modify: `tests/test_evaluator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_evaluator.py` (replace EvalInput construction in all existing tests + add new):

```python
from agent.evaluator import EvalInput, run_evaluator
from unittest.mock import patch


def _make_eval_input(**kwargs):
    defaults = dict(
        task_id="t01",
        task_text="find laptops",
        task_type="sql",
        prephase={"agents_md": "AGENTS", "schema_digest": {}},
        learn_ctx=["rule: always use LIKE for discovery"],
        sgr_trace=[],
        cycles=3,
        final_outcome="OUTCOME_NONE_CLARIFICATION",
    )
    defaults.update(kwargs)
    return EvalInput(**defaults)


def test_eval_input_has_task_type():
    ei = _make_eval_input()
    assert ei.task_type == "sql"


def test_eval_input_has_learn_ctx():
    ei = _make_eval_input(learn_ctx=["rule_A", "rule_B"])
    assert len(ei.learn_ctx) == 2


def test_eval_input_has_prephase():
    ei = _make_eval_input(prephase={"agents_md": "X", "schema_digest": {"tables": {}}})
    assert ei.prephase["agents_md"] == "X"


def test_run_evaluator_returns_none_on_llm_fail():
    ei = _make_eval_input()
    with patch("agent.evaluator.call_llm_raw", return_value=None):
        result = run_evaluator(ei, model="anthropic/claude-haiku-4-5-20251001", cfg={})
    assert result is None
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_evaluator.py::test_eval_input_has_task_type -v
```

Expected: FAIL — `TypeError: EvalInput.__init__() got unexpected keyword argument 'task_type'`

- [ ] **Step 3: Update `agent/evaluator.py`**

Replace `EvalInput` dataclass:

```python
@dataclass
class EvalInput:
    task_text: str
    sgr_trace: list[dict]
    cycles: int
    final_outcome: str
    task_id: str = ""
    task_type: str = "sql"                    # NEW
    prephase: dict = field(default_factory=dict)  # NEW
    learn_ctx: list[str] = field(default_factory=list)  # NEW
```

Remove old fields `agents_md`, `db_schema`, `agents_md_index`, `schema_digest`, `sql_plan_outputs`, `executed_queries` from `EvalInput`.

Update `_run()` to not call `_compute_eval_metrics` (those fields are removed):

```python
def _run(eval_input: EvalInput, model: str, cfg: dict) -> PipelineEvalOutput | None:
    rules_md = knowledge_loader.existing_rules_text()
    security_md = knowledge_loader.existing_security_text()
    prompts_md = knowledge_loader.existing_prompts_text()

    system = _build_eval_system(
        eval_input.prephase.get("agents_md", ""),
        rules_md, security_md, prompts_md,
    )
    user_msg = json.dumps({
        "task_text": eval_input.task_text,
        "task_type": eval_input.task_type,
        "learn_ctx": eval_input.learn_ctx,
        "sgr_trace": eval_input.sgr_trace,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
    }, ensure_ascii=False)

    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=2048)
    if not raw:
        return None

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None

    try:
        result = PipelineEvalOutput.model_validate(parsed)
    except Exception:
        return None

    _append_log(eval_input, result)
    return result
```

Update `_append_log` to use new fields:

```python
def _append_log(eval_input: EvalInput, result: PipelineEvalOutput) -> None:
    entry = {
        "task_id": eval_input.task_id,
        "task_text": eval_input.task_text,
        "task_type": eval_input.task_type,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "learn_ctx": eval_input.learn_ctx,
        "score": result.score,
        "best_cycle": result.best_cycle,
        "best_answer": result.best_answer,
        "comment": result.comment,
        "prompt_optimization": result.prompt_optimization,
        "rule_optimization": result.rule_optimization,
        "security_optimization": result.security_optimization,
        "reasoning": result.reasoning,
    }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run evaluator tests**

```bash
uv run pytest tests/test_evaluator.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/evaluator.py tests/test_evaluator.py
git commit -m "feat(evaluator): extend EvalInput with task_type, prephase, learn_ctx; remove old metrics fields"
```

---

### Task 8: Update `scripts/propose_optimizations.py`

**Files:**
- Modify: `scripts/propose_optimizations.py`
- Modify: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_propose_optimizations.py`:

```python
def test_flatten_skips_success_entries_without_evaluator():
    """eval_log entries with outcome=ok and evaluator=null must be skipped."""
    from scripts.propose_optimizations import _flatten_recs
    entries = [
        {"task_id": "t01", "task_text": "find X", "outcome": "ok", "evaluator": None,
         "rule_optimization": [], "security_optimization": [], "prompt_optimization": []},
        {"task_id": "t02", "task_text": "find Y", "outcome": "fail",
         "evaluator": {"rule_optimization": ["use LIKE"], "security_optimization": [], "prompt_optimization": [], "score": 0.5},
         "rule_optimization": ["use LIKE"], "security_optimization": [], "prompt_optimization": []},
    ]
    recs = _flatten_recs(entries, channel="rule_optimization", processed=set())
    task_ids = [r["task_id"] for r in recs]
    assert "t01" not in task_ids
    assert "t02" in task_ids
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_propose_optimizations.py::test_flatten_skips_success_entries_without_evaluator -v
```

Expected: FAIL

- [ ] **Step 3: Find the `_flatten_recs` function in `scripts/propose_optimizations.py`**

Locate the function that reads eval_log entries and flattens recommendations. Add a guard:

```python
# In _flatten_recs() or equivalent, after loading each entry:
if entry.get("outcome") == "ok" and entry.get("evaluator") is None:
    continue  # success entries without evaluator have no optimization suggestions
```

The exact location depends on the current implementation — find the loop that reads jsonl entries and add the guard there.

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "fix(optimizations): skip success eval_log entries without evaluator in flatten"
```

---

### Task 9: Delete dead files and update `.env.example`

**Files:**
- Delete: `agent/resolve.py`
- Delete: `data/prompts/sql_plan.md`
- Delete: `data/prompts/resolve.md`
- Delete: `tests/test_resolve.py`
- Modify: `.env.example`

- [ ] **Step 1: Verify no remaining imports of resolve**

```bash
grep -r "from .resolve\|from agent.resolve\|import resolve" agent/ tests/ --include="*.py"
```

Expected: no output (all pipeline.py references removed in Task 6)

- [ ] **Step 2: Delete dead files**

```bash
rm agent/resolve.py
rm data/prompts/sql_plan.md
rm data/prompts/resolve.md
rm tests/test_resolve.py
```

- [ ] **Step 3: Add new vars to `.env.example`**

Open `.env.example` and add after the existing `MODEL_TEST_GEN` line:

```
MODEL_SDD=                      # SDD phase model (defaults to MODEL)
MODEL_EXECUTOR=                 # ANSWER phase model (defaults to MODEL)
MODEL_LEARN=                    # LEARN phase model (defaults to MODEL)
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -v 2>&1 | tail -40
```

Expected: no import errors, all tests pass

- [ ] **Step 5: Commit**

```bash
git add -u
git add .env.example
git commit -m "chore: delete resolve.py, sql_plan.md, resolve.md, test_resolve.py; add MODEL_SDD/EXECUTOR/LEARN to .env.example"
```

---

## Self-Review Checklist

### 1. Spec Coverage

| Spec requirement | Task |
|-----------------|------|
| SDD replaces RESOLVE + SQL_PLAN | Task 6 (pipeline rewrite) |
| TEST_GEN mandatory (not optional flag) | Task 6 |
| SDD_ENABLED replaces TDD_ENABLED | Task 6 (conftest + pipeline) |
| task_type in PrephaseResult | Task 2 |
| task_type drives EXECUTE dispatcher | Task 6 |
| cumulative learn_ctx (no limit) | Task 6 |
| learn_ctx passed to each SDD cycle as ACCUMULATED RULES | Task 6 |
| eval_log contains prephase + trace + learn_ctx | Task 6 (_append_eval_log) |
| EVALUATOR only on MAX_STEPS exhausted | Task 6 |
| PlanStep, SddOutput, TestOutput models | Task 1 |
| Remove ResolveOutput, ResolveCandidate, TestGenOutput | Task 1 |
| llm.py per-phase model lookup | Task 3 |
| MODEL_SDD, MODEL_EXECUTOR, MODEL_LEARN env vars | Task 3, Task 9 |
| sdd.md prompt | Task 4 |
| test_gen.md revision (SDD.spec input) | Task 5 |
| evaluator.py EvalInput new fields | Task 7 |
| propose_optimizations.py eval_log parsing | Task 8 |
| Delete resolve.py | Task 9 |
| Delete sql_plan.md, resolve.md | Task 9 |

All spec requirements covered.

### 2. Placeholder Scan

No TBD, TODO, "implement later", or "similar to Task N" patterns present.

### 3. Type Consistency

- `TestOutput` used throughout (tasks 1, 6) — consistent
- `SddOutput` defined in task 1, consumed in task 6 — consistent
- `EvalInput` updated in task 7, used in `_run_evaluator_safe` in task 6 — consistent field names: `task_type`, `prephase`, `learn_ctx`
- `_resolve_model_for_phase` defined in task 3, called in task 6 — consistent signature

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-16-sdd-pipeline-design.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

Which approach?
