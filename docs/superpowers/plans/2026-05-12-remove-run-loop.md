# Remove run_loop() and Vault Artifacts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `agent/loop.py` and all code that supports only the reactive loop — vault Pydantic models, `dispatch()` tool router, few-shot prephase block — then rename `dispatch.py` → `llm.py`, leaving the structured SQL pipeline intact.

**Architecture:** Bottom-up removal so TDD signals cascade upward: clean leaf modules first (`models.py`, `json_extract.py`), then delete `loop.py` together with orchestrator fix, then clean `prephase.py`, then rename/trim `dispatch.py` → `llm.py` with all import-site updates in one atomic commit.

**Tech Stack:** Python 3.12, pydantic v2, pytest, uv

---

## File Map

| File | Change |
|------|--------|
| `agent/models.py` | Remove 10 vault classes; keep 4 pipeline models |
| `agent/json_extract.py` | Remove `_normalize_parsed()`; remove NextStep priority tiers; simplify `_richness_key`; import stays `.dispatch` until Task 5 |
| `agent/loop.py` | Delete entire file |
| `agent/orchestrator.py` | Remove `from agent.loop import run_loop` and `else: stats = run_loop(...)` branch |
| `agent/prephase.py` | Remove `_FEW_SHOT_USER`, `_FEW_SHOT_ASSISTANT` and their insertion into `log` |
| `agent/dispatch.py` → `agent/llm.py` | `git mv`; remove `dispatch()`, vault imports, `_nextstep_json_schema`, `_NEXTSTEP_SCHEMA`, json_schema branch of `get_response_format`, protobuf tool imports, `_PROTECTED_*`, `_FIND_KIND`; update `[dispatch]` prints → `[llm]` |
| `agent/pipeline.py` | `from .dispatch import` → `from .llm import` |
| `agent/evaluator.py` | `from .dispatch import` → `from .llm import` |
| `agent/json_extract.py` | `from .dispatch import` → `from .llm import` (same commit as rename) |
| `agent/prephase.py` | `from .dispatch import` → `from .llm import` (same commit as rename) |
| `tests/test_orchestrator_pipeline.py` | Remove `patch("agent.orchestrator.run_loop")` and `mock_loop.assert_not_called()` |
| `tests/test_models_cleanup.py` | **New** — assert vault classes gone, 4 pipeline classes remain |
| `tests/test_json_extract_cleanup.py` | **New** — assert `_normalize_parsed` gone, extraction still works |

---

### Task 1: Clean models.py — remove vault classes

**Files:**
- Modify: `agent/models.py`
- Create: `tests/test_models_cleanup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_cleanup.py`:

```python
import inspect
import pytest
import agent.models as m


def test_pipeline_models_present():
    assert hasattr(m, "SqlPlanOutput")
    assert hasattr(m, "LearnOutput")
    assert hasattr(m, "AnswerOutput")
    assert hasattr(m, "PipelineEvalOutput")


def test_vault_models_removed():
    vault_names = [
        "TaskRoute", "NextStep", "ReportTaskCompletion",
        "Req_Write", "Req_Delete", "Req_Tree", "Req_Find",
        "Req_Search", "Req_List", "Req_Read", "Req_Stat",
        "Req_Exec", "Req_Context", "EmailOutbox",
    ]
    for name in vault_names:
        assert not hasattr(m, name), f"Vault model still present: {name}"


def test_models_has_exactly_four_classes():
    from pydantic import BaseModel
    classes = [
        name for name, obj in inspect.getmembers(m, inspect.isclass)
        if issubclass(obj, BaseModel) and obj is not BaseModel
        and obj.__module__ == "agent.models"
    ]
    assert len(classes) == 4, f"Expected 4 pipeline classes, got {len(classes)}: {classes}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_models_cleanup.py -v
```
Expected: FAIL — `test_vault_models_removed` and `test_models_has_exactly_four_classes` fail.

- [ ] **Step 3: Replace `agent/models.py` with pipeline-only content**

```python
from typing import Literal

from pydantic import BaseModel


class SqlPlanOutput(BaseModel):
    reasoning: str
    queries: list[str]


class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str


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
    prompt_optimization: list[str]
    rule_optimization: list[str]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_models_cleanup.py -v
```
Expected: PASS — all 3 tests green.

- [ ] **Step 5: Run full suite for regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass. (`loop.py` still imports vault models directly but `test_orchestrator_pipeline.py` patches `run_loop` so the import never executes in tests.)

- [ ] **Step 6: Commit**

```bash
git add agent/models.py tests/test_models_cleanup.py
git commit -m "refactor: remove vault models from models.py, keep 4 pipeline classes"
```

---

### Task 2: Clean json_extract.py — remove loop artifacts

**Files:**
- Modify: `agent/json_extract.py`
- Create: `tests/test_json_extract_cleanup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_json_extract_cleanup.py`:

```python
import agent.json_extract as je


def test_normalize_parsed_removed():
    assert not hasattr(je, "_normalize_parsed"), "_normalize_parsed should be removed"


def test_extract_json_fenced_block():
    text = '```json\n{"reasoning": "test", "queries": ["SELECT 1"]}\n```'
    result = je._extract_json_from_text(text)
    assert result == {"reasoning": "test", "queries": ["SELECT 1"]}


def test_extract_json_plain_object():
    text = 'Some text {"queries": ["SELECT COUNT(*) FROM products"]} more text'
    result = je._extract_json_from_text(text)
    assert result is not None
    assert "queries" in result


def test_extract_json_mutation_preferred():
    text = '{"tool": "read", "path": "/x"} {"tool": "write", "path": "/y", "content": "z"}'
    result = je._extract_json_from_text(text)
    assert result is not None
    assert result.get("tool") == "write"


def test_extract_json_returns_none_for_no_json():
    result = je._extract_json_from_text("no json here at all")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_json_extract_cleanup.py -v
```
Expected: FAIL — `test_normalize_parsed_removed` fails.

- [ ] **Step 3: Replace `agent/json_extract.py` with cleaned version**

```python
"""JSON extraction from free-form LLM text output.

Public API:
  _obj_mutation_tool()      — check if a JSON object is a mutation action
  _richness_key()           — deterministic tie-break for same-tier candidates
  _extract_json_from_text() — multi-level priority JSON extraction
"""
import json
import re

from .dispatch import CLI_YELLOW, CLI_CLR  # updated to .llm in Task 5


def _try_json5(text: str):
    """Try json5 parse; raises on failure (ImportError or parse error)."""
    import json5 as _j5
    return _j5.loads(text)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MUTATION_TOOLS = frozenset({"write", "delete", "exec"})

# Maps Req_XXX class names to canonical tool names used in JSON payloads.
# Some models emit "Action: Req_Read({...})" without a "tool" field inside the JSON.
_REQ_CLASS_TO_TOOL: dict[str, str] = {
    "req_read": "read", "req_write": "write", "req_delete": "delete",
    "req_list": "list", "req_search": "search", "req_find": "find",
    "req_tree": "tree", "req_stat": "stat", "req_exec": "exec",
}
# Regex: capture "Req_Xxx" prefix immediately before a JSON object — FIX-150
_REQ_PREFIX_RE = re.compile(r"Req_(\w+)\s*\(", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _obj_mutation_tool(obj: dict) -> str | None:
    """Return the mutation tool name if obj is a write/delete/exec action, else None."""
    tool = obj.get("tool") or (obj.get("function") or {}).get("tool", "")
    return tool if tool in _MUTATION_TOOLS else None


def _richness_key(obj: dict) -> tuple:
    """Lower tuple = preferred. Used by min() to break ties among same-tier candidates."""
    return (-len(obj),)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json_from_text(text: str) -> dict | None:
    """Extract the most actionable valid JSON object from free-form model output.

    Priority (highest first):
    1. ```json fenced block — explicit, return immediately
    2. First object whose tool is a mutation (write/delete/exec)
    3. First bare object with any known 'tool' key
    4. First valid JSON object (richest by key count)
    5. YAML fallback
    """
    # 1. ```json ... ``` fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Collect ALL valid bracket-matched JSON objects.
    # FIX-150: detect "Req_XXX({...})" patterns and inject "tool" when absent.
    candidates: list[dict] = []
    pos = 0
    while True:
        start = text.find("{", pos)
        if start == -1:
            break
        prefix_match = None
        prefix_region = text[max(0, start - 20):start]
        pm = _REQ_PREFIX_RE.search(prefix_region)
        if pm:
            req_name = pm.group(1).lower()
            inferred_tool = _REQ_CLASS_TO_TOOL.get(f"req_{req_name}")
            if inferred_tool:
                prefix_match = inferred_tool
        depth = 0
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    fragment = text[start:idx + 1]
                    obj = None
                    try:
                        obj = json.loads(fragment)
                    except (json.JSONDecodeError, ValueError):
                        try:
                            obj = _try_json5(fragment)
                        except Exception:
                            pass
                    if obj is not None and isinstance(obj, dict):
                        if prefix_match and "tool" not in obj:
                            obj = {"tool": prefix_match, **obj}
                        candidates.append(obj)
                    pos = idx + 1
                    break
        else:
            # FIX-401: bracket-balance repair — truncated JSON at EOF
            repaired = text[start:] + "}" * depth
            for _load in (json.loads, _try_json5):
                try:
                    obj = _load(repaired)
                    if isinstance(obj, dict):
                        if prefix_match and "tool" not in obj:
                            obj = {"tool": prefix_match, **obj}
                        candidates.append(obj)
                        break
                except Exception:
                    continue
            break

    if candidates:
        # 2. Mutation (write/delete/exec)
        _muts = [o for o in candidates if _obj_mutation_tool(o)]
        if _muts:
            return min(_muts, key=_richness_key)
        # 3. Bare object with any known tool key
        _bare = [o for o in candidates if "tool" in o]
        if _bare:
            return min(_bare, key=_richness_key)
        # 4. Richest candidate
        return min(candidates, key=_richness_key)

    # 5. YAML fallback
    try:
        import yaml
        stripped = re.sub(r"```(?:yaml|markdown)?\s*", "", text.strip()).replace("```", "").strip()
        parsed_yaml = yaml.safe_load(stripped)
        if isinstance(parsed_yaml, dict) and "tool" in parsed_yaml:
            print(f"\x1B[33m[fallback] YAML fallback parsed successfully\x1B[0m")
            return parsed_yaml
    except Exception:
        pass

    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_json_extract_cleanup.py -v
```
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Run full suite for regressions**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/json_extract.py tests/test_json_extract_cleanup.py
git commit -m "refactor: remove _normalize_parsed and NextStep priority tiers from json_extract"
```

---

### Task 3: Delete loop.py + fix orchestrator.py + update test (atomic)

These three changes must land in one commit — deleting `loop.py` breaks `orchestrator.py`'s import, which breaks the test.

**Files:**
- Delete: `agent/loop.py`
- Modify: `agent/orchestrator.py`
- Modify: `tests/test_orchestrator_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add this function to `tests/test_orchestrator_pipeline.py` (alongside the existing test):

```python
import importlib
import pytest

def test_loop_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agent.loop")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_orchestrator_pipeline.py::test_loop_module_deleted -v
```
Expected: FAIL — `agent.loop` exists.

- [ ] **Step 3: Delete `agent/loop.py`**

```bash
git rm agent/loop.py
```

- [ ] **Step 4: Replace `agent/orchestrator.py` with loop-free version**

```python
"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import json
import os
from pathlib import Path

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.pipeline import run_pipeline
from agent.prompt import build_system_prompt

_MODEL = os.environ.get("MODEL", "")
_DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
_DRY_RUN_LOG = Path(__file__).parent.parent / "data" / "dry_run_analysis.jsonl"


def _write_dry_run(task_id: str, task_text: str, pre) -> None:
    entry = {
        "task_id": task_id,
        "task": task_text,
        "agents_md": pre.agents_md_content,
        "bin_sql_content": pre.bin_sql_content,
        "db_schema": pre.db_schema,
    }
    _DRY_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_DRY_RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)

    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}

    task_type = "lookup"
    system_prompt = build_system_prompt(task_type)
    pre = run_prephase(vm, task_text, system_prompt, dry_run=_DRY_RUN)

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

- [ ] **Step 5: Update `tests/test_orchestrator_pipeline.py` — remove run_loop mock**

Replace the entire file with:

```python
# tests/test_orchestrator_pipeline.py
import importlib
import pytest
from unittest.mock import MagicMock, patch
from agent.orchestrator import run_agent


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

- [ ] **Step 6: Run full suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass, including `test_loop_module_deleted`.

- [ ] **Step 7: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator_pipeline.py
git commit -m "refactor: delete loop.py, remove run_loop fallback from orchestrator"
```

---

### Task 4: Remove few-shot from prephase.py

**Files:**
- Modify: `agent/prephase.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_prephase.py` (open and append — do not replace existing tests):

```python
def test_no_few_shot_in_log():
    """prephase log must not contain the NextStep few-shot pair."""
    import agent.prephase as p
    assert not hasattr(p, "_FEW_SHOT_USER"), "_FEW_SHOT_USER should be removed"
    assert not hasattr(p, "_FEW_SHOT_ASSISTANT"), "_FEW_SHOT_ASSISTANT should be removed"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_prephase.py::test_no_few_shot_in_log -v
```
Expected: FAIL — constants still present.

- [ ] **Step 3: Edit `agent/prephase.py`**

Remove lines 23–34 (the `_FEW_SHOT_USER` and `_FEW_SHOT_ASSISTANT` constants) and lines 47–49 (their insertion into `log`).

The resulting `run_prephase` should initialize `log` as:

```python
    log: list = [
        {"role": "system", "content": system_prompt_text},
    ]
```

Full updated file:

```python
import os
from dataclasses import dataclass

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ReadRequest, ExecRequest
from google.protobuf.json_format import MessageToDict

from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW  # updated to .llm in Task 5

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    bin_sql_content: str = ""
    db_schema: str = ""


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
    system_prompt_text: str,
    dry_run: bool = False,
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

    bin_sql_content = ""
    if dry_run:
        try:
            bin_r = vm.read(ReadRequest(path="/bin/sql"))
            bin_sql_content = bin_r.content or ""
            print(f"{CLI_BLUE}[prephase] read /bin/sql:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
        except Exception as e:
            print(f"{CLI_YELLOW}[prephase] /bin/sql: {e}{CLI_CLR}")

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
        bin_sql_content=bin_sql_content,
        db_schema=db_schema,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_prephase.py -v
```
Expected: PASS — all prephase tests green.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "refactor: remove NextStep few-shot pair from prephase"
```

---

### Task 5: Rename dispatch.py → llm.py + trim dead code + update all imports (atomic)

This task must be one commit: the rename breaks every `from .dispatch import` site immediately.

**Files:**
- Rename: `agent/dispatch.py` → `agent/llm.py`
- Modify: `agent/llm.py` (remove dead code)
- Modify: `agent/pipeline.py`
- Modify: `agent/evaluator.py`
- Modify: `agent/json_extract.py`
- Modify: `agent/prephase.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_module.py`:

```python
def test_dispatch_module_deleted():
    import importlib
    import pytest
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agent.dispatch")


def test_llm_module_exports():
    from agent.llm import call_llm_raw, OUTCOME_BY_NAME
    assert callable(call_llm_raw)
    assert "OUTCOME_OK" in OUTCOME_BY_NAME


def test_llm_exports_cli_colors():
    from agent.llm import CLI_RED, CLI_GREEN, CLI_CLR, CLI_BLUE, CLI_YELLOW
    assert CLI_CLR == "\x1B[0m"


def test_dispatch_function_removed():
    import agent.llm as llm
    assert not hasattr(llm, "dispatch"), "dispatch() should be removed from llm.py"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_llm_module.py -v
```
Expected: FAIL — `agent.dispatch` exists and `agent.llm` doesn't.

- [ ] **Step 3: Rename dispatch.py → llm.py**

```bash
git mv agent/dispatch.py agent/llm.py
```

- [ ] **Step 4: Edit `agent/llm.py` — remove all dead code**

Apply the following changes to `agent/llm.py`:

**Remove these imports** (lines 13–44 approximately):
```python
# REMOVE:
from pydantic import BaseModel
from google.protobuf.json_format import MessageToDict
from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import (
    AnswerRequest,
    ContextRequest,
    DeleteRequest,
    ExecRequest,
    FindRequest,
    ListRequest,
    NodeKind,
    ReadRequest,
    SearchRequest,
    StatRequest,
    TreeRequest,
    WriteRequest,
)
from .models import (
    ReportTaskCompletion,
    Req_Context,
    Req_Delete,
    Req_Exec,
    Req_Find,
    Req_List,
    Req_Read,
    Req_Search,
    Req_Stat,
    Req_Tree,
    Req_Write,
)
```

**Keep only** `from bitgn.vm.ecom.ecom_pb2 import Outcome` (for `OUTCOME_BY_NAME`).

**Remove these module-level items**:
- `_nextstep_json_schema()` function (lines ~157–159)
- `_NEXTSTEP_SCHEMA: dict | None = None` (line ~161)
- `json_schema` branch inside `get_response_format()` — simplify to:

```python
def get_response_format(mode: str) -> dict | None:
    """Build response_format dict for the given mode, or None if mode='none'."""
    if mode == "json_object":
        return {"type": "json_object"}
    return None
```

**Remove these constants** (only used by `dispatch()`):
```python
# REMOVE:
_PROTECTED_WRITE = frozenset({"/AGENTS.MD", "/AGENTS.md"})
_PROTECTED_PREFIX = ("/docs/channels/",)
_OTP_PATH = "/docs/channels/otp.txt"
_FIND_KIND = {
    "all": NodeKind.NODE_KIND_UNSPECIFIED,
    "files": NodeKind.NODE_KIND_FILE,
    "dirs": NodeKind.NODE_KIND_DIR,
}
```

**Remove `dispatch()` function** (the entire function from `def dispatch(vm: EcomRuntimeClientSync, cmd: BaseModel):` through `raise ValueError(f"Unknown command: {cmd}")`).

**Update print strings** — replace `[dispatch]` → `[llm]` in two places:
- Line ~128: `f"[dispatch] Active backend: {_active} "` → `f"[llm] Active backend: {_active} "`
- Inside `call_llm_raw()`: `f"[dispatch] Primary exhausted — retrying..."` → `f"[llm] Primary exhausted — retrying..."`

- [ ] **Step 5: Update all import sites**

In `agent/pipeline.py` — change line 15:
```python
# Before:
from .dispatch import (
    call_llm_raw, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
# After:
from .llm import (
    call_llm_raw, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
```

In `agent/evaluator.py` — change line 8:
```python
# Before:
from .dispatch import call_llm_raw
# After:
from .llm import call_llm_raw
```

In `agent/json_extract.py` — change line 13:
```python
# Before:
from .dispatch import CLI_YELLOW, CLI_CLR
# After:
from .llm import CLI_YELLOW, CLI_CLR
```

In `agent/prephase.py` — change line 8:
```python
# Before:
from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW
# After:
from .llm import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_llm_module.py -v
```
Expected: PASS — all 4 tests green.

- [ ] **Step 7: Run full suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass.

- [ ] **Step 8: Verify success criteria from spec**

```bash
# loop.py gone
python -c "import agent.loop" 2>&1 | grep "ModuleNotFoundError"

# dispatch.py gone
python -c "import agent.dispatch" 2>&1 | grep "ModuleNotFoundError"

# llm.py exports required symbols
python -c "from agent.llm import call_llm_raw, OUTCOME_BY_NAME; print('ok')"

# models.py has exactly 4 classes
python -c "
import inspect, agent.models as m
from pydantic import BaseModel
cls = [n for n,o in inspect.getmembers(m, inspect.isclass)
       if issubclass(o, BaseModel) and o is not BaseModel and o.__module__ == 'agent.models']
print(cls); assert len(cls) == 4
"

# pipeline and evaluator use .llm
grep 'from .llm import' agent/pipeline.py agent/evaluator.py
```
Expected output:
```
ModuleNotFoundError: No module named 'agent.loop'
ModuleNotFoundError: No module named 'agent.dispatch'
ok
['AnswerOutput', 'LearnOutput', 'PipelineEvalOutput', 'SqlPlanOutput']
agent/pipeline.py:from .llm import (
agent/evaluator.py:from .llm import call_llm_raw
```

- [ ] **Step 9: Commit**

```bash
git add agent/llm.py agent/pipeline.py agent/evaluator.py agent/json_extract.py agent/prephase.py tests/test_llm_module.py
git commit -m "refactor: rename dispatch.py → llm.py, remove dispatch() and vault dead code, update all import sites"
```

---

## Final Verification

After all 5 tasks:

```bash
uv run pytest tests/ -v
```
Expected: All tests pass with zero failures.

Check file existence:
```bash
ls agent/loop.py 2>&1      # should: No such file or directory
ls agent/dispatch.py 2>&1  # should: No such file or directory
ls agent/llm.py            # should: agent/llm.py
```
