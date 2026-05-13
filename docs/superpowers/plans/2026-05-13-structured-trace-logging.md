# Structured JSONL Trace Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-task `.log` files with structured JSONL traces that capture every LLM call, gate check, SQL validate/execute, and final result.

**Architecture:** Thread-local singleton `agent/trace.py` exposes `TraceLogger` + `get_trace()` / `set_trace()` via `threading.local()`. Zero changes to function signatures outside the four instrumented files; all callsites guard with `if t := get_trace():`. System prompt deduplication via sha256 avoids repeating large blocks.

**Tech Stack:** Python 3.11+, `hashlib`, `json`, `threading`, `pathlib.Path`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `agent/trace.py` | TraceLogger class + thread-local accessors |
| Create | `tests/test_trace.py` | Unit tests for TraceLogger |
| Modify | `main.py` | Create/close TraceLogger, remove per-task `.log` |
| Modify | `agent/pipeline.py` | Add `cycle`/`phase` params + trace calls at every instrumentation point |
| Modify | `agent/resolve.py` | Timer + trace calls around LLM call and SQL execs |

---

## Task 1: Create `agent/trace.py`

**Files:**
- Create: `agent/trace.py`
- Create: `tests/test_trace.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_trace.py
import json
import threading
from pathlib import Path

import pytest

from agent.trace import TraceLogger, get_trace, set_trace


def _read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_get_trace_none_by_default():
    assert get_trace() is None


def test_set_and_get_trace(tmp_path):
    t = TraceLogger(tmp_path / "t.jsonl", "t01")
    set_trace(t)
    assert get_trace() is t
    set_trace(None)
    assert get_trace() is None
    t.close()


def test_header_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_header("find speakers under 5000", "claude-sonnet-4-6")
    t.close()
    recs = _read_records(p)
    assert len(recs) == 1
    r = recs[0]
    assert r["type"] == "header"
    assert r["task_id"] == "t01"
    assert r["task_text"] == "find speakers under 5000"
    assert r["model"] == "claude-sonnet-4-6"
    assert "ts" in r


def test_llm_call_deduplication(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    system = [{"type": "text", "text": "be helpful"}]
    t.log_llm_call("sql_plan", 1, system, "TASK: find X", "raw", {"queries": []}, 100, 50, 1200)
    t.log_llm_call("learn", 1, system, "TASK: find X\nERROR: ...", "raw2", {}, 90, 40, 900)
    t.close()
    recs = _read_records(p)
    # header_system written once, two llm_call records
    types = [r["type"] for r in recs]
    assert types.count("header_system") == 1
    assert types.count("llm_call") == 2
    sha = next(r["sha256"] for r in recs if r["type"] == "header_system")
    for r in recs:
        if r["type"] == "llm_call":
            assert r["system_sha256"] == sha
            assert "system" not in r


def test_llm_call_new_system_writes_new_header_system(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_llm_call("sql_plan", 1, [{"type": "text", "text": "A"}], "msg1", "r1", {}, 10, 5, 100)
    t.log_llm_call("answer", 1, [{"type": "text", "text": "B"}], "msg2", "r2", {}, 10, 5, 100)
    t.close()
    recs = _read_records(p)
    assert [r["type"] for r in recs].count("header_system") == 2


def test_gate_check_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_gate_check(1, "security", ["SELECT *"], True, "DDL not allowed")
    t.close()
    r = _read_records(p)[0]
    assert r["type"] == "gate_check"
    assert r["cycle"] == 1
    assert r["gate_type"] == "security"
    assert r["blocked"] is True
    assert r["error"] == "DDL not allowed"


def test_gate_check_not_blocked(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_gate_check(1, "schema", ["SELECT brand FROM products"], False, None)
    t.close()
    r = _read_records(p)[0]
    assert r["blocked"] is False
    assert r["error"] is None


def test_sql_validate_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_sql_validate(1, "SELECT 1", "1", None)
    t.close()
    r = _read_records(p)[0]
    assert r["type"] == "sql_validate"
    assert r["explain_result"] == "1"
    assert r["error"] is None


def test_sql_execute_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_sql_execute(1, "SELECT brand FROM products", "brand\nHeco\n", True, 230)
    t.close()
    r = _read_records(p)[0]
    assert r["type"] == "sql_execute"
    assert r["has_data"] is True
    assert r["duration_ms"] == 230


def test_resolve_exec_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_resolve_exec("SELECT DISTINCT brand FROM products WHERE brand ILIKE '%Heco%'", "brand\nHeco\n", "Heco")
    t.close()
    r = _read_records(p)[0]
    assert r["type"] == "resolve_exec"
    assert r["value_extracted"] == "Heco"


def test_task_result_record(tmp_path):
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    t.log_task_result("OUTCOME_OK", 1.0, 2, 7499, 1479, 65000, [])
    t.close()
    r = _read_records(p)[0]
    assert r["type"] == "task_result"
    assert r["outcome"] == "OUTCOME_OK"
    assert r["score"] == 1.0
    assert r["cycles_used"] == 2


def test_thread_isolation(tmp_path):
    results = {}

    def worker(tid: str):
        p = tmp_path / f"{tid}.jsonl"
        t = TraceLogger(p, tid)
        set_trace(t)
        assert get_trace() is t
        t.log_header("task", "model")
        t.close()
        set_trace(None)
        results[tid] = _read_records(p)

    threads = [threading.Thread(target=worker, args=(f"t0{i}",)) for i in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    for tid, recs in results.items():
        assert recs[0]["task_id"] == tid
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent
uv run pytest tests/test_trace.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'agent.trace'`

- [ ] **Step 3: Implement `agent/trace.py`**

```python
"""Thread-local structured JSONL trace logger for per-task pipeline traces."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_tl = threading.local()


def get_trace() -> "TraceLogger | None":
    return getattr(_tl, "logger", None)


def set_trace(logger: "TraceLogger | None") -> None:
    _tl.logger = logger


class TraceLogger:
    def __init__(self, path: Path, task_id: str) -> None:
        self._fh = path.open("w", buffering=1, encoding="utf-8")
        self._task_id = task_id
        self._seen_sha: set[str] = set()

    def _ts(self) -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _write(self, record: dict) -> None:
        record.setdefault("ts", self._ts())
        record.setdefault("task_id", self._task_id)
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _sys_sha256(self, system: "str | list[dict]") -> str:
        raw = json.dumps(system, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _ensure_header_system(self, system: "str | list[dict]") -> str:
        sha = self._sys_sha256(system)
        if sha not in self._seen_sha:
            self._seen_sha.add(sha)
            blocks = system if isinstance(system, list) else [{"type": "text", "text": system}]
            self._write({"type": "header_system", "sha256": sha, "blocks": blocks})
        return sha

    def log_header(self, task_text: str, model: str) -> None:
        self._write({"type": "header", "task_text": task_text, "model": model})

    def log_llm_call(
        self,
        phase: str,
        cycle: int,
        system: "str | list[dict]",
        user_msg: str,
        raw_response: str,
        parsed_output: "dict | None",
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
    ) -> None:
        sha = self._ensure_header_system(system)
        self._write({
            "type": "llm_call",
            "cycle": cycle,
            "phase": phase,
            "system_sha256": sha,
            "user_msg": user_msg,
            "raw_response": raw_response,
            "parsed_output": parsed_output,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
            "success": parsed_output is not None,
        })

    def log_gate_check(
        self,
        cycle: int,
        gate_type: str,
        queries: list[str],
        blocked: bool,
        error: "str | None",
    ) -> None:
        self._write({
            "type": "gate_check",
            "cycle": cycle,
            "gate_type": gate_type,
            "queries": queries,
            "blocked": blocked,
            "error": error,
        })

    def log_sql_validate(
        self,
        cycle: int,
        query: str,
        result: str,
        error: "str | None",
    ) -> None:
        self._write({
            "type": "sql_validate",
            "cycle": cycle,
            "query": query,
            "explain_result": result,
            "error": error,
        })

    def log_sql_execute(
        self,
        cycle: int,
        query: str,
        result: str,
        has_data: bool,
        duration_ms: int,
    ) -> None:
        self._write({
            "type": "sql_execute",
            "cycle": cycle,
            "query": query,
            "result": result,
            "has_data": has_data,
            "duration_ms": duration_ms,
        })

    def log_resolve_exec(self, query: str, result: str, value: str) -> None:
        self._write({
            "type": "resolve_exec",
            "query": query,
            "result": result,
            "value_extracted": value,
        })

    def log_task_result(
        self,
        outcome: str,
        score: float,
        cycles: int,
        total_in: int,
        total_out: int,
        elapsed_ms: int,
        score_detail: list[str],
    ) -> None:
        self._write({
            "type": "task_result",
            "outcome": outcome,
            "score": score,
            "cycles_used": cycles,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "elapsed_ms": elapsed_ms,
            "score_detail": score_detail,
        })

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_trace.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/trace.py tests/test_trace.py
git commit -m "feat: add TraceLogger module with thread-local JSONL trace logging"
```

---

## Task 2: Instrument `main.py`

**Files:**
- Modify: `main.py` — create/close TraceLogger, remove per-task log_fh, log_header + log_task_result

- [ ] **Step 1: Write failing test**

```python
# tests/test_trace_main.py
"""Verify main.py creates/closes TraceLogger and calls log_header + log_task_result."""
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest


def test_run_single_task_creates_jsonl_and_removes_log(tmp_path, monkeypatch):
    """After _run_single_task: .jsonl created, no .log file, log_header + log_task_result called."""
    import main as m

    monkeypatch.setattr(m, "_run_dir", tmp_path)

    fake_trial = MagicMock()
    fake_trial.task_id = "t01"
    fake_trial.trial_id = "trial-1"
    fake_trial.harness_url = "http://x"
    fake_trial.instruction = "find item"

    fake_end = MagicMock()
    fake_end.score = 1.0
    fake_end.score_detail = ["ok"]

    fake_client = MagicMock()
    fake_client.start_trial.return_value = fake_trial
    fake_client.end_trial.return_value = fake_end

    with patch("main.HarnessServiceClientSync", return_value=fake_client), \
         patch("main.run_agent", return_value={"input_tokens": 10, "output_tokens": 5,
                                                "outcome": "OUTCOME_OK", "cycles_used": 1,
                                                "task_type": "lookup", "model_used": "m"}):
        m._run_single_task("trial-1", [])

    jsonl_path = tmp_path / "t01.jsonl"
    assert jsonl_path.exists(), "t01.jsonl must be created"
    assert not (tmp_path / "t01.log").exists(), "t01.log must NOT be created"

    import json
    records = [json.loads(ln) for ln in jsonl_path.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "header" in types
    assert "task_result" in types
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_trace_main.py -v 2>&1 | tail -20
```

Expected: FAIL — test_run_single_task_creates_jsonl_and_removes_log

- [ ] **Step 3: Edit `main.py` — add import**

Add after `from agent import run_agent`:
```python
from agent.trace import TraceLogger, get_trace, set_trace
```

- [ ] **Step 4: Edit `main.py` — remove `_Tee.write` per-task file routing**

In `_Tee.write`, remove lines that write to `task_fh`:

Replace:
```python
        def write(self, data: str) -> None:
            prefix = getattr(_task_local, "task_id", None)
            task_fh = getattr(_task_local, "log_fh", None)
            clean = _ansi.sub("", data)
            if prefix and data and data != "\n":
                _orig.write(f"[{prefix}] {data}")
            else:
                _orig.write(data)
            if task_fh is not None:
                task_fh.write(clean)
            else:
                _fh.write(clean)

        def flush(self) -> None:
            _orig.flush()
            _fh.flush()
            task_fh = getattr(_task_local, "log_fh", None)
            if task_fh is not None:
                task_fh.flush()
```

With:
```python
        def write(self, data: str) -> None:
            prefix = getattr(_task_local, "task_id", None)
            clean = _ansi.sub("", data)
            if prefix and data and data != "\n":
                _orig.write(f"[{prefix}] {data}")
            else:
                _orig.write(data)
            _fh.write(clean)

        def flush(self) -> None:
            _orig.flush()
            _fh.flush()
```

- [ ] **Step 5: Edit `main.py` — replace per-task `.log` with TraceLogger in `_run_single_task`**

Replace:
```python
    _task_local.task_id = task_id
    assert _run_dir is not None
    _task_local.log_fh = open(_run_dir / f"{task_id}.log", "w", buffering=1, encoding="utf-8")
    try:
        task_start = time.time()
```

With:
```python
    _task_local.task_id = task_id
    assert _run_dir is not None
    _trace = TraceLogger(_run_dir / f"{task_id}.jsonl", task_id)
    set_trace(_trace)
    try:
        task_start = time.time()
```

- [ ] **Step 6: Edit `main.py` — log_header after task start print**

After:
```python
        print(f"\n{'=' * 30} Starting task: {task_id} {'=' * 30}")
        print(f"{CLI_BLUE}{trial.instruction}{CLI_CLR}\n{'-' * 80}")
```

Add:
```python
        _trace.log_header(trial.instruction, model=os.getenv("MODEL", "unknown"))
```

- [ ] **Step 7: Edit `main.py` — log_task_result after end_trial, before summary print**

After:
```python
        result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
        score = result.score
        detail = list(result.score_detail)
```

Add:
```python
        if t := get_trace():
            t.log_task_result(
                outcome=token_stats.get("outcome", ""),
                score=float(score),
                cycles=token_stats.get("cycles_used", 0),
                total_in=token_stats.get("input_tokens", 0),
                total_out=token_stats.get("output_tokens", 0),
                elapsed_ms=int(task_elapsed * 1000),
                score_detail=detail,
            )
```

- [ ] **Step 8: Edit `main.py` — close TraceLogger in finally, remove old log_fh close**

Replace:
```python
    finally:
        fh = _task_local.log_fh
        _task_local.log_fh = None
        if fh:
            fh.flush()
            fh.close()
```

With:
```python
    finally:
        if t := get_trace():
            t.close()
        set_trace(None)
```

- [ ] **Step 9: Run test to verify it passes**

```bash
uv run pytest tests/test_trace_main.py -v
```

Expected: PASS

- [ ] **Step 10: Run full test suite to catch regressions**

```bash
uv run pytest tests/ -v --ignore=tests/test_trace_main.py -x 2>&1 | tail -30
```

Expected: all existing tests PASS

- [ ] **Step 11: Commit**

```bash
git add main.py tests/test_trace_main.py
git commit -m "feat: instrument main.py with TraceLogger, remove per-task .log"
```

---

## Task 3: Instrument `agent/pipeline.py`

**Files:**
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_trace_pipeline.py
"""Verify pipeline instruments TraceLogger at all required points."""
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agent.pipeline import run_pipeline
from agent.prephase import PrephaseResult
from agent.trace import TraceLogger, set_trace, get_trace


def _make_pre(db_schema="CREATE TABLE products(id INT, brand TEXT, type TEXT, sku TEXT)"):
    return PrephaseResult(agents_md_content="", agents_md_path="/AGENTS.MD", db_schema=db_schema)


def _exec_ok(stdout='[{"brand":"Heco"}]'):
    r = MagicMock()
    r.stdout = stdout
    return r


@pytest.fixture(autouse=True)
def reset_caches():
    import agent.pipeline
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None
    yield
    agent.pipeline._rules_loader_cache = None
    agent.pipeline._security_gates_cache = None


def _collect_trace_records(tmp_path, task_id="t01"):
    p = tmp_path / f"{task_id}.jsonl"
    t = TraceLogger(p, task_id)
    set_trace(t)
    return t, p


def test_llm_call_records_written_on_success(tmp_path):
    """Happy path: sql_plan + answer llm_call records written."""
    t, p = _collect_trace_records(tmp_path)

    vm = MagicMock()
    vm.exec.return_value = _exec_ok()

    sql_json = json.dumps({"reasoning": "ok", "queries": ["SELECT brand FROM products WHERE type='X'"],
                           "agents_md_refs": []})
    answer_json = json.dumps({"reasoning": "ok", "message": "Found Heco",
                              "outcome": "OUTCOME_OK", "grounding_refs": [], "completed_steps": []})

    with patch("agent.pipeline.call_llm_raw", side_effect=[sql_json, answer_json]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._get_rules_loader"), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline.check_sql_queries", return_value=None), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "anthropic/claude-sonnet-4-6", "find X", _make_pre(), {})

    t.close()
    set_trace(None)

    records = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "llm_call" in types
    llm_calls = [r for r in records if r["type"] == "llm_call"]
    phases = {r["phase"] for r in llm_calls}
    assert "sql_plan" in phases
    assert "answer" in phases
    for r in llm_calls:
        assert "system_sha256" in r
        assert "cycle" in r
        assert "duration_ms" in r


def test_gate_check_records_written(tmp_path):
    """gate_check records for security + schema gates written every cycle."""
    t, p = _collect_trace_records(tmp_path)

    vm = MagicMock()
    vm.exec.return_value = _exec_ok()

    sql_json = json.dumps({"reasoning": "ok", "queries": ["SELECT brand FROM products"],
                           "agents_md_refs": []})
    answer_json = json.dumps({"reasoning": "ok", "message": "ok", "outcome": "OUTCOME_OK",
                              "grounding_refs": [], "completed_steps": []})

    with patch("agent.pipeline.call_llm_raw", side_effect=[sql_json, answer_json]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._get_rules_loader"), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline.check_sql_queries", return_value=None), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "anthropic/claude-sonnet-4-6", "find X", _make_pre(), {})

    t.close()
    set_trace(None)

    records = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    gate_records = [r for r in records if r["type"] == "gate_check"]
    gate_types = {r["gate_type"] for r in gate_records}
    assert "security" in gate_types
    assert "schema" in gate_types


def test_sql_validate_and_execute_records(tmp_path):
    """sql_validate + sql_execute records written on successful cycle."""
    t, p = _collect_trace_records(tmp_path)

    vm = MagicMock()
    vm.exec.return_value = _exec_ok()

    sql_json = json.dumps({"reasoning": "ok", "queries": ["SELECT brand FROM products WHERE type='X'"],
                           "agents_md_refs": []})
    answer_json = json.dumps({"reasoning": "ok", "message": "ok", "outcome": "OUTCOME_OK",
                              "grounding_refs": [], "completed_steps": []})

    with patch("agent.pipeline.call_llm_raw", side_effect=[sql_json, answer_json]), \
         patch("agent.pipeline.run_resolve", return_value={}), \
         patch("agent.pipeline._get_rules_loader"), \
         patch("agent.pipeline._get_security_gates", return_value=[]), \
         patch("agent.pipeline.check_sql_queries", return_value=None), \
         patch("agent.pipeline.check_schema_compliance", return_value=None):
        run_pipeline(vm, "anthropic/claude-sonnet-4-6", "find X", _make_pre(), {})

    t.close()
    set_trace(None)

    records = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "sql_validate" in types
    assert "sql_execute" in types
    exec_r = next(r for r in records if r["type"] == "sql_execute")
    assert "duration_ms" in exec_r
    assert isinstance(exec_r["has_data"], bool)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_trace_pipeline.py -v 2>&1 | tail -20
```

Expected: FAIL — no llm_call/gate_check/sql_validate/sql_execute records

- [ ] **Step 3: Add imports to `agent/pipeline.py`**

At the top, add `import time` and import trace:
```python
import time

from .trace import get_trace
```

(Place `import time` with existing stdlib imports, `.trace` import with existing relative imports)

- [ ] **Step 4: Add `phase` and `cycle` parameters to `_call_llm_phase`**

Replace the function signature and body:

```python
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
    """SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)."""
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
                    phase=phase_name,
                    cycle=cycle,
                    system=system,
                    user_msg=user_msg,
                    raw_response=raw or "",
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
            phase=phase_name,
            cycle=cycle,
            system=system,
            user_msg=user_msg,
            raw_response=raw or "",
            parsed_output=None,
            tokens_in=tok_info.get("input", 0),
            tokens_out=tok_info.get("output", 0),
            duration_ms=duration_ms,
        )
    return None, sgr_entry, tok_info
```

- [ ] **Step 5: Add `cycle` parameter to `_run_learn` and pass through to `_call_llm_phase`**

Replace the entire `_run_learn` function:

```python
def _run_learn(
    static_learn: "str | list[dict]",
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    sgr_trace: list[dict],
    session_rules: list[str],
    highlighted_vault_rules: list[str],
    agents_md_index: dict,
    error_type: str = "semantic",
    cycle: int = 0,
) -> None:
    learn_user = _build_learn_user_msg(task_text, queries, error, error_type)
    learn_out, sgr_learn, _ = _call_llm_phase(
        static_learn, learn_user, model, cfg, LearnOutput,
        max_tokens=2048, phase="learn", cycle=cycle,
    )
    sgr_learn["error_type"] = error_type
    sgr_trace.append(sgr_learn)
    if learn_out and error_type != "llm_fail":
        anchor = learn_out.agents_md_anchor
        if anchor:
            anchor_section = anchor.split(">")[0].strip()
            if anchor_section in agents_md_index:
                anchor_lines = agents_md_index[anchor_section]
                highlighted_vault_rules.append(f"[{anchor_section}]\n" + "\n".join(anchor_lines))
                print(f"{CLI_BLUE}[pipeline] LEARN: anchor={anchor!r}, elevating vault rule{CLI_CLR}")
                return
        session_rules.append(learn_out.rule_content)
        session_rules[:] = session_rules[-3:]
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")
```

- [ ] **Step 6: Update all `_call_llm_phase` and `_run_learn` call sites in `run_pipeline` to pass `phase` and `cycle`**

In `run_pipeline`, make these 7 replacements:

**SQL_PLAN call:**
```python
# before
sql_plan_out, sgr_entry, tok = _call_llm_phase(static_sql, user_msg, model, cfg, SqlPlanOutput)
# after
sql_plan_out, sgr_entry, tok = _call_llm_phase(
    static_sql, user_msg, model, cfg, SqlPlanOutput,
    phase="sql_plan", cycle=cycle + 1,
)
```

**ANSWER call:**
```python
# before
answer_out, sgr_answer, tok = _call_llm_phase(static_answer, answer_user, model, cfg, AnswerOutput)
# after
answer_out, sgr_answer, tok = _call_llm_phase(
    static_answer, answer_user, model, cfg, AnswerOutput,
    phase="answer", cycle=cycle + 1,
)
```

**`_run_learn` call 1 — SQL_PLAN LLM fail:**
```python
# before
_run_learn(static_learn, model, cfg, task_text, [], last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="llm_fail")
# after
_run_learn(static_learn, model, cfg, task_text, [], last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="llm_fail", cycle=cycle + 1)
```

**`_run_learn` call 2 — agents_md_refs empty:**
```python
# before
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="semantic")
# after (first occurrence, under agents_md_refs check)
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="semantic", cycle=cycle + 1)
```

**`_run_learn` call 3 — security gate blocked:**
```python
# before
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="security")
# after (under SECURITY CHECK)
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="security", cycle=cycle + 1)
```

**`_run_learn` call 4 — schema gate blocked:**
```python
# before
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="security")
# after (under SCHEMA GATE)
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index, error_type="security", cycle=cycle + 1)
```

**`_run_learn` call 5 — execute empty/failed:**
```python
# before
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index,
           error_type="empty" if last_empty and not execute_error else "semantic")
# after
_run_learn(static_learn, model, cfg, task_text, queries, last_error,
           sgr_trace, session_rules, highlighted_vault_rules,
           pre.agents_md_index,
           error_type="empty" if last_empty and not execute_error else "semantic",
           cycle=cycle + 1)
```

- [ ] **Step 7: Add gate_check trace after SECURITY CHECK**

Replace:
```python
        gate_err = check_sql_queries(queries, security_gates)
        if gate_err:
```

With:
```python
        gate_err = check_sql_queries(queries, security_gates)
        if t := get_trace():
            t.log_gate_check(cycle + 1, "security", queries, bool(gate_err), gate_err or None)
        if gate_err:
```

- [ ] **Step 8: Add gate_check trace after SCHEMA GATE**

Replace:
```python
        schema_err = check_schema_compliance(queries, pre.schema_digest, confirmed_values, task_text)
        if schema_err:
```

With:
```python
        schema_err = check_schema_compliance(queries, pre.schema_digest, confirmed_values, task_text)
        if t := get_trace():
            t.log_gate_check(cycle + 1, "schema", queries, bool(schema_err), schema_err or None)
        if schema_err:
```

- [ ] **Step 9: Add sql_validate trace in VALIDATE loop**

Replace the validate loop body:
```python
        validate_error = None
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[f"EXPLAIN {q}"]))
                result_txt = _exec_result_text(result)
                if "error" in result_txt.lower():
                    validate_error = f"EXPLAIN error: {result_txt[:200]}"
                    if t := get_trace():
                        t.log_sql_validate(cycle + 1, q, result_txt, validate_error)
                    break
                if t := get_trace():
                    t.log_sql_validate(cycle + 1, q, result_txt, None)
            except Exception as e:
                validate_error = f"EXPLAIN exception: {e}"
                if t := get_trace():
                    t.log_sql_validate(cycle + 1, q, "", validate_error)
                break
```

- [ ] **Step 10: Add sql_execute trace in EXECUTE loop**

Replace the execute loop body:
```python
        execute_error = None
        sql_results = []
        for q in queries:
            try:
                _t0 = time.monotonic()
                result = vm.exec(ExecRequest(path="/bin/sql", args=[q]))
                _dur = int((time.monotonic() - _t0) * 1000)
                result_txt = _exec_result_text(result)
                sql_results.append(result_txt)
                if t := get_trace():
                    t.log_sql_execute(cycle + 1, q, result_txt, _csv_has_data(result_txt), _dur)
                print(f"{CLI_BLUE}[pipeline] EXECUTE: {q[:60]!r} → {result_txt[:80]}{CLI_CLR}")
            except Exception as e:
                execute_error = f"Execute exception: {e}"
                break
```

- [ ] **Step 11: Add `cycles_used` to stats dict in `run_pipeline`**

Replace:
```python
    stats = {
        "outcome": outcome,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }
```

With:
```python
    stats = {
        "outcome": outcome,
        "cycles_used": cycles_used,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }
```

- [ ] **Step 12: Run trace pipeline tests**

```bash
uv run pytest tests/test_trace_pipeline.py -v
```

Expected: all PASS

- [ ] **Step 13: Run full test suite**

```bash
uv run pytest tests/ -v -x 2>&1 | tail -30
```

Expected: all PASS

- [ ] **Step 14: Commit**

```bash
git add agent/pipeline.py tests/test_trace_pipeline.py
git commit -m "feat: instrument pipeline.py with trace calls (llm_call, gate_check, sql_validate, sql_execute)"
```

---

## Task 4: Instrument `agent/resolve.py`

**Files:**
- Modify: `agent/resolve.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_trace_resolve.py
"""Verify resolve.py writes llm_call + resolve_exec trace records."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.resolve import run_resolve
from agent.prephase import PrephaseResult
from agent.trace import TraceLogger, set_trace


def _make_pre():
    return PrephaseResult(
        agents_md_content="",
        agents_md_path="/AGENTS.MD",
        db_schema="CREATE TABLE products(brand TEXT)",
    )


def _exec_result(stdout="brand\nHeco\n"):
    r = MagicMock()
    r.stdout = stdout
    return r


def test_resolve_exec_records_written(tmp_path):
    """resolve_exec written for each SQL execution in resolve phase."""
    p = tmp_path / "t01.jsonl"
    t = TraceLogger(p, "t01")
    set_trace(t)

    vm = MagicMock()
    vm.exec.return_value = _exec_result()

    resolve_json = json.dumps({
        "reasoning": "brand name needs confirmation",
        "candidates": [
            {"term": "heco", "field": "brand",
             "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%'"}
        ]
    })

    with patch("agent.resolve.call_llm_raw", return_value=resolve_json):
        run_resolve(vm, "model", "find Heco speakers", _make_pre(), {})

    t.close()
    set_trace(None)

    records = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    types = [r["type"] for r in records]
    assert "llm_call" in types
    assert "resolve_exec" in types

    llm = next(r for r in records if r["type"] == "llm_call")
    assert llm["phase"] == "resolve"
    assert llm["cycle"] == 0
    assert "duration_ms" in llm

    exec_r = next(r for r in records if r["type"] == "resolve_exec")
    assert "value_extracted" in exec_r
    assert exec_r["value_extracted"] == "Heco"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_trace_resolve.py -v 2>&1 | tail -10
```

Expected: FAIL — no llm_call/resolve_exec records

- [ ] **Step 3: Edit `agent/resolve.py` — add imports**

Add after existing imports:
```python
import time

from .trace import get_trace
```

- [ ] **Step 4: Edit `agent/resolve.py` — instrument `_run` function**

Replace the LLM call section in `_run`:

```python
    system = _build_resolve_system(pre)
    tok_info: dict = {}
    _t0 = time.monotonic()
    raw = call_llm_raw(system, f"TASK: {task_text}", model, cfg, max_tokens=1024, token_out=tok_info)
    _dur = int((time.monotonic() - _t0) * 1000)
    if not raw:
        return {}

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        if t := get_trace():
            t.log_llm_call("resolve", 0, system, f"TASK: {task_text}", raw, None,
                           tok_info.get("input", 0), tok_info.get("output", 0), _dur)
        return {}

    try:
        resolve_out = ResolveOutput.model_validate(parsed)
    except Exception:
        if t := get_trace():
            t.log_llm_call("resolve", 0, system, f"TASK: {task_text}", raw, None,
                           tok_info.get("input", 0), tok_info.get("output", 0), _dur)
        return {}

    if t := get_trace():
        t.log_llm_call("resolve", 0, system, f"TASK: {task_text}", raw, parsed,
                       tok_info.get("input", 0), tok_info.get("output", 0), _dur)
```

- [ ] **Step 5: Edit `agent/resolve.py` — add resolve_exec after each _exec_sql call**

Replace the candidate loop body:

```python
    confirmed_values: dict[str, list[str]] = {}

    for candidate in resolve_out.candidates:
        err = _security_check(candidate.discovery_query)
        if err:
            print(f"[resolve] security blocked: {err}")
            continue

        result_txt = _exec_sql(vm, candidate.discovery_query)
        value = _first_value(result_txt)
        if t := get_trace():
            t.log_resolve_exec(candidate.discovery_query, result_txt, value or "")
        if value:
            field = candidate.field
            if field not in confirmed_values:
                confirmed_values[field] = []
            if value not in confirmed_values[field]:
                confirmed_values[field].append(value)

    return confirmed_values
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_trace_resolve.py -v
```

Expected: PASS

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest tests/ -v -x 2>&1 | tail -30
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add agent/resolve.py tests/test_trace_resolve.py
git commit -m "feat: instrument resolve.py with llm_call and resolve_exec trace records"
```
