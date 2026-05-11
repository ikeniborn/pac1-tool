# SQL Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4/10 lookup failures by steering the agent to SQL-first catalogue queries and clean up dead subsystem files.

**Architecture:** Replace the file-traversal few-shot example with a SQL one; add a `## CATALOGUE STRATEGY` section to the system prompt; add `DRY_RUN` mode for cost-free task analysis; rename `MODEL_DEFAULT` → `MODEL`; delete dead test files and data directories.

**Tech Stack:** Python 3.12, pytest, uv, standard library (json, os, pathlib, datetime)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `agent/prephase.py` | Replace few-shot; add `sql_schema` to `PrephaseResult` |
| Modify | `agent/prompt.py` | Replace `## Catalogue lookup` with `## CATALOGUE STRATEGY` |
| Modify | `agent/orchestrator.py` | `DRY_RUN` mode; `MODEL_DEFAULT` → `MODEL`; `task_id` param |
| Modify | `main.py` | Pass `task_id` to `run_agent()`; `MODEL_DEFAULT` → `MODEL` |
| Modify | `.env.example` | Clean up dead vars; rename `MODEL_DEFAULT` → `MODEL` |
| Delete | `agent/contract_models.py` | Not imported anywhere |
| Delete | `tests/` (many files) | Reference removed modules |
| Delete | `tests/agents/` | Agent-level integration tests for removed subsystems |
| Delete | `tests/regression/` | Regression tests for removed subsystems |
| Delete | `data/default_contracts/` | Contract system removed |
| Delete | `data/prompts/` | DSPy prompt templates, no DSPy |
| Delete | `data/wiki/` | Wiki system not in agent |
| Create | `tests/test_sql_adaptation.py` | Tests for Tasks 2–5 |

---

### Task 1: Delete obsolete files

No TDD needed — pure deletion.

**Files to delete:**

- [ ] **Step 1: Delete obsolete test files (keep list)**

```bash
cd tests
# Keep: conftest.py, test_json_extraction.py, test_dispatch_transient.py,
#        test_loop_json_parse.py, test_prephase_vault_date.py
rm -rf agents/ regression/
rm -f test_capability_cache.py \
      test_classifier.py \
      test_contract_dspy.py test_contract_files.py test_contract_models.py \
      test_contract_monitor.py test_contract_phase.py \
      test_distill_contracts.py \
      test_dspy_lm_think_strip.py \
      test_evaluator_contract.py test_evaluator.py test_evaluator_wiki_quality.py \
      test_lifecycle.py \
      test_log_compaction.py \
      test_loop_agent_wiring.py test_loop_mutation_gate.py \
      test_maintenance_candidates.py test_maintenance_distill.py \
      test_maintenance_health.py test_maintenance_purge.py \
      test_optimization_backend_select.py test_optimization_budget.py \
      test_optimization_feedback.py test_optimization_smoke.py \
      test_optimization_split.py \
      test_postrun_outcome_gate.py \
      test_security_gates.py \
      test_task_types_aspects.py test_task_types_registry.py \
      test_visualize_graph.py \
      test_wiki_aspect_synthesis.py test_wiki_constraints.py \
      test_wiki_error_ingest.py test_wiki_format_fragment.py \
      test_wiki_graph_dedup.py test_wiki_graph_edges.py \
      test_wiki_graph_scoring.py test_wiki_graph_stemmed_dedup.py \
      test_wiki_incremental.py test_wiki_meta.py test_wiki_negatives.py \
      test_wiki_pages_lint.py test_wiki_page_soft_limit.py \
      test_wiki_promote_normal.py test_wiki_quality_header.py \
      test_wiki_sanitize.py
```

- [ ] **Step 2: Delete dead agent module and data directories**

```bash
rm agent/contract_models.py
rm -rf data/default_contracts/ data/prompts/ data/wiki/
```

- [ ] **Step 3: Verify kept tests still pass**

```bash
uv run python -m pytest tests/ -v
```

Expected: 4 test files collected, all pass (or skip if deps missing). Zero import errors.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete dead subsystems — contracts, DSPy, wiki, routing tests"
```

---

### Task 2: Add `sql_schema` to `PrephaseResult` and replace few-shot example

**Files:**
- Modify: `agent/prephase.py`
- Create: `tests/test_sql_adaptation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_sql_adaptation.py`:

```python
"""Tests for SQL-first few-shot and prephase sql_schema field."""


def test_few_shot_user_is_sql_task():
    from agent.prephase import _FEW_SHOT_USER
    assert "lawn mower" in _FEW_SHOT_USER.lower() or "catalogue" in _FEW_SHOT_USER.lower()
    assert "notes" not in _FEW_SHOT_USER.lower(), "few-shot must not reference notes folder"


def test_few_shot_assistant_uses_sql_exec():
    from agent.prephase import _FEW_SHOT_ASSISTANT
    assert '"tool":"exec"' in _FEW_SHOT_ASSISTANT.replace(" ", "")
    assert "/bin/sql" in _FEW_SHOT_ASSISTANT
    assert "EXPLAIN" in _FEW_SHOT_ASSISTANT
    assert "list" not in _FEW_SHOT_ASSISTANT.lower().split('"tool"')[0]


def test_prephase_result_has_sql_schema_field():
    from agent.prephase import PrephaseResult
    r = PrephaseResult(log=[], preserve_prefix=[])
    assert hasattr(r, "sql_schema")
    assert r.sql_schema == ""
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest tests/test_sql_adaptation.py::test_few_shot_user_is_sql_task \
    tests/test_sql_adaptation.py::test_few_shot_assistant_uses_sql_exec \
    tests/test_sql_adaptation.py::test_prephase_result_has_sql_schema_field -v
```

Expected: FAIL (`notes` still in few-shot user, `sql_schema` field missing)

- [ ] **Step 3: Replace few-shot constants in `agent/prephase.py` (lines 45–51)**

Replace:
```python
_FEW_SHOT_USER = "Example: what files are in the notes folder?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"listing notes folder to identify files",'
    '"plan_remaining_steps_brief":["list /notes","act on result"],'
    '"done_operations":[],"task_completed":false,'
    '"function":{"tool":"list","path":"/notes"}}'
)
```

With:
```python
_FEW_SHOT_USER = "Example: How many catalogue products are Lawn Mower?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"validating SQL syntax before executing count",'
    '"plan_remaining_steps_brief":["EXPLAIN query","SELECT COUNT","report result"],'
    '"done_operations":[],"task_completed":false,'
    '"function":{"tool":"exec","path":"/bin/sql",'
    '"args":["EXPLAIN SELECT COUNT(*) FROM products WHERE type=\'Lawn Mower\'"],'
    '"stdin":""}}'
)
```

- [ ] **Step 4: Add `sql_schema` field to `PrephaseResult` dataclass (line 15)**

Replace:
```python
@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
```

With:
```python
@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    sql_schema: str = ""
```

- [ ] **Step 5: Store `sql_schema` when fetched in `run_prephase` (around line 155–165)**

After the existing `sql_schema = schema_result.stdout.strip()` assignment (line ~157), the variable is already populated. At the end of `run_prephase`, update the `return` statement to pass it through.

Replace the final `return` statement (currently line 206):
```python
    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
    )
```

With:
```python
    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        sql_schema=sql_schema,
    )
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
uv run python -m pytest tests/test_sql_adaptation.py::test_few_shot_user_is_sql_task \
    tests/test_sql_adaptation.py::test_few_shot_assistant_uses_sql_exec \
    tests/test_sql_adaptation.py::test_prephase_result_has_sql_schema_field -v
```

Expected: PASS (3/3)

- [ ] **Step 7: Run full test suite**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add agent/prephase.py tests/test_sql_adaptation.py
git commit -m "feat: replace file-traversal few-shot with SQL example; add sql_schema to PrephaseResult"
```

---

### Task 3: Replace `## Catalogue lookup` with `## CATALOGUE STRATEGY` in system prompt

**Files:**
- Modify: `agent/prompt.py`
- Modify: `tests/test_sql_adaptation.py` (append tests)

- [ ] **Step 1: Write failing tests — append to `tests/test_sql_adaptation.py`**

```python
def test_system_prompt_has_catalogue_strategy_section():
    from agent.prompt import SYSTEM_PROMPT
    assert "## CATALOGUE STRATEGY" in SYSTEM_PROMPT


def test_catalogue_strategy_has_hard_rule():
    from agent.prompt import SYSTEM_PROMPT
    assert "list" in SYSTEM_PROMPT and "/proc/catalog" in SYSTEM_PROMPT
    # Hard rule: no list/find/read on /proc/catalog
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    assert idx != -1
    section = SYSTEM_PROMPT[idx:]
    assert "HARD RULE" in section or "Never use" in section


def test_catalogue_strategy_has_step_order():
    from agent.prompt import SYSTEM_PROMPT
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    section = SYSTEM_PROMPT[idx:]
    assert "EXPLAIN" in section
    assert "DISTINCT" in section


def test_catalogue_strategy_has_question_patterns():
    from agent.prompt import SYSTEM_PROMPT
    idx = SYSTEM_PROMPT.find("## CATALOGUE STRATEGY")
    section = SYSTEM_PROMPT[idx:]
    assert "COUNT(*)" in section
    assert "LIMIT 1" in section
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest tests/test_sql_adaptation.py -k "catalogue_strategy" -v
```

Expected: FAIL (`## CATALOGUE STRATEGY` not in SYSTEM_PROMPT)

- [ ] **Step 3: Replace `## Catalogue lookup` section in `agent/prompt.py`**

Replace the existing `## Catalogue lookup` block (lines 48–65).

> **Note for executor**: In `prompt.py` the SYSTEM_PROMPT triple-quoted string closes on the same line as the last sentence: `...your response message."""`. Include this closing `"""` in **both** the old and new strings passed to the Edit tool so the string stays valid.

Old string (include the closing `"""`):
```
## Catalogue lookup

Use `/bin/sql` to query the catalogue. The SQL schema is provided in your context.
SQL is the authoritative source — once SQL confirms a product exists, call report_completion immediately.
Do NOT read catalog files to verify SQL results. Do NOT list directories.

**SQL column mapping**: products table has separate columns: `brand`, `series`, `model`, `name`.
When the task mentions a product line name (e.g. "Rugged 3EY-11K"), search in `model` column, not `series`.

**NOT FOUND rule**: After 2 failed SQL attempts that return no matching rows, try one final broad query.
If still no match, call report_completion with message containing `<NO> Product not found in catalogue` and `grounding_refs=[]`.

**grounding_refs is MANDATORY** — include every file that contributed to the answer.
For catalogue items: grounding_refs must be `/proc/catalog/{sku}.json` using the SKU from SQL results.
Example: SQL returns `sku=PNT-2SB09GHC` → grounding_refs=["/proc/catalog/PNT-2SB09GHC.json"]
NEVER use the `path` column from SQL — always construct the path as `/proc/catalog/{sku}.json`.

When answering yes/no questions, include <YES> or <NO> in your response message."""
```

New string (include the closing `"""`):
```
## CATALOGUE STRATEGY

**HARD RULE**: Never use `list`, `find`, or `read` on `/proc/catalog/`. SQL ONLY via `/bin/sql`.

**Step order** (MAX_STEPS=5 — every step counts):
1. Check AGENTS.MD — if it defines exact values for the needed attribute, use them directly in SQL
2. If AGENTS.MD is silent on an attribute → `SELECT DISTINCT <attr> FROM products WHERE <narrowing conditions> LIMIT 50`
3. `EXPLAIN SELECT ...` — validate syntax before execution (catches typos at zero cost)
4. `SELECT ...` — retrieve the answer
5. `report_completion` immediately — do NOT read catalog files to confirm SQL results

**Question patterns**:
- `How many X?` → `SELECT COUNT(*) FROM products WHERE type='X'`
- `Do you have X?` → `SELECT 1 FROM products WHERE brand=? AND type=? LIMIT 1`

**Never assume attribute values** — verify from AGENTS.MD or DISTINCT first.

**SQL column mapping**: products table has separate columns: `brand`, `series`, `model`, `name`.
When the task mentions a product line name (e.g. "Rugged 3EY-11K"), search in `model` column, not `series`.

**NOT FOUND rule**: After 2 failed SQL attempts returning no rows, try one final broad query.
If still no match → `report_completion` with `<NO> Product not found in catalogue` and `grounding_refs=[]`.

**grounding_refs is MANDATORY** — include every file that contributed to the answer.
For catalogue items: grounding_refs must be `/proc/catalog/{sku}.json` using the SKU from SQL results.
Example: SQL returns `sku=PNT-2SB09GHC` → grounding_refs=["/proc/catalog/PNT-2SB09GHC.json"]
NEVER use the `path` column from SQL — always construct the path as `/proc/catalog/{sku}.json`.

When answering yes/no questions, include <YES> or <NO> in your response message."""
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run python -m pytest tests/test_sql_adaptation.py -k "catalogue_strategy" -v
```

Expected: PASS (4/4)

- [ ] **Step 5: Run full test suite**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add agent/prompt.py tests/test_sql_adaptation.py
git commit -m "feat: add CATALOGUE STRATEGY section with step order and question patterns"
```

---

### Task 4: Add `DRY_RUN` mode to `agent/orchestrator.py` + wire `task_id` in `main.py`

**Files:**
- Modify: `agent/orchestrator.py`
- Modify: `main.py`
- Modify: `tests/test_sql_adaptation.py` (append tests)

- [ ] **Step 1: Write failing tests — append to `tests/test_sql_adaptation.py`**

```python
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_pre(sql_schema: str = "CREATE TABLE products (sku TEXT)", agents_md: str = "# Agents"):
    pre = MagicMock()
    pre.sql_schema = sql_schema
    pre.agents_md_content = agents_md
    pre.log = [{"role": "user", "content": f"TASK: test\n{agents_md}"}]
    pre.preserve_prefix = pre.log[:]
    return pre


def test_dry_run_returns_dry_run_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    monkeypatch.setattr(orch, "_DRY_RUN_LOG", tmp_path / "dry_run_analysis.jsonl")
    mock_pre = _make_mock_pre()

    with patch("agent.orchestrator.EcomRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre):
        stats = orch.run_agent({}, "http://test", "test task", task_id="t01")

    assert stats["outcome"] == "DRY_RUN"
    assert stats["input_tokens"] == 0
    assert stats["output_tokens"] == 0


def test_dry_run_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    log_path = tmp_path / "dry_run_analysis.jsonl"
    monkeypatch.setattr(orch, "_DRY_RUN_LOG", log_path)
    mock_pre = _make_mock_pre(sql_schema="CREATE TABLE products (sku TEXT)", agents_md="# AG")

    with patch("agent.orchestrator.EcomRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre):
        orch.run_agent({}, "http://test", "task text here", task_id="t42")

    assert log_path.exists()
    entry = json.loads(log_path.read_text().strip())
    assert entry["task_id"] == "t42"
    assert entry["task_text"] == "task text here"
    assert entry["sql_schema"] == "CREATE TABLE products (sku TEXT)"
    assert entry["agents_md"] == "# AG"
    assert "timestamp" in entry


def test_normal_mode_calls_loop(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("MODEL", "test-model")

    import importlib
    import agent.orchestrator as orch
    importlib.reload(orch)

    mock_pre = _make_mock_pre()
    mock_stats = {"input_tokens": 10, "output_tokens": 5}

    with patch("agent.orchestrator.EcomRuntimeClientSync"), \
         patch("agent.orchestrator.run_prephase", return_value=mock_pre), \
         patch("agent.orchestrator.run_loop", return_value=mock_stats) as mock_loop:
        orch.run_agent({}, "http://test", "normal task")

    mock_loop.assert_called_once()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run python -m pytest tests/test_sql_adaptation.py -k "dry_run" -v
```

Expected: FAIL (no `_DRY_RUN`, no `task_id` param, no `_DRY_RUN_LOG`)

- [ ] **Step 3: Rewrite `agent/orchestrator.py`**

Replace the entire file:

```python
"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.loop import run_loop

_MODEL = os.environ.get("MODEL", "")
_DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
_DRY_RUN_LOG = Path(__file__).parent.parent / "data" / "dry_run_analysis.jsonl"


def _write_dry_run(task_id: str, task_text: str, pre) -> None:
    entry = {
        "task_id": task_id,
        "task_text": task_text,
        "agents_md": pre.agents_md_content,
        "sql_schema": pre.sql_schema,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _DRY_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_DRY_RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}

    pre = run_prephase(vm, task_text)

    if _DRY_RUN:
        _write_dry_run(task_id, task_text, pre)
        return {
            "model_used": model,
            "task_type": "lookup",
            "builder_used": False,
            "builder_in_tok": 0,
            "builder_out_tok": 0,
            "builder_addendum": "",
            "contract_rounds_taken": 0,
            "contract_is_default": True,
            "eval_rejection_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "outcome": "DRY_RUN",
        }

    stats = run_loop(vm, model, task_text, pre, cfg)

    stats["model_used"] = model
    stats["task_type"] = "lookup"
    stats["builder_used"] = False
    stats["builder_in_tok"] = 0
    stats["builder_out_tok"] = 0
    stats["builder_addendum"] = ""
    stats["contract_rounds_taken"] = 0
    stats["contract_is_default"] = True
    stats["eval_rejection_count"] = 0
    return stats
```

- [ ] **Step 4: Wire `task_id` in `main.py` (line 151)**

Replace:
```python
            token_stats = run_agent(MODEL_CONFIGS, trial.harness_url, trial.instruction)
```

With:
```python
            token_stats = run_agent(MODEL_CONFIGS, trial.harness_url, trial.instruction, task_id=task_id)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run python -m pytest tests/test_sql_adaptation.py -k "dry_run or normal_mode" -v
```

Expected: PASS (3/3)

- [ ] **Step 6: Run full test suite**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add agent/orchestrator.py main.py tests/test_sql_adaptation.py
git commit -m "feat: add DRY_RUN mode — prephase only, writes dry_run_analysis.jsonl"
```

---

### Task 5: Rename `MODEL_DEFAULT` → `MODEL` in `orchestrator.py` and `main.py`

Note: `orchestrator.py` was already updated in Task 4 to use `MODEL`. This task covers `main.py` (2 occurrences).

**Files:**
- Modify: `main.py`
- Modify: `tests/test_sql_adaptation.py` (append test)

- [ ] **Step 1: Write failing test — append to `tests/test_sql_adaptation.py`**

```python
def test_model_env_var_name_is_MODEL():
    """main.py must read MODEL, not MODEL_DEFAULT."""
    import ast
    root = Path(__file__).parent.parent
    src = (root / "main.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "MODEL_DEFAULT":
            raise AssertionError("main.py still references MODEL_DEFAULT literal")
```

- [ ] **Step 2: Run test — verify it fails**

```bash
uv run python -m pytest tests/test_sql_adaptation.py::test_model_env_var_name_is_MODEL -v
```

Expected: FAIL (MODEL_DEFAULT appears in main.py)

- [ ] **Step 3: Replace `MODEL_DEFAULT` in `main.py` — line 30**

Replace:
```python
    model = os.getenv("MODEL_DEFAULT") or _dotenv.get("MODEL_DEFAULT") or "unknown"
```

With:
```python
    model = os.getenv("MODEL") or _dotenv.get("MODEL") or "unknown"
```

- [ ] **Step 4: Replace `MODEL_DEFAULT` in `main.py` — line 123**

Replace:
```python
_model_default = _require_env("MODEL_DEFAULT")
print(f"[MODEL] default={_model_default}")
```

With:
```python
_model_default = _require_env("MODEL")
print(f"[MODEL] default={_model_default}")
```

- [ ] **Step 5: Run test — verify it passes**

```bash
uv run python -m pytest tests/test_sql_adaptation.py::test_model_env_var_name_is_MODEL -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```bash
uv run python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_sql_adaptation.py
git commit -m "feat: rename MODEL_DEFAULT → MODEL in main.py"
```

---

### Task 6: Update `.env.example`

No TDD — config file cleanup.

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Rewrite `.env.example`**

Replace the entire file with:

```bash
# pac1-py/.env — не коммитить в git. Credentials → .secrets.
# Приоритет: env > .secrets > .env

# ─── Общее ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO                       # DEBUG → логировать RAW LLM-ответы
TZ=                                  # пусто = системный

# ─── Benchmark ──────────────────────────────────────────────────────────────
BENCHMARK_HOST=https://api.bitgn.com
BENCHMARK_ID=bitgn/pac1-dev
BITGN_RUN_NAME=pac1-dev-your-name
BITGN_API_KEY=                       # API-ключ для авторизации на harness
TASK_TIMEOUT_S=300
PARALLEL_TASKS=1
MAX_STEPS=5

# ─── Модель ─────────────────────────────────────────────────────────────────
MODEL=anthropic/claude-sonnet-4-6

# ─── Режим отладки ──────────────────────────────────────────────────────────
DRY_RUN=0                            # 1 = только prephase, нет LLM-вызовов, пишет data/dry_run_analysis.jsonl

# ─── Ollama ─────────────────────────────────────────────────────────────────
# Модели формата name:tag (без слэша) → Ollama. Примеры: qwen3.5:cloud.
OLLAMA_BASE_URL=http://localhost:11434/v1

# ─── Claude Code tier (опционально) ─────────────────────────────────────────
# Активируется префиксом claude-code/* в MODEL.
# CC_ENABLED=1
# ICLAUDE_CMD=iclaude
# CC_MAX_RETRIES=2

# ─── Tracing ────────────────────────────────────────────────────────────────
# TRACE_ENABLED=0                    # 1 = logs/<run>/trace_<task>.jsonl
```

- [ ] **Step 2: Verify no active code reads the deleted variables**

```bash
grep -rn "EVALUATOR_\|WIKI_\|CONTRACT_\|DSPY_\|OPTIMIZER_\|GEPA_\|POSTRUN_\|MODEL_EMAIL\|MODEL_LOOKUP\|MODEL_INBOX\|MODEL_CLASSIFIER\|ROUTER_\|CLASSIFIER_" \
    agent/ main.py --include="*.py" | grep -v "^.*#" | grep -v "dispatch.py:276"
```

Expected: no output (or only comment lines)

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "chore: clean up .env.example — rename MODEL_DEFAULT→MODEL, remove dead subsystem vars"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Replace few-shot with SQL example | Task 2 |
| `sql_schema` available in PrephaseResult | Task 2 |
| `## CATALOGUE STRATEGY` section: HARD RULE no list/find/read | Task 3 |
| Step order: AGENTS.MD → DISTINCT → EXPLAIN → SELECT → report | Task 3 |
| Question patterns: COUNT, LIMIT 1 | Task 3 |
| Never assume attribute values | Task 3 |
| `DRY_RUN=1` mode with prephase-only + jsonl output | Task 4 |
| `task_id` param in `run_agent()` | Task 4 |
| Pass `task_id` from `main.py` | Task 4 |
| `MODEL_DEFAULT` → `MODEL` in orchestrator.py | Task 4 (inline with rewrite) |
| `MODEL_DEFAULT` → `MODEL` in main.py | Task 5 |
| `.env.example` cleanup | Task 6 |
| Delete `agent/contract_models.py` | Task 1 |
| Delete obsolete test files | Task 1 |
| Delete `data/default_contracts/`, `data/prompts/`, `data/wiki/` | Task 1 |

**Placeholder scan:** No TBD/TODO/placeholder in plan — all steps have actual code.

**Type consistency:**
- `PrephaseResult.sql_schema: str` added in Task 2, used in Task 4's `_write_dry_run(pre)` via `pre.sql_schema` ✓
- `run_agent(... task_id: str = "")` defined in Task 4, called with `task_id=task_id` in Task 5 step 4 ✓
- `_DRY_RUN_LOG: Path` defined at module level in Task 4, patched in tests via `monkeypatch.setattr` ✓
