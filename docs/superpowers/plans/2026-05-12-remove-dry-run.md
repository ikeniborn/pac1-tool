# Remove Orchestrator DRY_RUN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Удалить отладочный инструмент DRY_RUN и все его артефакты из оркестратора и prephase.

**Architecture:** Чистое удаление — никакой новой логики не вводится. Три затронутых модуля: `agent/prephase.py` (удалить параметр + поле), `agent/orchestrator.py` (удалить env var + функцию + ветку), тесты (удалить dry_run-тесты, исправить конструкторы PrephaseResult).

**Tech Stack:** Python, pytest, uv

---

### Task 1: Удалить dry_run из agent/prephase.py и обновить test_prephase.py

**Files:**
- Modify: `agent/prephase.py`
- Modify: `tests/test_prephase.py`

- [ ] **Step 1: Заменить содержимое agent/prephase.py**

Итоговый файл (удалены: параметр `dry_run`, поле `bin_sql_content`, блок `/bin/sql`):

```python
import os
from dataclasses import dataclass

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ReadRequest, ExecRequest
from google.protobuf.json_format import MessageToDict

from .llm import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
    system_prompt_text: str,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [
        {"role": "system", "content": system_prompt_text},
    ]

    # Read AGENTS.MD — source of truth for vault semantics and folder roles.
    agents_md_content = ""
    agents_md_path = ""
    for candidate in ("/AGENTS.MD", "/AGENTS.md"):
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                print(f"{CLI_BLUE}[prephase] read {candidate}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                break
        except Exception:
            pass

    prephase_parts = [f"TASK: {task_text}"]
    if agents_md_content:
        if _LOG_LEVEL == "DEBUG":
            print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")
        prephase_parts.append(
            f"\n{agents_md_path} CONTENT (source of truth for vault semantics):\n{agents_md_content}"
        )
    prephase_parts.append(
        "\nNOTE: Use AGENTS.MD above to identify actual folder paths. "
        "Verify paths with list/find before acting. Do not assume paths."
    )

    log.append({"role": "user", "content": "\n".join(prephase_parts)})
    preserve_prefix = list(log)

    db_schema = ""
    try:
        schema_result = vm.exec(ExecRequest(path="/bin/sql", args=[".schema"]))
        try:
            d = MessageToDict(schema_result)
            db_schema = d.get("stdout", "") or d.get("output", "")
        except Exception:
            db_schema = ""
        if not db_schema:
            db_schema = getattr(schema_result, "stdout", "") or getattr(schema_result, "output", "") or ""
        print(f"{CLI_BLUE}[prephase] /bin/sql .schema:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/sql .schema: {e}{CLI_CLR}")

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
    )
```

- [ ] **Step 2: Обновить tests/test_prephase.py**

Удалить три теста (`test_dry_run_reads_bin_sql`, `test_dry_run_bin_sql_not_in_log`, `test_write_dry_run_format`) и исправить два существующих.

Итоговый файл:

```python
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from agent.prephase import run_prephase, PrephaseResult


def _make_vm(agents_md="AGENTS CONTENT", bin_sql="SQL CONTENT"):
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = agents_md
    bin_r = MagicMock(); bin_r.content = bin_sql
    def _read(req):
        if req.path in ("/AGENTS.MD", "/AGENTS.md"):
            return agents_r
        if req.path == "/bin/sql":
            return bin_r
        raise Exception(f"unexpected read: {req.path}")
    vm.read.side_effect = _read
    return vm


def test_prephase_result_fields():
    """PrephaseResult has exactly the expected fields."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert fields == {"log", "preserve_prefix", "agents_md_content", "agents_md_path",
                      "db_schema"}


def test_normal_mode_reads_only_agents_md():
    """Normal mode: exactly 1 vm.read call (AGENTS.MD)."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.read.call_count == 1
    assert result.agents_md_content == "AGENTS CONTENT"


def test_normal_mode_log_structure():
    """Log has system + prephase user."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert result.log[0]["role"] == "system"
    assert result.log[1]["role"] == "user"
    assert "find products" in result.log[1]["content"]
    assert "AGENTS CONTENT" in result.log[1]["content"]


def test_normal_mode_no_tree_no_context():
    """vm.tree and vm.context are never called."""
    vm = _make_vm()
    run_prephase(vm, "task", "sys")
    assert vm.tree.call_count == 0
    assert vm.context.call_count == 0


def test_agents_md_not_found():
    """If AGENTS.MD missing, agents_md_content is empty, no crash."""
    vm = MagicMock()
    vm.read.side_effect = Exception("not found")
    result = run_prephase(vm, "task", "sys")
    assert result.agents_md_content == ""
    assert result.agents_md_path == ""


def test_preserve_prefix_equals_log():
    """preserve_prefix is a copy of log at return time."""
    vm = _make_vm()
    result = run_prephase(vm, "task", "sys")
    assert result.preserve_prefix == result.log


def test_prephase_result_has_db_schema_field():
    """PrephaseResult now has db_schema field."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert "db_schema" in fields


def test_normal_mode_reads_schema():
    """Normal mode still calls vm.exec for schema."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS CONTENT"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products ..."
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.exec.call_count == 1
    assert result.db_schema == "CREATE TABLE products ..."


def test_schema_exec_fail_sets_empty_db_schema():
    """vm.exec exception → db_schema is empty string, no crash."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    vm.read.return_value = agents_r
    vm.exec.side_effect = Exception("exec failed")
    result = run_prephase(vm, "task", "sys")
    assert result.db_schema == ""


def test_schema_not_in_log():
    """db_schema content must NOT appear in LLM log messages."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    exec_r = MagicMock(); exec_r.stdout = "UNIQUE_SCHEMA_MARKER_XYZ"
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "task", "sys")
    for msg in result.log:
        assert "UNIQUE_SCHEMA_MARKER_XYZ" not in msg.get("content", "")


def test_no_few_shot_in_log():
    """prephase log must not contain the NextStep few-shot pair."""
    import agent.prephase as p
    assert not hasattr(p, "_FEW_SHOT_USER"), "_FEW_SHOT_USER should be removed"
    assert not hasattr(p, "_FEW_SHOT_ASSISTANT"), "_FEW_SHOT_ASSISTANT should be removed"
```

- [ ] **Step 3: Запустить тесты prephase**

```bash
uv run pytest tests/test_prephase.py -v
```

Ожидание: все тесты PASS, нет упоминаний `dry_run` или `bin_sql_content`.

- [ ] **Step 4: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "refactor: remove dry_run param and bin_sql_content from prephase"
```

---

### Task 2: Удалить dry_run из agent/orchestrator.py и обновить test_orchestrator_pipeline.py

**Files:**
- Modify: `agent/orchestrator.py`
- Modify: `tests/test_orchestrator_pipeline.py`

- [ ] **Step 1: Заменить содержимое agent/orchestrator.py**

Итоговый файл (удалены: `import json`, `from pathlib import Path`, `_DRY_RUN`, `_DRY_RUN_LOG`, `_write_dry_run`, `if _DRY_RUN:` ветка):

```python
"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import os

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.pipeline import run_pipeline
from agent.prompt import build_system_prompt

_MODEL = os.environ.get("MODEL", "")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}

    task_type = "lookup"
    system_prompt = build_system_prompt(task_type)
    pre = run_prephase(vm, task_text, system_prompt)

    stats = run_pipeline(vm, model, task_text, pre, cfg)
    stats["model_used"] = model
    stats["task_type"] = task_type
    stats["builder_used"] = False
    stats["builder_in_tok"] = 0
    stats["builder_out_tok"] = 0
    stats["builder_addendum"] = ""
    stats["contract_rounds_taken"] = 0
    stats["contract_is_default"] = True
    stats["eval_rejection_count"] = 0
    return stats


def write_wiki_fragment(*args, **kwargs) -> None:
    """No-op: wiki subsystem removed."""
```

- [ ] **Step 2: Обновить tests/test_orchestrator_pipeline.py**

Удалить `test_write_dry_run_format`, убрать неиспользуемые импорты (`json`, `tempfile`, `Path`), убрать `_write_dry_run` из import строки:

```python
# tests/test_orchestrator_pipeline.py
import importlib
import pytest
from unittest.mock import MagicMock, patch
from agent.orchestrator import run_agent
from agent.prephase import PrephaseResult


def _make_vm_mock():
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products(...)"
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    return vm


def test_lookup_routes_to_pipeline():
    """run_agent calls run_pipeline for all tasks."""
    with patch("agent.orchestrator.EcomRuntimeClientSync", return_value=_make_vm_mock()), \
         patch("agent.orchestrator.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {
            "outcome": "OUTCOME_OK",
            "step_facts": [],
            "done_ops": [],
            "input_tokens": 10,
            "output_tokens": 5,
            "total_elapsed_ms": 100,
        }
        result = run_agent({}, "http://localhost:9001", "How many Lawn Mowers?", "t01")

    mock_pipeline.assert_called_once()
    assert result["outcome"] == "OUTCOME_OK"
    assert result["task_type"] == "lookup"


def test_loop_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agent.loop")
```

- [ ] **Step 3: Запустить тесты оркестратора**

```bash
uv run pytest tests/test_orchestrator_pipeline.py -v
```

Ожидание: оба теста PASS.

- [ ] **Step 4: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator_pipeline.py
git commit -m "refactor: remove _DRY_RUN, _write_dry_run, and DRY_RUN branch from orchestrator"
```

---

### Task 3: Исправить test_pipeline.py

**Files:**
- Modify: `tests/test_pipeline.py:10-17`

- [ ] **Step 1: Убрать bin_sql_content из _make_pre()**

В `tests/test_pipeline.py` строки 10–17 — fixture `_make_pre`. Заменить:

```python
def _make_pre(agents_md="AGENTS", db_schema="CREATE TABLE products(id INT, type TEXT, brand TEXT, sku TEXT, model TEXT)"):
    return PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[],
        agents_md_content=agents_md,
        agents_md_path="/AGENTS.MD",
        db_schema=db_schema,
    )
```

- [ ] **Step 2: Запустить тесты pipeline**

```bash
uv run pytest tests/test_pipeline.py -v
```

Ожидание: все тесты PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "refactor: remove bin_sql_content from PrephaseResult fixture in test_pipeline"
```

---

### Task 4: Очистить документацию и данные, финальная верификация

**Files:**
- Modify: `agent/CLAUDE.md`
- Delete: `data/dry_run_analysis.jsonl` (если существует)

- [ ] **Step 1: Удалить DRY_RUN из agent/CLAUDE.md**

В `agent/CLAUDE.md` строки 19–23 — блок env vars. Убрать строку:

```
- `DRY_RUN=1` — prephase only, no LLM calls, writes `data/dry_run_analysis.jsonl`
```

Также строку 30 в Architecture section убрать упоминание dry_run:

```
1. `prephase.py:run_prephase()` — reads `/AGENTS.MD` and injects task text
```

(было: `...and injects task text; if \`DRY_RUN=1\`, also reads \`/bin/sql\` and writes \`data/dry_run_analysis.jsonl\``)

- [ ] **Step 2: Удалить data/dry_run_analysis.jsonl если существует**

```bash
rm -f data/dry_run_analysis.jsonl
```

- [ ] **Step 3: Финальная верификация — все тесты**

```bash
uv run pytest tests/ -v
```

Ожидание: все тесты PASS.

- [ ] **Step 4: Финальная верификация — grep**

```bash
grep -r "dry_run\|DRY_RUN\|_write_dry_run\|bin_sql_content" agent/ tests/
```

Ожидание: нет вывода (кроме `scripts/propose_optimizations.py` — его не трогаем).

- [ ] **Step 5: Commit**

```bash
git add agent/CLAUDE.md
git commit -m "docs: remove DRY_RUN env var from CLAUDE.md"
```
