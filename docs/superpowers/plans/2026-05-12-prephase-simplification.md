# Prephase Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip `run_prephase()` down to AGENTS.MD + task only; add `bin_sql_content` field written to `data/dry_run_analysis.jsonl` in dry_run mode.

**Architecture:** Single-file rewrite of `agent/prephase.py` — delete tree/preload/date/context steps, simplify `PrephaseResult`, add `dry_run` path that reads `/bin/sql`. Orchestrator gets updated field names in `_write_dry_run`.

**Tech Stack:** Python 3.12, dataclasses, unittest.mock (tests), existing EcomRuntimeClientSync/ReadRequest.

---

### Task 1: Write failing tests for simplified prephase

**Files:**
- Create: `tests/test_prephase.py`

- [ ] **Step 1: Write tests**

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
    assert fields == {"log", "preserve_prefix", "agents_md_content", "agents_md_path", "bin_sql_content"}


def test_normal_mode_reads_only_agents_md():
    """Normal mode: exactly 1 vm.read call (AGENTS.MD)."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert vm.read.call_count == 1
    assert result.agents_md_content == "AGENTS CONTENT"
    assert result.bin_sql_content == ""


def test_normal_mode_log_structure():
    """Log has system + few-shot user + few-shot assistant + prephase user."""
    vm = _make_vm()
    result = run_prephase(vm, "find products", "sys prompt")
    assert result.log[0]["role"] == "system"
    assert result.log[1]["role"] == "user"
    assert result.log[2]["role"] == "assistant"
    assert result.log[3]["role"] == "user"
    assert "find products" in result.log[3]["content"]
    assert "AGENTS CONTENT" in result.log[3]["content"]


def test_normal_mode_no_tree_no_context():
    """vm.tree and vm.context are never called."""
    vm = _make_vm()
    run_prephase(vm, "task", "sys")
    assert vm.tree.call_count == 0
    assert vm.context.call_count == 0


def test_dry_run_reads_bin_sql():
    """dry_run=True: 2 vm.read calls, bin_sql_content populated."""
    vm = _make_vm()
    result = run_prephase(vm, "task", "sys", dry_run=True)
    assert vm.read.call_count == 2
    assert result.bin_sql_content == "SQL CONTENT"


def test_dry_run_bin_sql_not_in_log():
    """bin_sql content must NOT appear in LLM log messages."""
    vm = _make_vm(bin_sql="UNIQUE_BIN_SQL_MARKER")
    result = run_prephase(vm, "task", "sys", dry_run=True)
    for msg in result.log:
        assert "UNIQUE_BIN_SQL_MARKER" not in msg.get("content", "")


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


def test_write_dry_run_format():
    """_write_dry_run writes correct JSON fields to jsonl."""
    from agent.orchestrator import _write_dry_run, _DRY_RUN_LOG
    pre = PrephaseResult(log=[], preserve_prefix=[], agents_md_content="AGENTS", bin_sql_content="SQL")
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "dry_run_analysis.jsonl"
        with patch("agent.orchestrator._DRY_RUN_LOG", log_path):
            _write_dry_run("t01", "find products", pre)
        line = json.loads(log_path.read_text().strip())
    assert line["task_id"] == "t01"
    assert line["task"] == "find products"
    assert line["agents_md"] == "AGENTS"
    assert line["bin_sql_content"] == "SQL"
    assert "sql_schema" not in line
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent && uv run python -m pytest tests/test_prephase.py -v 2>&1 | head -50
```

Expected: FAIL — `PrephaseResult` still has old fields, `bin_sql_content` doesn't exist.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_prephase.py
git commit -m "test: add prephase simplification tests (red)"
```

---

### Task 2: Simplify `PrephaseResult` and rewrite `run_prephase()`

**Files:**
- Modify: `agent/prephase.py`

- [ ] **Step 1: Replace entire `agent/prephase.py`**

```python
import os
from dataclasses import dataclass

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ReadRequest

from .dispatch import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    bin_sql_content: str = ""


# Few-shot user→assistant pair — strongest signal for JSON-only output.
# Placed immediately after system prompt so the model sees its own expected format
# before any task context.
_FEW_SHOT_USER = "Example: How many catalogue products are Lawn Mower?"
_FEW_SHOT_ASSISTANT = (
    '{"current_state":"validating SQL syntax before executing count",'
    '"plan_remaining_steps_brief":["EXPLAIN query","SELECT COUNT","report result"],'
    '"done_operations":[],"task_completed":false,'
    '"function":{"tool":"exec","path":"/bin/sql",'
    '"args":["EXPLAIN SELECT COUNT(*) FROM products WHERE type=\'Lawn Mower\'"],'
    '"stdin":""}}'
)


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
    system_prompt_text: str,
    task_id: str = "",
    dry_run: bool = False,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": _FEW_SHOT_USER},
        {"role": "assistant", "content": _FEW_SHOT_ASSISTANT},
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

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        bin_sql_content=bin_sql_content,
    )
```

- [ ] **Step 2: Run tests**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent && uv run python -m pytest tests/test_prephase.py -v -k "not test_write_dry_run"
```

Expected: all pass except `test_write_dry_run_format` (orchestrator not updated yet).

- [ ] **Step 3: Commit**

```bash
git add agent/prephase.py
git commit -m "refactor: simplify prephase — keep only AGENTS.MD + task reads"
```

---

### Task 3: Update orchestrator `_write_dry_run` and `run_agent`

**Files:**
- Modify: `agent/orchestrator.py:20-31,41`

- [ ] **Step 1: Update `_write_dry_run`, `run_prephase` call, and remove unused import**

Remove `from datetime import datetime, timezone` (top of file — no longer used after timestamp removed from entry).

Replace the `_write_dry_run` function (lines 20–31):

```python
def _write_dry_run(task_id: str, task_text: str, pre) -> None:
    entry = {
        "task_id": task_id,
        "task": task_text,
        "agents_md": pre.agents_md_content,
        "bin_sql_content": pre.bin_sql_content,
    }
    _DRY_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_DRY_RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

Change the `run_prephase` call (line 41):
```python
pre = run_prephase(vm, task_text, system_prompt, task_id=task_id, dry_run=_DRY_RUN)
```

- [ ] **Step 2: Run all tests**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent && uv run python -m pytest tests/test_prephase.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 3: Commit**

```bash
git add agent/orchestrator.py
git commit -m "fix: update orchestrator — pass dry_run/task_id to prephase, fix _write_dry_run fields"
```

---

### Task 4: Verify `data/` directory exists and smoke test dry_run path

**Files:**
- No code change — verify runtime behavior

- [ ] **Step 1: Ensure `data/` directory exists**

```bash
mkdir -p /home/ikeniborn/Documents/Project/ecom1-agent/data
```

- [ ] **Step 2: Verify no stale imports or references**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent && grep -rn "vault_tree_text\|vault_date_est\|inbox_files\|sql_schema\|TreeRequest\|ContextRequest\|ListRequest\|NodeKind" agent/ --include="*.py"
```

Expected: no matches.

- [ ] **Step 3: Final test run**

```bash
cd /home/ikeniborn/Documents/Project/ecom1-agent && uv run python -m pytest tests/test_prephase.py -v
```

Expected: 9/9 pass.

- [ ] **Step 4: Commit data dir**

```bash
touch /home/ikeniborn/Documents/Project/ecom1-agent/data/.gitkeep
git add data/.gitkeep
git commit -m "chore: ensure data/ directory tracked for dry_run_analysis.jsonl"
```
