# Tracer Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete `agent/tracer.py` and all call sites in `main.py` and `agent/loop.py`.

**Architecture:** Pure deletion — remove JSONL event logger that was never used in production (`TRACE_ENABLED=0` default). No replacement needed; `LOG_LEVEL=DEBUG` covers debugging needs.

**Tech Stack:** Python, no new dependencies.

---

### Task 1: Remove tracer import and emit calls from `agent/loop.py`

**Files:**
- Modify: `agent/loop.py:26` (import)
- Modify: `agent/loop.py:264-265` (task_start emit)
- Modify: `agent/loop.py:306` (report_completion emit)
- Modify: `agent/loop.py:325` (action emit)
- Modify: `agent/loop.py:347` (task_end emit)

- [ ] **Step 1: Remove import line 26**

Delete this line from `agent/loop.py`:
```python
from .tracer import get_task_tracer
```

- [ ] **Step 2: Remove tracer init and task_start emit (lines 264–265)**

Delete these two lines from `agent/loop.py` (inside `run_loop()`, just before the `for step` loop):
```python
    _tracer = get_task_tracer()
    _tracer.emit("task_start", 0, {"model": model, "task_text": task_text[:200]})
```

- [ ] **Step 3: Remove report_completion emit (line 306)**

Delete this line from `agent/loop.py` (inside the `if isinstance(cmd, ReportTaskCompletion):` block):
```python
            _tracer.emit(step_label, step, {"action": "report_completion", "outcome": outcome})
```

- [ ] **Step 4: Remove action emit (line 325)**

Delete this line from `agent/loop.py` (in the `# Execute tool` section, between `step_facts.append(...)` and `print(f"  tool=...")`):
```python
        _tracer.emit(step_label, step, {"action": action_name})
```

- [ ] **Step 5: Remove task_end emit (line 347)**

Delete this line from `agent/loop.py` (after the `for step` loop, before `return {`):
```python
    _tracer.emit("task_end", max_steps, {"outcome": outcome, "total_in_tok": total_in_tok, "total_out_tok": total_out_tok})
```

- [ ] **Step 6: Verify no tracer references remain in loop.py**

Run:
```bash
grep -n "tracer" agent/loop.py
```
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add agent/loop.py
git commit -m "refactor: remove tracer calls from loop.py"
```

---

### Task 2: Remove tracer calls from `main.py`

**Files:**
- Modify: `main.py:87-89` (import + init block)
- Modify: `main.py:142` (set_task_id call)
- Modify: `main.py:265-267` (close_tracer in finally block)

- [ ] **Step 1: Remove import and init block (lines 87–89)**

Delete these three lines from `main.py`:
```python
from agent.tracer import init_tracer as _init_tracer, set_task_id as _set_task_id
if _run_dir is not None:
    _init_tracer(str(_run_dir))
```

- [ ] **Step 2: Remove set_task_id call (line 142)**

Delete this line from `main.py` (inside `run_trial()`, after `_task_local.task_id = task_id`):
```python
    _set_task_id(task_id)
```

- [ ] **Step 3: Remove close_tracer in finally block (lines 265–267)**

Replace this `finally` block in `main.py`:
```python
    finally:
        from agent.tracer import close_tracer as _close_tracer
        _close_tracer()
```
With just the `main()` call (no finally needed):
```python
    main()
```

That is: the full `if __name__ == "__main__":` block becomes:
```python
if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify no tracer references remain in main.py**

Run:
```bash
grep -n "tracer" main.py
```
Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "refactor: remove tracer calls from main.py"
```

---

### Task 3: Delete `agent/tracer.py`

**Files:**
- Delete: `agent/tracer.py`

- [ ] **Step 1: Delete the file**

```bash
git rm agent/tracer.py
```

- [ ] **Step 2: Verify no remaining imports in any Python file**

```bash
grep -rn "tracer" --include="*.py" .
```
Expected: no output (only non-Python files like `.graphify/` may still mention it — those are irrelevant).

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: delete agent/tracer.py (legacy, never used)"
```

---

### Task 4: Verify clean execution

- [ ] **Step 1: Run import check (syntax + imports only)**

```bash
uv run python -c "import agent.loop; import main"
```
Expected: no output, exit code 0.

- [ ] **Step 2: Run existing tests**

```bash
uv run python -m pytest tests/ -v
```
Expected: all tests pass, no `ImportError` or `NameError`.

- [ ] **Step 3: Smoke test with DRY_RUN**

```bash
DRY_RUN=1 uv run python main.py
```
Expected: prephase runs, no traceback.
