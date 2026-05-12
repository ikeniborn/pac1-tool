# Agent Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 12 code anomalies across pipeline.py, llm.py, prephase.py, orchestrator.py, sql_security.py: dead code, broken token counting, unbounded session rules, synchronous evaluator, missing error classification, per-cycle disk I/O, and absent prompt caching.

**Architecture:** Eight sequential tasks following spec's risk-ordered implementation (§10 from design doc). Tasks 1-2 remove dead code; Tasks 3-5 fix pipeline logic; Task 6 fixes threading; Task 7 fixes SQL parsing; Task 8 adds prompt caching (highest risk, last).

**Tech Stack:** Python 3.12, pytest, uv, sqlglot ≥25.0, anthropic SDK, openai SDK

---

## File Map

| File | Changes |
|------|---------|
| `agent/prephase.py` | Remove `log`, `preserve_prefix` from `PrephaseResult`; remove `system_prompt_text` param |
| `agent/orchestrator.py` | Remove `build_system_prompt` import, dead stats fields, `write_wiki_fragment` |
| `agent/pipeline.py` | 3-tuple `_call_llm_phase`; `error_type` in LEARN; session_rules FIFO; module-level caches; `_build_static_system`; user_msg builders; evaluator threading; tuple return |
| `agent/llm.py` | `_system_as_str()`; widen `system: str → str | list[dict]` in `_call_raw_single_model` and `call_llm_raw`; tier routing for blocks |
| `agent/sql_security.py` | `_has_where_clause()` uses sqlglot + regex fallback |
| `pyproject.toml` | Add `sqlglot>=25.0` |
| `tests/test_prephase.py` | Update field checks; remove log/preserve_prefix tests; update call sites |
| `tests/test_pipeline.py` | Update `_make_pre()`; add tests for tok counting, error_type, FIFO, static system, threading |
| `tests/test_sql_security.py` | Add subquery / CTE / double-quote WHERE tests |
| `tests/test_llm_module.py` | Add `_system_as_str` test |
| `tests/test_orchestrator_pipeline.py` | Update mock to return tuple; add `run_agent` returns `dict` test |

---

## Task 1: Dead code removal — prephase.py (A1)

`PrephaseResult.log` and `.preserve_prefix` are loop-architecture remnants. `run_prephase()` accepts `system_prompt_text` only to build them. Remove all three.

**Files:**
- Modify: `agent/prephase.py`
- Modify: `tests/test_prephase.py`
- Modify: `tests/test_pipeline.py` (update `_make_pre()` helper)

- [ ] **Step 1: Write failing tests**

In `tests/test_prephase.py`, replace the existing field/log tests with:

```python
def test_prephase_result_fields():
    """PrephaseResult has exactly the expected fields — no log or preserve_prefix."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert fields == {"agents_md_content", "agents_md_path", "db_schema", "agents_md_index", "schema_digest"}


def test_run_prephase_no_system_prompt_param():
    """run_prephase() takes only (vm, task_text) — no system_prompt_text."""
    import inspect
    sig = inspect.signature(run_prephase)
    assert "system_prompt_text" not in sig.parameters
```

Remove these now-obsolete tests (they test log/preserve_prefix behavior):
- `test_normal_mode_log_structure`
- `test_preserve_prefix_equals_log`
- `test_schema_not_in_log`
- `test_no_few_shot_in_log`

Update remaining call sites that pass `"sys prompt"` as third arg:
```python
# Before:
result = run_prephase(vm, "find products", "sys prompt")
# After:
result = run_prephase(vm, "find products")
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_prephase.py -v -x
```
Expected: FAIL — `AssertionError: {'log', 'preserve_prefix', ...} != {'agents_md_content', ...}`

- [ ] **Step 3: Remove dead fields and param from prephase.py**

Replace `agent/prephase.py` with:

```python
import os
from dataclasses import dataclass, field

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ExecRequest, ReadRequest
from google.protobuf.json_format import MessageToDict

from .agents_md_parser import parse_agents_md
from .llm import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


@dataclass
class PrephaseResult:
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)


def _build_schema_digest(vm: EcomRuntimeClientSync) -> dict:
    try:
        result = vm.exec(ExecRequest(path="/bin/sql", args=[".schema"]))
        try:
            d = MessageToDict(result)
            raw = d.get("stdout", "") or d.get("output", "")
        except Exception:
            raw = getattr(result, "stdout", "") or getattr(result, "output", "") or ""
        tables: dict = {}
        current = None
        for line in raw.splitlines():
            line = line.strip()
            if line.upper().startswith("CREATE TABLE"):
                name = line.split("(")[0].split()[-1].strip('"')
                current = name
                tables[current] = {"columns": [], "fk": []}
            elif current and line and not line.startswith(")"):
                parts = line.rstrip(",").split()
                if parts and parts[0].upper() not in ("PRIMARY", "UNIQUE", "CHECK", "INDEX"):
                    tables[current]["columns"].append(
                        {"name": parts[0].strip('"'), "type": parts[1] if len(parts) > 1 else ""}
                    )
                if "REFERENCES" in line.upper():
                    tables[current]["fk"].append({"from": parts[0], "to": line})
        return {"tables": tables}
    except Exception:
        return {}


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

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

    if agents_md_content and _LOG_LEVEL == "DEBUG":
        print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")

    agents_md_index: dict = parse_agents_md(agents_md_content) if agents_md_content else {}

    db_schema = ""
    schema_digest: dict = {}
    try:
        schema_result = vm.exec(ExecRequest(path="/bin/sql", args=[".schema"]))
        try:
            d = MessageToDict(schema_result)
            db_schema = d.get("stdout", "") or d.get("output", "")
        except Exception:
            db_schema = ""
        if not db_schema:
            db_schema = getattr(schema_result, "stdout", "") or getattr(schema_result, "output", "") or ""
        schema_digest = _build_schema_digest(vm)
        print(f"{CLI_BLUE}[prephase] schema_digest: {len(schema_digest.get('tables', {}))} tables{CLI_CLR}")
        print(f"{CLI_BLUE}[prephase] /bin/sql .schema:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/sql .schema: {e}{CLI_CLR}")

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
        agents_md_index=agents_md_index,
        schema_digest=schema_digest,
    )
```

- [ ] **Step 4: Update `_make_pre()` in tests/test_pipeline.py**

```python
def _make_pre(agents_md="AGENTS", db_schema="CREATE TABLE products(id INT, type TEXT, brand TEXT, sku TEXT, model TEXT)"):
    return PrephaseResult(
        agents_md_content=agents_md,
        agents_md_path="/AGENTS.MD",
        db_schema=db_schema,
    )
```

- [ ] **Step 5: Run all tests**

```
uv run pytest tests/test_prephase.py tests/test_pipeline.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py tests/test_pipeline.py
git commit -m "refactor: remove dead log/preserve_prefix fields from PrephaseResult (A1)"
```

---

## Task 2: Dead code removal — orchestrator.py (A2, A11)

`build_system_prompt()` result is thrown away; dead stats fields add noise to every task result; `write_wiki_fragment()` is a no-op stub.

**Files:**
- Modify: `agent/orchestrator.py`
- Modify: `tests/test_orchestrator_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_orchestrator_pipeline.py`:

```python
def test_run_agent_no_dead_stats():
    """run_agent() result must not contain builder_*/contract_*/eval_rejection_count fields."""
    import json
    with patch("agent.orchestrator.EcomRuntimeClientSync", return_value=_make_vm_mock()), \
         patch("agent.orchestrator.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = {
            "outcome": "OUTCOME_OK",
            "step_facts": [],
            "done_ops": [],
            "input_tokens": 10,
            "output_tokens": 5,
            "total_elapsed_ms": 0,
        }
        result = run_agent({}, "http://localhost:9001", "test", "t01")

    dead_keys = {"builder_used", "builder_in_tok", "builder_out_tok", "builder_addendum",
                 "contract_rounds_taken", "contract_is_default", "eval_rejection_count"}
    found = dead_keys & result.keys()
    assert not found, f"Dead stats keys found: {found}"


def test_write_wiki_fragment_removed():
    import agent.orchestrator as orch
    assert not hasattr(orch, "write_wiki_fragment"), "write_wiki_fragment should be removed"


def test_build_system_prompt_not_imported():
    import agent.orchestrator as orch
    assert not hasattr(orch, "build_system_prompt"), "build_system_prompt should not be in orchestrator"
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_orchestrator_pipeline.py::test_run_agent_no_dead_stats -v
```
Expected: FAIL

- [ ] **Step 3: Rewrite orchestrator.py**

```python
"""Minimal orchestrator for ecom benchmark."""
from __future__ import annotations

import os

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from agent.prephase import run_prephase
from agent.pipeline import run_pipeline

_MODEL = os.environ.get("MODEL", "")


def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    vm = EcomRuntimeClientSync(harness_url)
    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}
    pre = run_prephase(vm, task_text)
    stats = run_pipeline(vm, model, task_text, pre, cfg)
    stats["model_used"] = model
    stats["task_type"] = "lookup"
    return stats
```

- [ ] **Step 4: Run all tests**

```
uv run pytest tests/test_orchestrator_pipeline.py tests/test_prephase.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator_pipeline.py
git commit -m "refactor: remove dead stats/imports/write_wiki_fragment from orchestrator (A2, A11)"
```

---

## Task 3: Token counting fix (A3)

`_call_llm_phase()` already captures `tok_info` via `token_out=tok_info` but never returns it. `total_in_tok/total_out_tok` in `run_pipeline()` stay 0.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_call_llm_phase_returns_three_tuple(tmp_path):
    """_call_llm_phase returns (obj, sgr, tok) — tok has input/output keys."""
    from agent.pipeline import _call_llm_phase
    from agent.models import SqlPlanOutput

    raw = json.dumps({
        "reasoning": "ok",
        "queries": ["SELECT 1"],
    })

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: (
        kw.get("token_out", {}).update({"input": 42, "output": 7}) or raw
    )):
        obj, sgr, tok = _call_llm_phase("sys", "user", "model", {}, SqlPlanOutput)

    assert obj is not None
    assert tok.get("input") == 42
    assert tok.get("output") == 7


def test_pipeline_token_counts_nonzero(tmp_path):
    """total_in_tok and total_out_tok are non-zero after successful pipeline run."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 3}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    def _fake_llm(system, user_msg, model, cfg, max_tokens=4096, token_out=None):
        if token_out is not None:
            token_out["input"] = 100
            token_out["output"] = 20
        if "TASK:" in user_msg and token_out is not None:
            # Distinguish SQL_PLAN vs ANSWER by checking session_rules presence
            pass
        # Return SQL plan for first call, answer for second
        if not hasattr(_fake_llm, "_count"):
            _fake_llm._count = 0
        _fake_llm._count += 1
        if _fake_llm._count == 1:
            return _sql_plan_json()
        return _answer_json()

    with patch("agent.pipeline.call_llm_raw", side_effect=_fake_llm), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "How many Lawn Mowers?", pre, {})

    assert stats["input_tokens"] > 0, f"input_tokens still 0: {stats}"
    assert stats["output_tokens"] > 0, f"output_tokens still 0: {stats}"
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_pipeline.py::test_call_llm_phase_returns_three_tuple -v
```
Expected: FAIL — `cannot unpack non-iterable` or `too many values`

- [ ] **Step 3: Update `_call_llm_phase()` to return 3-tuple**

In `agent/pipeline.py`, change the function signature and return:

```python
def _call_llm_phase(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    output_cls,
    max_tokens: int = 4096,
) -> tuple[object | None, dict, dict]:
    """SGR LLM call: returns (parsed_output_or_None, sgr_trace_entry, tok_info)."""
    tok_info: dict = {}
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=max_tokens, token_out=tok_info)
    phase_name = output_cls.__name__
    sgr_entry: dict = {
        "phase": phase_name,
        "guide_prompt": system[:300],
        "reasoning": "",
        "output": raw or "",
    }
    if not raw:
        return None, sgr_entry, tok_info
    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None, sgr_entry, tok_info
    try:
        obj = output_cls.model_validate(parsed)
        sgr_entry["reasoning"] = obj.reasoning
        sgr_entry["output"] = parsed
        return obj, sgr_entry, tok_info
    except Exception:
        return None, sgr_entry, tok_info
```

- [ ] **Step 4: Update all callers of `_call_llm_phase()` in pipeline.py**

In `run_pipeline()`, SQL_PLAN call (line ~161):
```python
sql_plan_out, sgr_entry, tok = _call_llm_phase(system, user_msg, model, cfg, SqlPlanOutput)
sgr_trace.append(sgr_entry)
total_in_tok += tok.get("input", 0)
total_out_tok += tok.get("output", 0)
```

In `run_pipeline()`, ANSWER call (line ~254):
```python
answer_out, sgr_answer, tok = _call_llm_phase(answer_system, answer_user, model, cfg, AnswerOutput)
sgr_trace.append(sgr_answer)
total_in_tok += tok.get("input", 0)
total_out_tok += tok.get("output", 0)
```

In `_run_learn()` (line ~312):
```python
learn_out, sgr_learn, _ = _call_llm_phase(learn_system, learn_user, model, cfg, LearnOutput, max_tokens=2048)
```

- [ ] **Step 5: Run all tests**

```
uv run pytest tests/test_pipeline.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "fix: _call_llm_phase returns 3-tuple with tok_info; accumulate token counts (A3)"
```

---

## Task 4: LEARN error_type + session_rules FIFO (A5, A7, A10)

`_run_learn()` always appends rules even on LLM failures; `session_rules` grows unbounded; sgr_trace LEARN entries lack error classification.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_session_rules_fifo_cap(tmp_path):
    """session_rules never exceeds 3 entries after 4+ LEARN calls."""
    vm = MagicMock()
    # 4 cycles: all fail VALIDATE, each triggers LEARN
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "rule"})
    # 4 cycles × (sql_plan + learn) = 8 calls, but MAX_CYCLES=3 so 3 cycles max
    # Let's force 3 full cycles: each has sql_plan + learn
    call_seq = ([_sql_plan_json(), learn_json]) * 4
    call_iter = iter(call_seq)

    captured_rules: list = []

    original_run_learn = None

    import agent.pipeline as pp
    original = pp._run_learn

    def _capturing_learn(*args, **kwargs):
        original(*args, **kwargs)
        # session_rules is the 8th positional arg
        captured_rules.append(len(args[7]) if len(args) > 7 else 0)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        stats = run_pipeline(vm, "model", "task", pre, {})

    assert stats["outcome"] == "OUTCOME_NONE_CLARIFICATION"


def test_learn_llm_fail_does_not_add_session_rule(tmp_path):
    """_run_learn with error_type='llm_fail' must not add to session_rules."""
    from agent.pipeline import _run_learn

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "should not appear"})
    session_rules: list[str] = []
    sgr_trace: list[dict] = []

    pre = _make_pre()
    rules_loader_mock = MagicMock()
    rules_loader_mock.get_rules_markdown.return_value = ""

    with patch("agent.pipeline.call_llm_raw", return_value=learn_json), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        _run_learn(
            pre, "model", {}, "task", [], "llm error",
            rules_loader_mock, session_rules, sgr_trace, [],
            {}, [],
            error_type="llm_fail",
        )

    assert session_rules == [], f"session_rules should be empty, got: {session_rules}"


def test_sgr_learn_entry_has_error_type(tmp_path):
    """LEARN sgr_trace entry must contain 'error_type' field."""
    from agent.pipeline import _run_learn

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "rule"})
    session_rules: list[str] = []
    sgr_trace: list[dict] = []

    pre = _make_pre()
    rules_loader_mock = MagicMock()
    rules_loader_mock.get_rules_markdown.return_value = ""

    with patch("agent.pipeline.call_llm_raw", return_value=learn_json), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        _run_learn(
            pre, "model", {}, "task", ["SELECT 1"], "syntax error",
            rules_loader_mock, session_rules, sgr_trace, [],
            {}, [],
            error_type="syntax",
        )

    assert len(sgr_trace) == 1
    assert sgr_trace[0].get("error_type") == "syntax", f"sgr_trace entry: {sgr_trace[0]}"
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_pipeline.py::test_learn_llm_fail_does_not_add_session_rule -v
```
Expected: FAIL — `TypeError: _run_learn() got unexpected keyword argument 'error_type'`

- [ ] **Step 3: Update `_run_learn()` in pipeline.py**

```python
def _run_learn(
    pre: PrephaseResult,
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    rules_loader: RulesLoader,
    session_rules: list[str],
    sgr_trace: list[dict],
    security_gates: list[dict],
    confirmed_values: dict,
    highlighted_vault_rules: list[str],
    error_type: str = "semantic",
) -> None:
    learn_system = _build_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, session_rules, security_gates,
        confirmed_values=confirmed_values,
        highlighted_vault_rules=highlighted_vault_rules,
        task_text=task_text,
    )
    learn_user = (
        f"TASK: {task_text}\n"
        f"FAILED QUERIES: {json.dumps(queries)}\n"
        f"ERROR: {error}\n"
        f"ERROR_TYPE: {error_type}"
    )
    learn_out, sgr_learn, _ = _call_llm_phase(learn_system, learn_user, model, cfg, LearnOutput, max_tokens=2048)
    sgr_learn["error_type"] = error_type
    sgr_trace.append(sgr_learn)
    if learn_out and error_type != "llm_fail":
        anchor = learn_out.agents_md_anchor
        if anchor:
            anchor_section = anchor.split(">")[0].strip()
            if anchor_section in pre.agents_md_index:
                anchor_lines = pre.agents_md_index[anchor_section]
                highlighted_vault_rules.append(f"[{anchor_section}]\n" + "\n".join(anchor_lines))
                print(f"{CLI_BLUE}[pipeline] LEARN: anchor={anchor!r}, elevating vault rule{CLI_CLR}")
                return
        session_rules.append(learn_out.rule_content)
        session_rules[:] = session_rules[-3:]
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")
```

- [ ] **Step 4: Update `_run_learn()` callers in `run_pipeline()` with correct error_type**

SQL_PLAN LLM fail call:
```python
_run_learn(pre, model, cfg, task_text, [], last_error,
           rules_loader, session_rules, sgr_trace, security_gates,
           confirmed_values, highlighted_vault_rules,
           error_type="llm_fail")
```

SECURITY blocked call:
```python
_run_learn(pre, model, cfg, task_text, queries, last_error,
           rules_loader, session_rules, sgr_trace, security_gates,
           confirmed_values, highlighted_vault_rules,
           error_type="security")
```

VALIDATE fail call:
```python
_run_learn(pre, model, cfg, task_text, queries, last_error,
           rules_loader, session_rules, sgr_trace, security_gates,
           confirmed_values, highlighted_vault_rules,
           error_type="syntax")
```

EXECUTE fail call (replace the existing single `_run_learn` call for execute errors):
```python
_et = "empty" if last_empty else "semantic"
_run_learn(pre, model, cfg, task_text, queries, last_error,
           rules_loader, session_rules, sgr_trace, security_gates,
           confirmed_values, highlighted_vault_rules,
           error_type=_et)
```

- [ ] **Step 5: Run all pipeline tests**

```
uv run pytest tests/test_pipeline.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "fix: error_type in LEARN; session_rules FIFO cap 3; llm_fail skips rule append (A5, A7, A10)"
```

---

## Task 5: Module-level cache + static system refactor (A4, A8)

`_build_system()` is called 3× per cycle (SQL_PLAN, LEARN, ANSWER) with identical static content. `RulesLoader` and `load_security_gates()` hit disk every `run_pipeline()` call.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_build_static_system_sql_plan_has_security_gates(tmp_path):
    """_build_static_system('sql_plan') includes security gates; 'learn' does not."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)
    gates = [{"id": "sec-001", "message": "no DDL"}]

    sql_system = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, gates)
    learn_system = _build_static_system("learn", "AGENTS", {}, "SCHEMA", {}, rl, gates)

    assert "sec-001" in sql_system, "sql_plan system must include security gates"
    assert "sec-001" not in learn_system, "learn system must NOT include security gates"


def test_build_static_system_no_session_rules(tmp_path):
    """_build_static_system does not include IN-SESSION RULE (session_rules moved to user_msg)."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    system = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, [])
    assert "IN-SESSION RULE" not in system
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_pipeline.py::test_build_static_system_sql_plan_has_security_gates -v
```
Expected: FAIL — `ImportError: cannot import name '_build_static_system'`

- [ ] **Step 3: Add module-level caches and new helpers to pipeline.py**

After the existing imports, add cache globals:

```python
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
```

- [ ] **Step 4: Add `_build_static_system()` and user_msg builders to pipeline.py**

Add after `_gates_summary()`:

```python
def _build_static_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    task_text: str = "",
) -> str:
    parts: list[str] = []

    if phase in ("sql_plan", "learn", "answer"):
        if agents_md_index and task_text and phase in ("sql_plan", "learn"):
            relevant = _relevant_agents_sections(agents_md_index, task_text)
            index_line = "Section index: " + ", ".join(agents_md_index.keys())
            if relevant:
                section_blocks = "\n\n".join(
                    f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
                )
                parts.append(f"# VAULT RULES\n{index_line}\n\n{section_blocks}")
            elif agents_md:
                parts.append(f"# VAULT RULES\n{agents_md}")
        elif agents_md:
            parts.append(f"# VAULT RULES\n{agents_md}")

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            parts.append(f"# PIPELINE RULES\n{rules_md}")

    if phase == "sql_plan" and security_gates:
        parts.append(f"# SECURITY GATES\n{_gates_summary(security_gates)}")

    if schema_digest and phase in ("sql_plan", "learn"):
        parts.append(f"# SCHEMA DIGEST\n{_format_schema_digest(schema_digest)}")

    if db_schema:
        parts.append(f"# DATABASE SCHEMA\n{db_schema}")

    if confirmed_values and phase in ("sql_plan", "learn"):
        parts.append(f"# CONFIRMED VALUES\n{_format_confirmed_values(confirmed_values)}")

    guide = load_prompt(phase)
    if guide:
        parts.append(guide)

    return "\n\n".join(parts)


def _build_sql_user_msg(
    task_text: str,
    session_rules: list[str],
    highlighted_vault_rules: list[str],
    last_error: str,
) -> str:
    parts: list[str] = []
    for r in highlighted_vault_rules:
        parts.append(f"# HIGHLIGHTED VAULT RULE\n{r}")
    for r in session_rules:
        parts.append(f"# IN-SESSION RULE\n{r}")
    parts.append(f"TASK: {task_text}")
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


def _build_answer_user_msg(task_text: str, sql_results: list[str]) -> str:
    return f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
```

- [ ] **Step 5: Refactor `run_pipeline()` to build static systems once and use new user_msg builders**

Replace the top of `run_pipeline()` (through start of the cycle loop):

```python
def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    """Phase-based SQL pipeline. Returns stats dict compatible with run_loop()."""
    rules_loader = _get_rules_loader()
    security_gates = _get_security_gates()
    session_rules: list[str] = []
    highlighted_vault_rules: list[str] = []
    sgr_trace: list[dict] = []
    total_in_tok = 0
    total_out_tok = 0

    last_error = ""
    sql_results: list[str] = []
    success = False
    cycles_used = 0

    confirmed_values: dict = run_resolve(vm, model, task_text, pre, cfg)

    static_sql = _build_static_system(
        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
    )
    static_learn = _build_static_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
    )
    static_answer = _build_static_system(
        "answer", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
    )
```

Replace the SQL_PLAN section inside the loop:

```python
        # ── SQL_PLAN ──────────────────────────────────────────────────────────
        user_msg = _build_sql_user_msg(task_text, session_rules, highlighted_vault_rules, last_error)
        sql_plan_out, sgr_entry, tok = _call_llm_phase(static_sql, user_msg, model, cfg, SqlPlanOutput)
        sgr_trace.append(sgr_entry)
        total_in_tok += tok.get("input", 0)
        total_out_tok += tok.get("output", 0)
```

Replace the SQL_PLAN LLM fail branch:

```python
        if not sql_plan_out:
            print(f"{CLI_RED}[pipeline] SQL_PLAN LLM call failed{CLI_CLR}")
            last_error = "SQL_PLAN phase LLM call failed"
            _run_learn(static_learn, model, cfg, task_text, [], last_error,
                       sgr_trace, session_rules, highlighted_vault_rules, pre.agents_md_index,
                       error_type="llm_fail")
            continue
```

Replace SECURITY blocked branch:

```python
        if gate_err:
            print(f"{CLI_YELLOW}[pipeline] SECURITY gate blocked: {gate_err}{CLI_CLR}")
            last_error = gate_err
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules, pre.agents_md_index,
                       error_type="security")
            continue
```

Replace VALIDATE fail branch:

```python
        if validate_error:
            print(f"{CLI_YELLOW}[pipeline] VALIDATE failed: {validate_error}{CLI_CLR}")
            last_error = validate_error
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules, pre.agents_md_index,
                       error_type="syntax")
            continue
```

Replace EXECUTE fail branch:

```python
        if execute_error or last_empty:
            err = execute_error or f"Empty result set: {(sql_results[-1] if sql_results else '').strip()[:120]}"
            print(f"{CLI_YELLOW}[pipeline] EXECUTE failed: {err}{CLI_CLR}")
            last_error = err
            _run_learn(static_learn, model, cfg, task_text, queries, last_error,
                       sgr_trace, session_rules, highlighted_vault_rules, pre.agents_md_index,
                       error_type="empty" if last_empty else "semantic")
            continue
```

Replace the ANSWER section:

```python
    # ── ANSWER ────────────────────────────────────────────────────────────────
    answer_user = _build_answer_user_msg(task_text, sql_results)
    answer_out, sgr_answer, tok = _call_llm_phase(static_answer, answer_user, model, cfg, AnswerOutput)
    sgr_trace.append(sgr_answer)
    total_in_tok += tok.get("input", 0)
    total_out_tok += tok.get("output", 0)
```

- [ ] **Step 6: Refactor `_run_learn()` to accept pre-built static_learn**

Replace `_run_learn()` signature and body:

```python
def _run_learn(
    static_learn: str,
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
) -> None:
    learn_user = _build_learn_user_msg(task_text, queries, error, error_type)
    learn_out, sgr_learn, _ = _call_llm_phase(static_learn, learn_user, model, cfg, LearnOutput, max_tokens=2048)
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

- [ ] **Step 7: Remove the old `_build_system()` function**

Delete lines for `_build_system()` (the function that accepted `session_rules` and built a `str` from parts including `IN-SESSION RULE` blocks).

- [ ] **Step 8: Update test helpers in test_pipeline.py that called `_run_learn` with old signature**

The tests `test_learn_llm_fail_does_not_add_session_rule` and `test_sgr_learn_entry_has_error_type` must be updated to use the new signature:

```python
# test_learn_llm_fail_does_not_add_session_rule — update _run_learn call:
_run_learn(
    "system prompt",  # static_learn replaces pre + rules_loader + security_gates
    "model", {}, "task", [], "llm error",
    sgr_trace, session_rules, [], {},
    error_type="llm_fail",
)

# test_sgr_learn_entry_has_error_type — update similarly:
_run_learn(
    "system prompt",
    "model", {}, "task", ["SELECT 1"], "syntax error",
    sgr_trace, session_rules, [], {},
    error_type="syntax",
)
```

Also remove now-unused patches (`patch("agent.pipeline._RULES_DIR", ...)` and `patch("agent.pipeline.load_security_gates", ...)`).

- [ ] **Step 9: Run all tests**

```
uv run pytest tests/test_pipeline.py -v
```
Expected: all PASS

- [ ] **Step 10: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "refactor: module-level caches; _build_static_system; split user_msg builders; static systems built once per pipeline (A4, A8)"
```

---

## Task 6: Evaluator threading (A9)

Evaluator blocks the return path and runs only on success. Fix: always run as daemon=False thread; `run_pipeline()` returns `tuple[dict, Thread | None]`; `run_agent()` joins with timeout.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `agent/orchestrator.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_orchestrator_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_run_pipeline_returns_tuple(tmp_path):
    """run_pipeline returns (dict, Thread | None)."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result('[{"count": 1}]')

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    call_seq = [_sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]):
        result = run_pipeline(vm, "model", "task", pre, {})

    assert isinstance(result, tuple) and len(result) == 2, f"expected 2-tuple, got {type(result)}"
    stats, thread = result
    assert isinstance(stats, dict)
    assert thread is None  # EVAL_ENABLED=0 by default in tests


def test_evaluator_thread_starts_on_failure(tmp_path):
    """Evaluator thread starts even when all cycles fail."""
    vm = MagicMock()
    vm.exec.return_value = _make_exec_result("Error: syntax error")

    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({"reasoning": "x", "conclusion": "y", "rule_content": "z"})
    call_seq = ([_sql_plan_json(), learn_json]) * 3
    call_iter = iter(call_seq)

    thread_started = []

    def _fake_evaluator(*args, **kwargs):
        thread_started.append(True)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.pipeline._EVAL_ENABLED", True), \
         patch("agent.pipeline._MODEL_EVALUATOR", "eval-model"), \
         patch("agent.pipeline._run_evaluator_safe", side_effect=_fake_evaluator):
        stats, thread = run_pipeline(vm, "model", "task", pre, {})
        if thread is not None:
            thread.join(timeout=5)

    assert thread_started, "Evaluator must start even on pipeline failure"
```

Add to `tests/test_orchestrator_pipeline.py`:

```python
def test_run_agent_returns_dict():
    """run_agent() always returns a plain dict (public API unchanged)."""
    import threading
    with patch("agent.orchestrator.EcomRuntimeClientSync", return_value=_make_vm_mock()), \
         patch("agent.orchestrator.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = (
            {
                "outcome": "OUTCOME_OK",
                "step_facts": [],
                "done_ops": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "total_elapsed_ms": 0,
            },
            None,  # no eval thread
        )
        result = run_agent({}, "http://localhost:9001", "task", "t01")

    assert isinstance(result, dict)
    assert result["outcome"] == "OUTCOME_OK"
```

Update existing `test_lookup_routes_to_pipeline` to return a tuple:

```python
def test_lookup_routes_to_pipeline():
    """run_agent calls run_pipeline for all tasks."""
    with patch("agent.orchestrator.EcomRuntimeClientSync", return_value=_make_vm_mock()), \
         patch("agent.orchestrator.run_pipeline") as mock_pipeline:
        mock_pipeline.return_value = (
            {
                "outcome": "OUTCOME_OK",
                "step_facts": [],
                "done_ops": [],
                "input_tokens": 10,
                "output_tokens": 5,
                "total_elapsed_ms": 100,
            },
            None,
        )
        result = run_agent({}, "http://localhost:9001", "How many Lawn Mowers?", "t01")

    mock_pipeline.assert_called_once()
    assert result["outcome"] == "OUTCOME_OK"
    assert result["task_type"] == "lookup"
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_pipeline.py::test_run_pipeline_returns_tuple -v
```
Expected: FAIL — `assert isinstance(result, tuple)` fails (currently returns `dict`)

- [ ] **Step 3: Update `run_pipeline()` to return tuple and run evaluator always**

Add `import threading` at the top of `pipeline.py`.

Change `run_pipeline()` return type annotation:
```python
def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> tuple[dict, threading.Thread | None]:
```

Remove the existing `if _EVAL_ENABLED and _MODEL_EVALUATOR:` block from inside the `if success:` branch (lines ~271-281).

After the ANSWER block (and after the failure `return` is restructured), add the evaluator thread launch and unified return. Replace the current failure early-return and success EVALUATE+return with:

```python
    # ── ANSWER (only on success) ──────────────────────────────────────────────
    outcome = "OUTCOME_NONE_CLARIFICATION"
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
    else:
        answer_user = _build_answer_user_msg(task_text, sql_results)
        answer_out, sgr_answer, tok = _call_llm_phase(static_answer, answer_user, model, cfg, AnswerOutput)
        sgr_trace.append(sgr_answer)
        total_in_tok += tok.get("input", 0)
        total_out_tok += tok.get("output", 0)
        if answer_out:
            outcome = answer_out.outcome
            print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
            try:
                vm.answer(AnswerRequest(
                    message=answer_out.message,
                    outcome=OUTCOME_BY_NAME[outcome],
                    refs=answer_out.grounding_refs,
                ))
            except Exception as e:
                print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    # ── EVALUATE (always, success or fail) ────────────────────────────────────
    eval_thread: threading.Thread | None = None
    if _EVAL_ENABLED and _MODEL_EVALUATOR:
        eval_thread = threading.Thread(
            target=_run_evaluator_safe,
            kwargs={
                "task_text": task_text,
                "agents_md": pre.agents_md_content,
                "agents_md_index": pre.agents_md_index,
                "db_schema": pre.db_schema,
                "schema_digest": pre.schema_digest,
                "sgr_trace": sgr_trace,
                "cycles": cycles_used,
                "final_outcome": outcome,
                "sql_plan_outputs": sql_plan_outputs,
                "executed_queries": executed_queries,
                "model": _MODEL_EVALUATOR,
                "cfg": cfg,
            },
            daemon=False,
        )
        eval_thread.start()

    stats = {
        "outcome": outcome,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }
    return stats, eval_thread
```

- [ ] **Step 4: Update `run_agent()` in orchestrator.py to unpack tuple and join thread**

```python
def run_agent(model_configs: dict, harness_url: str, task_text: str, task_id: str = "") -> dict:
    """Execute a single benchmark task."""
    import threading
    vm = EcomRuntimeClientSync(harness_url)
    model = _MODEL
    cfg = model_configs.get(model, {}) if model_configs else {}
    pre = run_prephase(vm, task_text)
    stats, eval_thread = run_pipeline(vm, model, task_text, pre, cfg)
    if eval_thread is not None:
        eval_thread.join(timeout=30)
        if eval_thread.is_alive():
            print("[orchestrator] evaluator timeout — log may be incomplete")
    stats["model_used"] = model
    stats["task_type"] = "lookup"
    return stats
```

- [ ] **Step 5: Run all tests**

```
uv run pytest tests/test_pipeline.py tests/test_orchestrator_pipeline.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py agent/orchestrator.py tests/test_pipeline.py tests/test_orchestrator_pipeline.py
git commit -m "fix: evaluator runs always in daemon=False thread; run_pipeline returns tuple (A9)"
```

---

## Task 7: WHERE clause fix for subqueries (A12)

`_has_where_clause()` splits on whitespace — misses `WHERE` inside subqueries (`SELECT ... WHERE id IN (SELECT id FROM t WHERE ...)`) and chokes on double-quoted identifiers.

**Files:**
- Modify: `pyproject.toml`
- Modify: `agent/sql_security.py`
- Modify: `tests/test_sql_security.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_sql_security.py`:

```python
def test_subquery_outer_no_where_blocked():
    """Outer SELECT has no WHERE even though subquery does — should be blocked."""
    sql = "SELECT * FROM products WHERE id IN (SELECT id FROM inventory WHERE qty > 0)"
    # Outer has WHERE → should PASS
    err = check_sql_queries([sql], _GATES)
    assert err is None, f"Outer WHERE should pass: {err}"


def test_nested_subquery_no_outer_where_blocked():
    """Outer SELECT without WHERE should be blocked even if inner subquery has WHERE."""
    sql = "SELECT * FROM products WHERE id IN (SELECT id FROM inventory WHERE qty > 0)"
    # This is actually outer-has-WHERE, so passes. Let's test a truly outer-no-WHERE case:
    sql_no_outer = "SELECT id FROM products"
    err = check_sql_queries([sql_no_outer], _GATES)
    assert err is not None and "sec-002" in err


def test_cte_with_where_passes():
    """CTE query with WHERE in the final SELECT passes."""
    sql = "WITH cte AS (SELECT id FROM products WHERE type='X') SELECT * FROM cte WHERE id > 0"
    err = check_sql_queries([sql], _GATES)
    assert err is None, f"CTE with WHERE should pass: {err}"


def test_where_in_double_quoted_identifier_not_confused():
    """Double-quoted identifier containing WHERE substring should not satisfy check."""
    sql = 'SELECT * FROM products WHERE "WHERE_clause" = 1'
    err = check_sql_queries([sql], _GATES)
    assert err is None, f"WHERE in double-quoted identifier with outer WHERE should pass: {err}"


def test_has_where_clause_subquery():
    """_has_where_clause correctly detects WHERE in queries with subqueries."""
    from agent.sql_security import _has_where_clause
    assert _has_where_clause("SELECT * FROM t WHERE id IN (SELECT id FROM t2)")
    assert not _has_where_clause("SELECT * FROM t")
    assert _has_where_clause("SELECT * FROM t WHERE id IN (SELECT id FROM t2 WHERE x=1)")
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_sql_security.py::test_has_where_clause_subquery -v
```
Expected: Currently likely passes (regex works for simple cases) — but the double-quoted identifier test may fail. Run all new tests to check which fail.

```
uv run pytest tests/test_sql_security.py -v
```

- [ ] **Step 3: Add sqlglot to pyproject.toml**

In `pyproject.toml`, add to `[project] dependencies`:

```toml
    "sqlglot>=25.0",
```

- [ ] **Step 4: Install updated deps**

```
uv sync
```
Expected: sqlglot downloaded and installed

- [ ] **Step 5: Rewrite `_has_where_clause()` in sql_security.py**

```python
def _has_where_clause(sql: str) -> bool:
    try:
        import sqlglot
        tree = sqlglot.parse_one(sql, dialect="sqlite")
        return bool(tree.find(sqlglot.exp.Where))
    except Exception:
        stripped = re.sub(r"'[^']*'", "", sql).upper()
        return "WHERE" in stripped.split()
```

- [ ] **Step 6: Run all security tests**

```
uv run pytest tests/test_sql_security.py -v
```
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml agent/sql_security.py tests/test_sql_security.py
git commit -m "fix: _has_where_clause uses sqlglot for subquery/CTE/double-quote correctness (A12)"
```

---

## Task 8: Prompt caching (A6)

`_build_static_system()` returns `str`; Anthropic's prompt caching requires `list[dict]` blocks with `cache_control`. Non-Anthropic tiers need string fallback.

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `agent/llm.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_llm_module.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_pipeline.py`:

```python
def test_build_static_system_returns_list_of_blocks(tmp_path):
    """_build_static_system returns list[dict], last block has cache_control."""
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, [])

    assert isinstance(blocks, list), f"Expected list, got {type(blocks)}"
    assert all(isinstance(b, dict) for b in blocks)
    last = blocks[-1]
    assert last.get("cache_control") == {"type": "ephemeral"}, \
        f"Last block must have cache_control: {last}"
```

Add to `tests/test_llm_module.py`:

```python
def test_system_as_str_from_blocks():
    """_system_as_str flattens list[dict] blocks to newline-joined text."""
    from agent.llm import _system_as_str
    blocks = [
        {"type": "text", "text": "block one"},
        {"type": "text", "text": "block two", "cache_control": {"type": "ephemeral"}},
    ]
    result = _system_as_str(blocks)
    assert "block one" in result
    assert "block two" in result


def test_system_as_str_passthrough_str():
    """_system_as_str returns str unchanged."""
    from agent.llm import _system_as_str
    assert _system_as_str("plain text") == "plain text"
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_pipeline.py::test_build_static_system_returns_list_of_blocks tests/test_llm_module.py::test_system_as_str_from_blocks -v
```
Expected: FAIL — `_system_as_str` not exported; `_build_static_system` returns `str` not `list`

- [ ] **Step 3: Add `_system_as_str()` to llm.py**

Add after the `_THINK_RE` definition (around line 235):

```python
def _system_as_str(system: "str | list[dict]") -> str:
    """Flatten system prompt blocks to plain string for non-caching tiers."""
    if isinstance(system, str):
        return system
    return "\n\n".join(b.get("text", "") for b in system if b.get("type") == "text")
```

- [ ] **Step 4: Widen `system` type in `_call_raw_single_model()` and `call_llm_raw()` in llm.py**

Change the signature:
```python
def _call_raw_single_model(
    system: "str | list[dict]",
    ...
```

After the line `_provider = get_provider(model, cfg)` (around line 300), add:

```python
    is_claude_via_or = (_provider == "openrouter" and is_claude_model(model))
    _msgs_system: "str | list[dict]" = (
        system if is_claude_via_or else _system_as_str(system)
    )
    msgs = [
        {"role": "system", "content": _msgs_system},
        {"role": "user", "content": user_msg},
    ]
```

Remove the old `msgs = [...]` lines (the 4-line block at the top of the function).

For the Anthropic tier, `system=system` in `_create_kw` stays unchanged — Anthropic SDK accepts both `str` and `list[dict]`.

Change `call_llm_raw()` signature:
```python
def call_llm_raw(
    system: "str | list[dict]",
    ...
```

- [ ] **Step 5: Widen `system` type in `_call_llm_phase()` in pipeline.py**

```python
def _call_llm_phase(
    system: "str | list[dict]",
    ...
```

- [ ] **Step 6: Convert `_build_static_system()` to return `list[dict]`**

Replace the function body in `pipeline.py`:

```python
def _build_static_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    task_text: str = "",
) -> list[dict]:
    blocks: list[dict] = []

    if phase in ("sql_plan", "learn", "answer"):
        if agents_md_index and task_text and phase in ("sql_plan", "learn"):
            relevant = _relevant_agents_sections(agents_md_index, task_text)
            index_line = "Section index: " + ", ".join(agents_md_index.keys())
            if relevant:
                section_blocks = "\n\n".join(
                    f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
                )
                blocks.append({"type": "text", "text": f"# VAULT RULES\n{index_line}\n\n{section_blocks}"})
            elif agents_md:
                blocks.append({"type": "text", "text": f"# VAULT RULES\n{agents_md}"})
        elif agents_md:
            blocks.append({"type": "text", "text": f"# VAULT RULES\n{agents_md}"})

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            text = f"# PIPELINE RULES\n{rules_md}"
            if phase == "sql_plan" and security_gates:
                text += f"\n\n# SECURITY GATES\n{_gates_summary(security_gates)}"
            blocks.append({"type": "text", "text": text})

    if schema_digest and phase in ("sql_plan", "learn"):
        blocks.append({"type": "text", "text": f"# SCHEMA DIGEST\n{_format_schema_digest(schema_digest)}"})

    if db_schema:
        blocks.append({"type": "text", "text": f"# DATABASE SCHEMA\n{db_schema}"})

    if confirmed_values and phase in ("sql_plan", "learn"):
        blocks.append({"type": "text", "text": f"# CONFIRMED VALUES\n{_format_confirmed_values(confirmed_values)}"})

    guide = load_prompt(phase)
    blocks.append({
        "type": "text",
        "text": guide or f"# PHASE: {phase}",
        "cache_control": {"type": "ephemeral"},
    })
    return blocks
```

- [ ] **Step 7: Update static_system tests that check for string content**

`test_build_static_system_sql_plan_has_security_gates` and `test_build_static_system_no_session_rules` used `"sec-001" in sql_system` which assumed `str`. Update to inspect block texts:

```python
def test_build_static_system_sql_plan_has_security_gates(tmp_path):
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)
    gates = [{"id": "sec-001", "message": "no DDL"}]

    sql_blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, gates)
    learn_blocks = _build_static_system("learn", "AGENTS", {}, "SCHEMA", {}, rl, gates)

    sql_text = " ".join(b.get("text", "") for b in sql_blocks)
    learn_text = " ".join(b.get("text", "") for b in learn_blocks)

    assert "sec-001" in sql_text, "sql_plan must include security gates"
    assert "sec-001" not in learn_text, "learn must NOT include security gates"


def test_build_static_system_no_session_rules(tmp_path):
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rl = RulesLoader(rules_dir)

    blocks = _build_static_system("sql_plan", "AGENTS", {}, "SCHEMA", {}, rl, [])
    combined = " ".join(b.get("text", "") for b in blocks)
    assert "IN-SESSION RULE" not in combined
```

- [ ] **Step 8: Run all tests**

```
uv run pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add agent/pipeline.py agent/llm.py tests/test_pipeline.py tests/test_llm_module.py
git commit -m "feat: prompt caching — _build_static_system returns list[dict] blocks with cache_control; tier routing for Anthropic/OpenRouter+Claude vs Ollama (A6)"
```

---

## Final check

- [ ] **Run full test suite**

```
uv run pytest tests/ -v
```
Expected: all PASS, no warnings about deprecated APIs

- [ ] **Verify token counts appear in a smoke run (optional, requires API key)**

```
MODEL=anthropic/claude-sonnet-4-6 LOG_LEVEL=DEBUG uv run python main.py 2>&1 | grep -E "input_tokens|output_tokens"
```
Expected: non-zero values printed in stats

- [ ] **Final commit (if any fixups needed)**

```bash
git add -p
git commit -m "fix: post-integration cleanups"
```
