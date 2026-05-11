# Agent Type/Subtype Re-Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add type:subtype hierarchy to the agent pipeline so ecom1-dev lookup tasks route to SQL-optimised strategies, eliminating context overflow and FIX-345 false positives.

**Architecture:** Extend `task_types.json` with per-type `subtypes` dict; thread `task_subtype` through classifier → prephase → prompt → evaluator; replace the single `run_prephase` with a 4-strategy dispatcher keyed by `prephase_strategy`.

**Tech Stack:** Python 3.11, DSPy, Pydantic v2, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `data/task_types.json` | Modify | Add `subtypes`, `default_subtype`, `prephase_strategy` |
| `agent/task_types.py` | Modify | `get_subtype_config()`, `get_prephase_strategy()`, `is_discovery_gate_exempt()` |
| `agent/contracts/__init__.py` | Modify | Add `task_subtype` to `ClassificationResult`, `PlannerInput`, `ExecutorInput`, `WikiReadRequest` |
| `agent/classifier.py` | Modify | New DSPy OutputFields; `_log_subtype_candidate()`; return subtype from `classify_task_llm` |
| `agent/agents/classifier_agent.py` | Modify | Return `task_subtype` in `ClassificationResult` |
| `agent/prephase.py` | Modify | Replace monolithic `run_prephase` with strategy dispatch |
| `agent/prompt.py` | Modify | Two-level `_TASK_BLOCKS`; `get_task_block(type, subtype)` |
| `agent/loop.py` | Modify | Pass `task_subtype` to discovery gate; fix `error_counts` tuple key |
| `agent/security.py` | Modify | `check_discovery_gate()` — SQL exec counts as vault discovery |
| `agent/evaluator.py` | Modify | Add `task_subtype` InputField; grounding_refs enforcement for `sql_attr` |
| `agent/prompt_builder.py` | Modify | Add `task_subtype` InputField |
| `agent/contract_phase.py` | Modify | `_load_prompt` 3-level fallback; `_load_default_contract` subtype JSON; `negotiate_contract` gains `task_subtype` |
| `agent/orchestrator.py` | Modify | Pass `task_subtype` through entire pipeline |
| `agent/wiki_graph.py` | Modify | `hash_trajectory` dict fallback |
| `main.py` | Modify | `_nm_traj` fix: summary + dict/object fallback + meaningful-step gate |
| `agent/maintenance/subtype_candidates.py` | Create | CLI review tool for proposed subtypes |
| `data/prompts/lookup/sql_count/{executor,planner,evaluator}_contract.md` | Create | 3 contract files |
| `data/prompts/lookup/sql_attr/{executor,planner,evaluator}_contract.md` | Create | 3 contract files |
| `data/prompts/lookup/sql_negative/{executor,planner,evaluator}_contract.md` | Create | 3 contract files |
| `data/prompts/lookup/sql_broad/{executor,planner,evaluator}_contract.md` | Create | 3 contract files |
| `data/default_contracts/lookup_sql_{count,attr,negative,broad}.json` | Create | 4 default contract JSON files |
| `data/wiki/pages/lookup.md` | Modify | Remove 6 empty trajectory patterns |

---

## Task 1: `task_types.json` — add subtype fields

**Files:**
- Modify: `data/task_types.json`

- [ ] **Step 1: Write failing test**

```python
# tests/test_task_types_subtypes.py
from agent.task_types import get_subtype_config, get_prephase_strategy, is_discovery_gate_exempt, REGISTRY

def test_lookup_subtypes_in_registry():
    raw = REGISTRY.types["lookup"]
    # After our change, task_types.py will expose subtypes via get_subtype_config
    cfg = get_subtype_config("lookup", "sql_count")
    assert cfg.get("prephase_strategy") == "none"

def test_lookup_sql_attr_prephase():
    assert get_prephase_strategy("lookup", "sql_attr") == "minimal"

def test_lookup_no_subtype_falls_back_to_type():
    cfg = get_subtype_config("lookup", None)
    assert cfg.get("prephase_strategy") == "standard"

def test_discovery_gate_exempt():
    assert is_discovery_gate_exempt("lookup", "sql_count") is True
    assert is_discovery_gate_exempt("lookup", "sql_attr") is True
    assert is_discovery_gate_exempt("lookup", None) is False

def test_email_no_subtypes():
    cfg = get_subtype_config("email", None)
    assert cfg is not None
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_task_types_subtypes.py -v
```
Expected: `ImportError` or `AttributeError` — functions don't exist yet.

- [ ] **Step 3: Add subtype fields to `data/task_types.json`**

Inside the `"lookup"` entry, add after `"status": "stable"`:

```json
"prephase_strategy": "standard",
"default_subtype": "sql_attr",
"subtypes": {
  "sql_count": {
    "prephase_strategy": "none",
    "discovery_gate_exempt": true,
    "needs_builder": false,
    "description": "Count products by kind — single SQL COUNT(*) query"
  },
  "sql_attr": {
    "prephase_strategy": "minimal",
    "discovery_gate_exempt": true,
    "needs_builder": true,
    "description": "Attribute existence check on specific product — SQL match + cite SKU file"
  },
  "sql_negative": {
    "prephase_strategy": "minimal",
    "discovery_gate_exempt": true,
    "needs_builder": false,
    "description": "Attribute check where attribute likely absent from schema — schema check first"
  },
  "sql_broad": {
    "prephase_strategy": "minimal",
    "discovery_gate_exempt": true,
    "needs_builder": true,
    "description": "Attribute check across broad product category — SQL only, no filesystem"
  }
}
```

For all other types (email, crm, temporal, etc.), add at the end of each type's dict:
```json
"prephase_strategy": "standard",
"default_subtype": null,
"subtypes": {}
```

- [ ] **Step 4: Add functions to `agent/task_types.py`**

Add after the `_load_registry` section, before the `REGISTRY` line at the bottom helpers:

```python
def get_subtype_config(task_type: str, task_subtype: str | None) -> dict:
    """Merged config: type-level defaults overridden by subtype fields."""
    raw_path = _REGISTRY_PATH
    try:
        data = json.loads(raw_path.read_text())
    except Exception:
        return {}
    type_raw = data.get("types", {}).get(task_type, {})
    if not task_subtype:
        return type_raw
    subtype_raw = type_raw.get("subtypes", {}).get(task_subtype, {})
    return {**type_raw, **subtype_raw}


def get_prephase_strategy(task_type: str, task_subtype: str | None) -> str:
    return get_subtype_config(task_type, task_subtype).get("prephase_strategy", "standard")


def is_discovery_gate_exempt(task_type: str, task_subtype: str | None) -> bool:
    return bool(get_subtype_config(task_type, task_subtype).get("discovery_gate_exempt", False))


def get_valid_subtypes(task_type: str) -> frozenset[str]:
    """Return frozenset of registered subtype keys for a task type."""
    t = REGISTRY.types.get(task_type)
    if t is None:
        return frozenset()
    # subtypes live in raw JSON; access via file (REGISTRY doesn't store them yet)
    try:
        data = json.loads(_REGISTRY_PATH.read_text())
        return frozenset(data.get("types", {}).get(task_type, {}).get("subtypes", {}).keys())
    except Exception:
        return frozenset()
```

- [ ] **Step 5: Run tests, confirm PASS**

```bash
uv run pytest tests/test_task_types_subtypes.py -v
```
Expected: all 5 pass.

- [ ] **Step 6: Commit**

```bash
git add data/task_types.json agent/task_types.py tests/test_task_types_subtypes.py
git commit -m "feat: add subtype fields to task_types registry (FIX-450)"
```

---

## Task 2: Contracts — add `task_subtype` to shared types

**Files:**
- Modify: `agent/contracts/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_contracts_subtype.py
from agent.contracts import ClassificationResult, PlannerInput, TaskInput, WikiContext, WikiReadRequest
from agent.prephase import PrephaseResult

def test_classification_result_has_subtype():
    r = ClassificationResult(task_type="lookup", task_subtype="sql_count", model="m", model_cfg={}, confidence=0.9)
    assert r.task_subtype == "sql_count"

def test_classification_result_subtype_none_default():
    r = ClassificationResult(task_type="lookup", model="m", model_cfg={}, confidence=0.9)
    assert r.task_subtype is None

def test_wiki_read_request_has_subtype():
    r = WikiReadRequest(task_type="lookup", task_text="x", task_subtype="sql_attr")
    assert r.task_subtype == "sql_attr"
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_contracts_subtype.py -v
```
Expected: `ValidationError` — field doesn't exist.

- [ ] **Step 3: Update `agent/contracts/__init__.py`**

```python
class ClassificationResult(BaseModel):
    """Result from ClassifierAgent."""
    task_type: str
    task_subtype: str | None = None
    model: str
    model_cfg: dict
    confidence: float


class WikiReadRequest(BaseModel):
    """Request to WikiGraphAgent to load wiki context."""
    task_type: str
    task_text: str
    task_subtype: str | None = None
```

Also find `ExecutionPlan` and `ExecutorInput` in `agent/contracts/__init__.py` — add `task_subtype: str | None = None` to `ExecutorInput` if it exists there, otherwise locate it:

```bash
grep -n "class ExecutorInput\|class PlannerInput\|class ExecutionPlan" agent/contracts/__init__.py
```

Add `task_subtype: str | None = None` to `PlannerInput` and `ExecutorInput`.

- [ ] **Step 4: Run tests, confirm PASS**

```bash
uv run pytest tests/test_contracts_subtype.py -v
```

- [ ] **Step 5: Run existing contract tests, confirm no regression**

```bash
uv run pytest tests/test_contract_models.py tests/agents/test_contracts.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/contracts/__init__.py tests/test_contracts_subtype.py
git commit -m "feat: add task_subtype field to ClassificationResult and related contracts"
```

---

## Task 3: Classifier — add subtype DSPy fields and candidate logging

**Files:**
- Modify: `agent/classifier.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_classifier_subtype.py
import pytest
from unittest.mock import patch, MagicMock

def test_classify_task_llm_returns_subtype_field():
    """classify_task_llm must return (task_type, task_subtype) tuple."""
    from agent.classifier import classify_task_llm
    with patch("agent.classifier._classify_task_llm_once") as mock:
        mock.return_value = ("lookup", "sql_count")
        result = classify_task_llm("How many products?", "model", {})
    assert isinstance(result, tuple)
    assert result[0] == "lookup"
    assert result[1] == "sql_count"

def test_classify_task_llm_unknown_subtype_logged():
    """Unknown subtype triggers candidate log, returns (type, None)."""
    from agent.classifier import classify_task_llm
    with patch("agent.classifier._classify_task_llm_once") as mock_once, \
         patch("agent.classifier._log_subtype_candidate") as mock_log:
        mock_once.return_value = ("lookup", "new:inventory_check")
        result = classify_task_llm("check inventory", "model", {})
    mock_log.assert_called_once()
    assert result == ("lookup", None)
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_classifier_subtype.py -v
```

- [ ] **Step 3: Update `ClassifyTask` DSPy Signature in `agent/classifier.py`**

Replace:
```python
class ClassifyTask(dspy.Signature):
    """Placeholder docstring — overridden at module load from registry."""
    task_text: str = dspy.InputField(desc="Task description to classify")
    vault_hint: str = dspy.InputField(desc="Optional vault context: AGENTS.MD excerpt and folder structure. Empty string if unavailable.")
    task_type: str = dspy.OutputField(desc="overridden at module load")
```

With:
```python
class ClassifyTask(dspy.Signature):
    """Placeholder docstring — overridden at module load from registry."""
    task_text: str = dspy.InputField(desc="Task description to classify")
    vault_hint: str = dspy.InputField(desc="Optional vault context: AGENTS.MD excerpt and folder structure. Empty string if unavailable.")
    task_type: str = dspy.OutputField(desc="overridden at module load")
    task_subtype: str = dspy.OutputField(
        desc="matching subtype key from registry, or 'new:<proposed_name>' if no match, or '' if type has no subtypes"
    )
    task_subtype_reason: str = dspy.OutputField(desc="one-sentence justification for subtype choice")
    task_subtype_strategy_hint: str = dspy.OutputField(
        desc="only when new: prefix — one of none|minimal|standard; empty string otherwise"
    )
```

- [ ] **Step 4: Add `_SUBTYPE_CANDIDATES_PATH` and `_log_subtype_candidate` in `agent/classifier.py`**

Add after `_CANDIDATES_PATH = ...`:
```python
_SUBTYPE_CANDIDATES_PATH = Path(__file__).parent.parent / "data" / "subtype_candidates.jsonl"
```

Add after `_log_soft_candidate`:
```python
def _log_subtype_candidate(
    task_type: str,
    proposed_subtype: str,
    reason: str,
    strategy_hint: str,
    task_text: str,
) -> None:
    """Log a proposed subtype for offline review."""
    import datetime as _dt2
    try:
        record = {
            "task_type": task_type,
            "proposed_subtype": proposed_subtype,
            "reason": reason[:200],
            "suggested_strategy": strategy_hint or "standard",
            "task_text": task_text[:300],
            "timestamp": _dt2.datetime.now(_dt2.timezone.utc).isoformat(timespec="seconds"),
        }
        with _SUBTYPE_CANDIDATES_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[MODEL_ROUTER] Could not log subtype candidate ({exc})")
```

- [ ] **Step 5: Update `_classify_task_llm_once` to extract subtype**

The function currently returns `str`. Change signature and extraction:

Find the return in `_classify_task_llm_once` where it returns `detected` (the task_type string). Change the return type to `tuple[str, str | None]`.

Where DSPy path succeeds:
```python
# After: if detected in VALID_TYPES:
if detected in VALID_TYPES:
    raw_subtype = (getattr(pred, "task_subtype", "") or "").strip()
    raw_reason = (getattr(pred, "task_subtype_reason", "") or "").strip()
    raw_hint = (getattr(pred, "task_subtype_strategy_hint", "") or "").strip()
    from .task_types import get_valid_subtypes
    valid_subs = get_valid_subtypes(detected)
    if raw_subtype and raw_subtype.startswith("new:"):
        _log_subtype_candidate(detected, raw_subtype, raw_reason, raw_hint, task_text)
        print(f"[MODEL_ROUTER] DSPy classifier: '{detected}' subtype=new:{raw_subtype!r} (logged)")
        return detected, None
    subtype = raw_subtype if raw_subtype in valid_subs else None
    print(f"[MODEL_ROUTER] DSPy classifier: '{detected}' subtype={subtype!r}")
    return detected, subtype
```

At all other `return ""` / `return detected` sites, return `(value, None)` tuples.

- [ ] **Step 6: Update `classify_task_llm` to handle tuple returns**

```python
def classify_task_llm(task_text: str, model: str, model_config: dict,
                      vault_hint: str | None = None) -> tuple[str, str | None]:
    # ... existing regex pre-check (return (type, None) for regex hits) ...
    # ... votes logic: collect (type, subtype) pairs ...
    # final return: (type, subtype)
```

Specifically at the regex fast path:
```python
_regex_pre = classify_regex(task_text)
if _regex_pre is not None and _regex_pre[1] == "high":
    print(f"[MODEL_ROUTER] Regex-confident type={_regex_pre[0]!r}, skipping LLM")
    return _regex_pre[0], None
```

At the single-vote path:
```python
result = _classify_task_llm_once(task_text, model, model_config, vault_hint)
task_type, task_subtype = result if isinstance(result, tuple) else (result, None)
return (task_type if task_type in VALID_TYPES else classify_task(task_text)), task_subtype
```

For multi-vote CC path, tally only `task_type` for majority vote, return subtype from the winning vote.

- [ ] **Step 7: Update `ModelRouter.resolve_after_prephase` to return subtype**

Change return type to `tuple[str, dict, str, str | None]`:
```python
task_type_result = classify_task_llm(...)
if isinstance(task_type_result, tuple):
    task_type, task_subtype = task_type_result
else:
    task_type, task_subtype = task_type_result, None
# ... existing model selection ...
return model_id, adapted_cfg, task_type, task_subtype
```

- [ ] **Step 8: Run tests, confirm PASS**

```bash
uv run pytest tests/test_classifier_subtype.py tests/test_classifier.py -v
```

- [ ] **Step 9: Commit**

```bash
git add agent/classifier.py tests/test_classifier_subtype.py
git commit -m "feat: add task_subtype to DSPy classifier signature and candidate logging (FIX-451)"
```

---

## Task 4: ClassifierAgent — propagate subtype to ClassificationResult

**Files:**
- Modify: `agent/agents/classifier_agent.py`

- [ ] **Step 1: Write failing test**

```python
# tests/agents/test_classifier_agent_subtype.py
from unittest.mock import MagicMock, patch
from agent.agents.classifier_agent import ClassifierAgent
from agent.contracts import TaskInput

def test_classifier_agent_returns_subtype():
    router = MagicMock()
    router.resolve_after_prephase.return_value = ("model-x", {}, "lookup", "sql_count")
    agent = ClassifierAgent(router=router)
    prephase = MagicMock()
    task = TaskInput(task_text="How many products?", harness_url="h", trial_id="t1")
    result = agent.run(task, prephase=prephase)
    assert result.task_type == "lookup"
    assert result.task_subtype == "sql_count"
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/agents/test_classifier_agent_subtype.py -v
```

- [ ] **Step 3: Update `agent/agents/classifier_agent.py`**

```python
def run(self, task: TaskInput, prephase: PrephaseResult | None = None) -> ClassificationResult:
    if prephase is not None:
        result = self._router.resolve_after_prephase(task.task_text, prephase)
        if len(result) == 4:
            model, cfg, task_type, task_subtype = result
        else:
            model, cfg, task_type = result
            task_subtype = None
        confidence = 0.95
    else:
        task_type = classify_task(task.task_text)
        task_subtype = None
        model = self._router.default
        cfg = self._router.configs.get(model, {})
        confidence = 0.8

    return ClassificationResult(
        task_type=task_type,
        task_subtype=task_subtype,
        model=model,
        model_cfg=cfg,
        confidence=confidence,
    )
```

- [ ] **Step 4: Run tests, confirm PASS**

```bash
uv run pytest tests/agents/test_classifier_agent_subtype.py tests/agents/ -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/agents/classifier_agent.py tests/agents/test_classifier_agent_subtype.py
git commit -m "feat: ClassifierAgent propagates task_subtype in ClassificationResult"
```

---

## Task 5: Prephase — strategy dispatch

**Files:**
- Modify: `agent/prephase.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_prephase_strategy.py
from unittest.mock import MagicMock, call, patch
from agent.prephase import run_prephase

def _make_vm():
    vm = MagicMock()
    vm.tree.return_value = MagicMock(root=MagicMock(name="/", children=[]))
    vm.read.return_value = MagicMock(content="# AGENTS.MD content\n/bin/ folder")
    vm.context.return_value = MagicMock(content="")
    return vm

def test_strategy_none_makes_3_calls():
    vm = _make_vm()
    result = run_prephase(vm, "How many products?", "", task_type="lookup", task_subtype="sql_count")
    # none strategy: tree + read AGENTS.MD + context = 3 ops
    assert vm.tree.call_count == 1
    assert vm.read.call_count == 1  # only AGENTS.MD
    assert vm.context.call_count == 1

def test_strategy_minimal_reads_sql():
    vm = _make_vm()
    # Make /bin/sql readable
    def side_effect(req):
        if hasattr(req, 'path') and req.path == "/bin/sql":
            return MagicMock(content="SQL interface docs")
        if hasattr(req, 'path') and "AGENTS" in req.path:
            return MagicMock(content="# AGENTS.MD\n/bin/ folder")
        return MagicMock(content="")
    vm.read.side_effect = side_effect
    result = run_prephase(vm, "Do you have X?", "", task_type="lookup", task_subtype="sql_attr")
    paths_read = [c.args[0].path for c in vm.read.call_args_list]
    assert any("/bin/sql" in p for p in paths_read)

def test_strategy_standard_no_task_subtype():
    vm = _make_vm()
    # standard: existing behaviour — no crash
    result = run_prephase(vm, "find something", "", task_type="lookup", task_subtype=None)
    assert result is not None
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_prephase_strategy.py -v
```

- [ ] **Step 3: Refactor `agent/prephase.py`**

Add at top of file (after imports):
```python
import os as _os
_PREPHASE_MAX_READS = int(_os.environ.get("PREPHASE_MAX_READS", "200"))
```

Extract the existing body of `run_prephase` into `_strategy_standard`. Then add:

```python
def _strategy_none(vm, task_text: str, system_prompt_text: str) -> PrephaseResult:
    """sql_count: tree + AGENTS.MD + context only. ~3K tokens."""
    log: list = [
        {"role": "system", "content": system_prompt_text},
        {"role": "user", "content": _FEW_SHOT_USER},
        {"role": "assistant", "content": _FEW_SHOT_ASSISTANT},
    ]
    print(f"\n{CLI_BLUE}[prephase] strategy=none{CLI_CLR}")
    tree_txt = ""
    try:
        tree_result = vm.tree(TreeRequest(root="/", level=2))
        tree_txt = _render_tree_result(tree_result, root_path="/", level=2)
        print(f"{CLI_BLUE}[prephase] tree ok{CLI_CLR}")
    except Exception as e:
        tree_txt = f"(tree failed: {e})"

    agents_md_content = ""
    agents_md_path = ""
    for candidate in ["/AGENTS.MD", "/AGENTS.md"]:
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                break
        except Exception:
            pass

    try:
        ctx_result = vm.context(ContextRequest())
        ctx_content = (ctx_result.content or "").strip()
        if ctx_content:
            log.append({"role": "user", "content": f"TASK CONTEXT:\n{ctx_content}"})
    except Exception:
        pass

    prephase_parts = [
        f"TASK: {task_text}",
        f"VAULT STRUCTURE:\n{tree_txt}",
    ]
    if agents_md_content:
        prephase_parts.append(f"\n{agents_md_path} CONTENT:\n{agents_md_content}")
    log.append({"role": "user", "content": "\n".join(prephase_parts)})
    preserve_prefix = list(log)
    print(f"{CLI_BLUE}[prephase] done (strategy=none){CLI_CLR}")
    return PrephaseResult(
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        vault_tree_text=tree_txt,
    )


def _strategy_minimal(vm, task_text: str, system_prompt_text: str) -> PrephaseResult:
    """sql_attr/sql_negative/sql_broad: tree + AGENTS.MD + /bin/sql + context. ~5K tokens."""
    result = _strategy_none(vm, task_text, system_prompt_text)
    # Append /bin/sql spec
    try:
        sql_r = vm.read(ReadRequest(path="/bin/sql"))
        if sql_r.content:
            for i in range(len(result.log) - 1, -1, -1):
                if result.log[i].get("role") == "user" and "TASK:" in result.log[i].get("content", ""):
                    result.log[i]["content"] += f"\n\n--- /bin/sql ---\n{sql_r.content}"
                    if i < len(result.preserve_prefix):
                        result.preserve_prefix[i]["content"] = result.log[i]["content"]
                    break
            print(f"{CLI_BLUE}[prephase] /bin/sql loaded (strategy=minimal){CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/sql read failed: {e}{CLI_CLR}")
    return result
```

Update `_strategy_standard` (the original function body) to add a read cap:
```python
# Inside _strategy_standard, in _read_dir, add a module-level counter:
# After each successful read, check _reads_done >= _PREPHASE_MAX_READS and return
```

Add the dispatch function and update `run_prephase` signature:

```python
_STRATEGY_DISPATCH = {
    "none":     _strategy_none,
    "minimal":  _strategy_minimal,
    "standard": _strategy_standard,
    "full":     _strategy_standard,  # deprecated alias
}


def run_prephase(
    vm,
    task_text: str,
    system_prompt_text: str,
    task_type: str = "default",
    task_subtype: str | None = None,
) -> PrephaseResult:
    from .task_types import get_prephase_strategy
    strategy = get_prephase_strategy(task_type, task_subtype)
    if strategy == "full":
        print(f"{CLI_YELLOW}[prephase] strategy=full is deprecated, using standard{CLI_CLR}")
    print(f"{CLI_BLUE}[prephase] strategy={strategy} (type={task_type}, subtype={task_subtype}){CLI_CLR}")
    fn = _STRATEGY_DISPATCH.get(strategy, _strategy_standard)
    return fn(vm, task_text, system_prompt_text)
```

- [ ] **Step 4: Run tests, confirm PASS**

```bash
uv run pytest tests/test_prephase_strategy.py -v
```

- [ ] **Step 5: Run existing prephase tests**

```bash
uv run pytest tests/ -k "prephase" -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/prephase.py tests/test_prephase_strategy.py
git commit -m "feat: prephase strategy dispatch — none/minimal/standard per subtype (FIX-452)"
```

---

## Task 6: Orchestrator — thread `task_subtype` through pipeline

**Files:**
- Modify: `agent/orchestrator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/agents/test_orchestrator_subtype.py
from unittest.mock import MagicMock, patch

def test_orchestrator_passes_subtype_to_prephase():
    """After classification, run_prephase receives task_subtype."""
    with patch("agent.orchestrator.run_prephase") as mock_prephase, \
         patch("agent.orchestrator.ClassifierAgent") as mock_cls_cls, \
         patch("agent.orchestrator.WikiGraphAgent"), \
         patch("agent.orchestrator.PlannerAgent"), \
         patch("agent.orchestrator.ExecutorAgent"):
        mock_prephase.return_value = MagicMock(
            log=[{"role": "system", "content": ""}],
            preserve_prefix=[{"role": "system", "content": ""}],
            agents_md_content="", vault_tree_text="", vault_date_est="",
        )
        mock_cls = MagicMock()
        mock_cls.run.return_value = MagicMock(
            task_type="lookup", task_subtype="sql_count", model="m", model_cfg={}, confidence=0.9
        )
        mock_cls_cls.return_value = mock_cls

        from agent.orchestrator import run_agent
        router = MagicMock()
        router.evaluator = "m"
        router.configs = {}
        router._adapt_config = lambda cfg, t: cfg
        try:
            run_agent(router, "http://x", "How many products?")
        except Exception:
            pass  # executor may fail in test — we only check prephase call
        call_kwargs = mock_prephase.call_args
        assert call_kwargs is not None
        # task_subtype must be passed
        assert "task_subtype" in call_kwargs.kwargs or (
            len(call_kwargs.args) >= 5 and call_kwargs.args[4] == "sql_count"
        )
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/agents/test_orchestrator_subtype.py -v
```

- [ ] **Step 3: Update `agent/orchestrator.py`**

In `run_agent`, change the prephase call:
```python
# Before:
pre = run_prephase(vm, task_text, "")

# After:
# Initial prephase with empty system prompt (classification happens after prephase in current flow)
# But we need subtype for strategy — do a two-pass: standard prephase first for classification,
# then if subtype != None and strategy != standard, re-run prephase with subtype.
pre = run_prephase(vm, task_text, "", task_type="default", task_subtype=None)
```

After classification:
```python
task_type = classification.task_type
task_subtype = classification.task_subtype

# Re-run prephase with correct subtype if strategy differs from standard
from agent.task_types import get_prephase_strategy
strategy = get_prephase_strategy(task_type, task_subtype)
if strategy != "standard":
    print(f"[orchestrator] re-running prephase with strategy={strategy} (subtype={task_subtype})")
    pre = run_prephase(vm, task_text, "", task_type=task_type, task_subtype=task_subtype)
```

Pass `task_subtype` to `PlannerInput`:
```python
plan = planner.run(PlannerInput(
    task_input=task_input,
    classification=classification,
    wiki_context=wiki_context,
    prephase=pre,
    task_subtype=task_subtype,
))
```

Pass `task_subtype` to `ExecutorInput`:
```python
result = executor.run(ExecutorInput(
    ...
    task_type=task_type,
    task_subtype=task_subtype,
    ...
))
```

Also update `stats` dict:
```python
stats["task_subtype"] = task_subtype
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/agents/test_orchestrator_subtype.py tests/agents/test_orchestrator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/orchestrator.py tests/agents/test_orchestrator_subtype.py
git commit -m "feat: thread task_subtype through orchestrator pipeline"
```

---

## Task 7: Security — FIX-345 SQL bypass and error_counts key fix

**Files:**
- Modify: `agent/security.py`
- Modify: `agent/loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_discovery_gate_sql.py
from unittest.mock import MagicMock

def test_sql_exec_counts_as_vault_discovery():
    from agent.security import check_discovery_gate
    # A tool history with sql exec but no list/read
    tool_history = [MagicMock(tool="exec", path="/bin/sql")]
    assert check_discovery_gate("lookup", "sql_count", tool_history) is True

def test_no_discovery_no_sql_blocks():
    from agent.security import check_discovery_gate
    assert check_discovery_gate("lookup", None, []) is False

def test_exempt_subtype_always_passes():
    from agent.security import check_discovery_gate
    assert check_discovery_gate("lookup", "sql_attr", []) is True

def test_email_not_affected():
    from agent.security import check_discovery_gate
    # email is not in the discovery-gate types
    assert check_discovery_gate("email", None, []) is True
```

```python
# tests/test_error_counts_key.py
from collections import Counter

def test_error_counts_str_key_not_tuple():
    """error_counts key must be str for JSON serialisation in StallRequest."""
    from agent import loop as _loop
    # Check the key format used in loop.py
    import inspect
    src = inspect.getsource(_loop)
    assert '(action_name, _err_path, "EXCEPTION")' not in src, \
        "Tuple key found in error_counts — must use f-string key"
```

- [ ] **Step 2: Run tests, confirm FAIL**

```bash
uv run pytest tests/test_discovery_gate_sql.py tests/test_error_counts_key.py -v
```

- [ ] **Step 3: Add `check_discovery_gate` to `agent/security.py`**

Add after the existing gate functions:
```python
from .task_types import is_discovery_gate_exempt

_DISCOVERY_GATE_TYPES = frozenset({"temporal", "queue", "inbox", "lookup"})


def check_discovery_gate(task_type: str, task_subtype: str | None, tool_history: list) -> bool:
    """Return True if report_completion is allowed; False if blocked.

    FIX-345 extended: SQL exec on /bin/sql counts as vault discovery.
    Subtypes with discovery_gate_exempt=true bypass entirely.
    Types not in _DISCOVERY_GATE_TYPES are always allowed.
    """
    if task_type not in _DISCOVERY_GATE_TYPES:
        return True
    if is_discovery_gate_exempt(task_type, task_subtype):
        return True
    # SQL exec counts as vault discovery
    sql_calls = [t for t in tool_history if getattr(t, "tool", "") == "exec" and getattr(t, "path", "") == "/bin/sql"]
    if sql_calls:
        return True
    # Original FIX-345: any list/read/find/search/tree counts
    has_discovery = any(
        getattr(t, "tool", "") in ("list", "read", "find", "search", "tree")
        for t in tool_history
    )
    return has_discovery
```

- [ ] **Step 4: Update FIX-345 check in `agent/loop.py`**

Find the FIX-345 block (line ~1702):
```python
if (isinstance(job.function, ReportTaskCompletion)
        and task_type in (TASK_TEMPORAL, TASK_QUEUE, TASK_INBOX, TASK_LOOKUP)
        and not st.listed_dirs
        and not st.read_paths):
```

Replace with:
```python
if isinstance(job.function, ReportTaskCompletion):
    from .security import check_discovery_gate
    _tool_history = [
        type("_T", (), {"tool": f.kind, "path": f.path})()
        for f in st.step_facts
    ]
    if not check_discovery_gate(task_type, task_subtype, _tool_history):
```

This requires `task_subtype` to be passed into the loop. Find the `run_loop` signature and add `task_subtype: str | None = None` parameter. Pass it through from `ExecutorAgent`.

- [ ] **Step 5: Fix `error_counts` tuple key in `agent/loop.py`** (line ~2607)

```python
# Before:
st.error_counts[(action_name, _err_path, "EXCEPTION")] += 1

# After:
st.error_counts[f"{action_name}:{_err_path}:EXCEPTION"] += 1
```

- [ ] **Step 6: Run tests, confirm PASS**

```bash
uv run pytest tests/test_discovery_gate_sql.py tests/test_error_counts_key.py tests/test_security_gates.py -v
```

- [ ] **Step 7: Commit**

```bash
git add agent/security.py agent/loop.py tests/test_discovery_gate_sql.py tests/test_error_counts_key.py
git commit -m "feat: SQL exec counts as vault discovery in FIX-345 gate; fix error_counts tuple key (FIX-453)"
```

---

## Task 8: Prompt — two-level `_TASK_BLOCKS` and `get_task_block`

**Files:**
- Modify: `agent/prompt.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_prompt_subtype_blocks.py
from agent.prompt import get_task_block

def test_sql_count_block_exists():
    block = get_task_block("lookup", "sql_count")
    assert "COUNT" in block
    assert "/bin/sql" in block

def test_sql_attr_block_exists():
    block = get_task_block("lookup", "sql_attr")
    assert "grounding_refs" in block.lower() or "SKU" in block

def test_sql_negative_block_exists():
    block = get_task_block("lookup", "sql_negative")
    assert ".schema" in block or "schema" in block.lower()

def test_sql_broad_block_never_reads_files():
    block = get_task_block("lookup", "sql_broad")
    assert "NEVER" in block

def test_unknown_subtype_falls_back_to_type_default():
    block = get_task_block("lookup", "nonexistent_subtype")
    assert block  # must return something

def test_no_subtype_returns_type_default():
    block = get_task_block("lookup", None)
    assert block
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_prompt_subtype_blocks.py -v
```

- [ ] **Step 3: Refactor `_TASK_BLOCKS` in `agent/prompt.py`**

Find the existing `_TASK_BLOCKS` dict. Change it from:
```python
_TASK_BLOCKS: dict[str, str] = { "lookup": "...", "email": "...", ... }
```

To a two-level structure:
```python
_TASK_BLOCKS: dict[str, dict[str, str]] = {
    "lookup": {
        "_default": "<existing lookup block content>",
        "sql_count": """TASK: catalogue count query

1. GET kind_id: SELECT id FROM product_kinds WHERE name LIKE '%X%'
2. COUNT: SELECT COUNT(*) FROM products WHERE kind_id = ?
3. Report the number as '<COUNT:n>' exactly as required by task.
Grounding refs: ["/bin/sql"]
No file reads needed.""",
        "sql_attr": """TASK: catalogue attribute check (specific product)

1. SQL: SELECT sku, properties FROM products
        WHERE brand=? AND model=? AND properties LIKE '%attr%value%'
2. Answer with <YES> or <NO> token.
3. REQUIRED — grounding_refs must include exact product file:
   "/proc/catalog/<category>/<kind>/<family>/<SKU>.json"
   A directory path alone is insufficient and will fail grading.""",
        "sql_negative": """TASK: catalogue attribute check (attribute may not exist in schema)

1. FIRST: /bin/sql '.schema' — check if attribute column exists.
2. Non-standard attributes (Bluetooth, app-scheduling, IoT, smart-home)
   are NOT in the catalogue schema — answer <NO> immediately citing schema.
3. If attribute IS in schema: run targeted SQL query.
4. SQL timeout: retry once, then use search as fallback.
Grounding refs: schema result or specific product file.""",
        "sql_broad": """TASK: catalogue attribute check (broad product category)

NEVER read individual catalogue files — catalogue has thousands of files
and reading them causes context window overflow.

1. SQL only: SELECT sku, properties FROM products
             WHERE kind_id=? AND brand=? AND model=? AND properties LIKE ?
2. Filter results in-memory if needed.
3. Answer <YES>/<NO> with SQL result as grounding.""",
    },
    "email": {"_default": "<existing email block>"},
    # ... other types keep single _default entry
}
```

Add `get_task_block`:
```python
def get_task_block(task_type: str, task_subtype: str | None) -> str:
    type_blocks = _TASK_BLOCKS.get(task_type, {})
    if isinstance(type_blocks, str):
        return type_blocks
    if task_subtype and task_subtype in type_blocks:
        return type_blocks[task_subtype]
    default = type_blocks.get("_default", "")
    if default:
        return default
    return _TASK_BLOCKS.get("default", {}).get("_default", "")
```

Update `build_system_prompt` to use `get_task_block(task_type, task_subtype)` — add `task_subtype` parameter:
```python
def build_system_prompt(task_type: str, task_subtype: str | None = None) -> str:
    ...
    block = get_task_block(task_type, task_subtype)
    ...
```

- [ ] **Step 4: Run tests, confirm PASS**

```bash
uv run pytest tests/test_prompt_subtype_blocks.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/prompt.py tests/test_prompt_subtype_blocks.py
git commit -m "feat: two-level _TASK_BLOCKS with subtype-specific prompt blocks (FIX-454)"
```

---

## Task 9: Evaluator and PromptBuilder — add `task_subtype` InputField

**Files:**
- Modify: `agent/evaluator.py`
- Modify: `agent/prompt_builder.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_evaluator_subtype.py
import re
from unittest.mock import MagicMock, patch

def test_evaluator_blocks_sql_attr_yes_without_sku_ref():
    """sql_attr YES answer without /proc/catalog/...json in grounding_refs gets objection."""
    from agent.evaluator import evaluate_completion
    with patch("agent.evaluator._run_dspy_evaluation") as mock_eval:
        mock_eval.return_value = ("yes", "", "")
        result = evaluate_completion(
            task_text="Do you have ProductX with 2000W?",
            task_type="lookup",
            task_subtype="sql_attr",
            proposed_outcome="OUTCOME_OK",
            agent_message="<YES> ProductX has 2000W",
            done_ops=[],
            completed_steps=[],
            grounding_refs=["/proc/catalog/"],  # directory only, no SKU file
            model="m",
            cfg={},
        )
    assert result.approved is False or any("SKU" in (i or "") for i in (result.issues or []))

def test_evaluator_allows_sql_attr_with_sku_ref():
    from agent.evaluator import evaluate_completion
    with patch("agent.evaluator._run_dspy_evaluation") as mock_eval:
        mock_eval.return_value = ("yes", "", "")
        result = evaluate_completion(
            task_text="Do you have ProductX with 2000W?",
            task_type="lookup",
            task_subtype="sql_attr",
            proposed_outcome="OUTCOME_OK",
            agent_message="<YES>",
            done_ops=[],
            completed_steps=[],
            grounding_refs=["/proc/catalog/heaters/boiler/premium/SKU123.json"],
            model="m",
            cfg={},
        )
    # With valid SKU ref, no objection added
    assert result is not None
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_evaluator_subtype.py -v
```

- [ ] **Step 3: Update `EvaluateCompletion` Signature in `agent/evaluator.py`**

Add `task_subtype` after `task_type`:
```python
task_type: str = dspy.InputField()
task_subtype: str = dspy.InputField(desc="subtype key or empty string")
```

- [ ] **Step 4: Update `evaluate_completion` function signature**

Add `task_subtype: str | None = None` parameter. Pass `task_subtype or ""` to the DSPy call.

- [ ] **Step 5: Add grounding_refs enforcement in `evaluate_completion`**

After the DSPy evaluation returns `approved=True`, add pre-approval check:

```python
import re as _re

_SKU_REF_RE = _re.compile(r"/proc/catalog/.+\.json$")

# After DSPy returns approved:
if approved and task_subtype == "sql_attr" and "<YES>" in (agent_message or ""):
    has_sku_ref = any(_SKU_REF_RE.match(ref) for ref in (grounding_refs or []))
    if not has_sku_ref:
        approved = False
        issues = list(issues or []) + ["grounding_refs must include specific /proc/catalog/SKU.json path"]
```

- [ ] **Step 6: Update `PromptAddendum` Signature in `agent/prompt_builder.py`**

Add after `task_type`:
```python
task_subtype: str = dspy.InputField(desc="task subtype key or empty string if none")
```

Update `build_dynamic_addendum` signature to accept `task_subtype: str | None = None` and pass `task_subtype or ""` to the DSPy call.

- [ ] **Step 7: Run tests, confirm PASS**

```bash
uv run pytest tests/test_evaluator_subtype.py tests/test_evaluator.py -v
```

- [ ] **Step 8: Commit**

```bash
git add agent/evaluator.py agent/prompt_builder.py tests/test_evaluator_subtype.py
git commit -m "feat: add task_subtype to EvaluateCompletion and PromptAddendum signatures (FIX-455)"
```

---

## Task 10: SQL retry and dispatch fix

**Files:**
- Modify: `agent/dispatch.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_dispatch_sql_retry.py
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call

def test_exec_retries_on_timeout():
    from agent.dispatch import dispatch_tool
    vm = MagicMock()
    call_count = 0
    def side_effect(req):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TimeoutError("SQL timeout")
        return MagicMock(content="42")
    vm.exec.side_effect = side_effect

    from agent.models import Req_Exec
    cmd = Req_Exec(path="/bin/sql", args=["SELECT COUNT(*)"], stdin="")
    # Patch env for 1 retry
    with patch.dict("os.environ", {"SQL_MAX_RETRIES": "1", "SQL_RETRY_DELAY_S": "0"}):
        result = dispatch_tool(vm, cmd)
    assert vm.exec.call_count == 2
    assert result.content == "42"
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_dispatch_sql_retry.py -v
```

- [ ] **Step 3: Add retry logic in `agent/dispatch.py`**

Find the `Req_Exec` dispatch (line ~674):
```python
if isinstance(cmd, Req_Exec):
    return vm.exec(ExecRequest(path=cmd.path, args=list(cmd.args), stdin=cmd.stdin))
```

Replace with:
```python
if isinstance(cmd, Req_Exec):
    _sql_max_retries = int(os.getenv("SQL_MAX_RETRIES", "1"))
    _sql_retry_delay = float(os.getenv("SQL_RETRY_DELAY_S", "2.0"))
    for _attempt in range(_sql_max_retries + 1):
        try:
            return vm.exec(ExecRequest(path=cmd.path, args=list(cmd.args), stdin=cmd.stdin))
        except (TimeoutError, Exception) as _exc:
            if "timeout" in str(_exc).lower() and _attempt < _sql_max_retries:
                print(f"[dispatch] SQL timeout attempt {_attempt + 1}, retrying in {_sql_retry_delay}s")
                time.sleep(_sql_retry_delay)
                continue
            raise
```

- [ ] **Step 4: Run tests, confirm PASS**

```bash
uv run pytest tests/test_dispatch_sql_retry.py tests/test_dispatch_transient.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/dispatch.py tests/test_dispatch_sql_retry.py
git commit -m "feat: SQL exec retry on timeout in dispatch_tool (FIX-456)"
```

---

## Task 11: Contract phase — subtype fallback chain

**Files:**
- Modify: `agent/contract_phase.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_contract_phase_subtype.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

def test_load_prompt_falls_back_through_subtype_type_default(tmp_path):
    """_load_prompt tries subtype/ → type/ → default/ in order."""
    from agent import contract_phase as cp
    # Create type-level file only
    (tmp_path / "lookup").mkdir()
    (tmp_path / "lookup" / "executor_contract.md").write_text("type-level executor")
    (tmp_path / "default").mkdir()
    (tmp_path / "default" / "executor_contract.md").write_text("default executor")

    with patch.object(cp, "_DATA", tmp_path):
        result = cp._load_prompt("executor", "lookup", "sql_count")
    assert result == "type-level executor"

def test_load_prompt_uses_subtype_when_exists(tmp_path):
    (tmp_path / "lookup").mkdir()
    (tmp_path / "lookup" / "sql_count").mkdir()
    (tmp_path / "lookup" / "sql_count" / "executor_contract.md").write_text("subtype executor")
    (tmp_path / "default").mkdir()
    (tmp_path / "default" / "executor_contract.md").write_text("default")

    with patch.object(cp, "_DATA", tmp_path):
        from agent import contract_phase as cp
        result = cp._load_prompt("executor", "lookup", "sql_count")
    assert result == "subtype executor"

def test_load_default_contract_tries_subtype_json(tmp_path):
    from agent import contract_phase as cp
    (tmp_path / "default_contracts").mkdir()
    (tmp_path / "default_contracts" / "lookup_sql_count.json").write_text(
        '{"plan_steps":["SQL"],"success_criteria":["ok"],"required_evidence":[],"failure_conditions":[]}'
    )
    with patch.object(cp, "_DATA", tmp_path):
        contract = cp._load_default_contract("lookup", "sql_count")
    assert "SQL" in contract.plan_steps
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_contract_phase_subtype.py -v
```

- [ ] **Step 3: Update `_load_prompt` in `agent/contract_phase.py`**

```python
def _load_prompt(role: str, task_type: str, task_subtype: str | None = None) -> str:
    """Load domain-specific prompt with 3-level fallback: subtype → type → default."""
    candidates = []
    if task_subtype:
        candidates.append(_DATA / "prompts" / task_type / task_subtype / f"{role}_contract.md")
    candidates.append(_DATA / "prompts" / task_type / f"{role}_contract.md")
    candidates.append(_DATA / "prompts" / "default" / f"{role}_contract.md")
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return ""
```

- [ ] **Step 4: Update `_load_default_contract` in `agent/contract_phase.py`**

```python
def _load_default_contract(task_type: str, task_subtype: str | None = None) -> Contract:
    """Load fallback contract: subtype-specific → per-type → universal default."""
    names = []
    if task_subtype:
        names.append(f"{task_type}_{task_subtype}.json")
    names.extend([f"{task_type}.json", "default.json"])
    for name in names:
        p = _DATA / "default_contracts" / name
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                data["is_default"] = True
                data.setdefault("rounds_taken", 0)
                data.setdefault("evidence_standard", "vault_required")
                return Contract(**data)
            except Exception:
                pass
    return Contract(
        plan_steps=["discover vault", "execute task", "report"],
        success_criteria=["task completed"],
        required_evidence=[],
        failure_conditions=["no action taken"],
        is_default=True,
        rounds_taken=0,
    )
```

- [ ] **Step 5: Update `negotiate_contract` signature**

Add `task_subtype: str | None = None` parameter. Update the two calls to `_load_prompt` and `_load_default_contract`:

```python
executor_system = _load_prompt("executor", task_type, task_subtype)
evaluator_system = _load_prompt("evaluator", task_type, task_subtype)
# ...
return _load_default_contract(task_type, task_subtype), 0, 0, []
```

- [ ] **Step 6: Run tests, confirm PASS**

```bash
uv run pytest tests/test_contract_phase_subtype.py tests/test_contract_phase.py -v
```

- [ ] **Step 7: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase_subtype.py
git commit -m "feat: contract_phase 3-level fallback for subtype-specific prompts (FIX-457)"
```

---

## Task 12: Create contract files for 4 lookup subtypes

**Files:**
- Create: `data/prompts/lookup/sql_count/{executor,planner,evaluator}_contract.md`
- Create: `data/prompts/lookup/sql_attr/{executor,planner,evaluator}_contract.md`
- Create: `data/prompts/lookup/sql_negative/{executor,planner,evaluator}_contract.md`
- Create: `data/prompts/lookup/sql_broad/{executor,planner,evaluator}_contract.md`
- Create: `data/default_contracts/lookup_sql_{count,attr,negative,broad}.json`

- [ ] **Step 1: Write test to verify files exist**

```python
# tests/test_subtype_contract_files.py
from pathlib import Path
import json, pytest

_DATA = Path("data")

@pytest.mark.parametrize("subtype", ["sql_count", "sql_attr", "sql_negative", "sql_broad"])
@pytest.mark.parametrize("role", ["executor", "planner", "evaluator"])
def test_subtype_contract_file_exists(subtype, role):
    p = _DATA / "prompts" / "lookup" / subtype / f"{role}_contract.md"
    assert p.exists(), f"Missing: {p}"
    assert len(p.read_text()) > 50

@pytest.mark.parametrize("subtype", ["sql_count", "sql_attr", "sql_negative", "sql_broad"])
def test_default_contract_json_valid(subtype):
    p = _DATA / "default_contracts" / f"lookup_{subtype}.json"
    assert p.exists(), f"Missing: {p}"
    data = json.loads(p.read_text())
    assert "plan_steps" in data
    assert "success_criteria" in data
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_subtype_contract_files.py -v
```

- [ ] **Step 3: Create `data/prompts/lookup/sql_count/` files**

```bash
mkdir -p data/prompts/lookup/sql_count data/prompts/lookup/sql_attr data/prompts/lookup/sql_negative data/prompts/lookup/sql_broad
```

`data/prompts/lookup/sql_count/executor_contract.md`:
```
You are an ExecutorAgent for LOOKUP / sql_count.
Strategy: single SQL COUNT(*).

1. GET kind_id: SELECT id FROM product_kinds WHERE name LIKE '%X%'
2. COUNT: SELECT COUNT(*) FROM products WHERE kind_id = ?
3. report_completion with '<COUNT:n>' exactly.

Grounding refs: ["/bin/sql"]. No file reads.
```

`data/prompts/lookup/sql_count/planner_contract.md`:
```
Strategy: sql_count. No vault discovery needed.
SQL path: /bin/sql. Two queries: kind_id lookup → COUNT(*).
No filesystem exploration required.
```

`data/prompts/lookup/sql_count/evaluator_contract.md`:
```
Success: answer matches '<COUNT:n>' format, grounding_refs includes "/bin/sql".
Fail: filesystem reads performed, COUNT syntax wrong, report before SQL executed.
required_evidence: ["/bin/sql"]
```

`data/prompts/lookup/sql_attr/executor_contract.md`:
```
You are an ExecutorAgent for LOOKUP / sql_attr.
Strategy: SQL exact match + cite specific SKU file.

1. SQL: SELECT sku, properties FROM products
        WHERE brand=? AND model=? AND properties LIKE '%attr%value%'
2. Answer <YES> or <NO>.
3. REQUIRED: grounding_refs must include exact "/proc/catalog/<cat>/<kind>/<fam>/<SKU>.json"
   A directory path alone fails grading.

Grounding refs: ["/bin/sql", "/proc/catalog/.../<SKU>.json"]
```

`data/prompts/lookup/sql_attr/planner_contract.md`:
```
Strategy: sql_attr. search_scope: ["/bin/sql"].
Two-step: SQL query → cite specific SKU JSON file.
No directory traversal.
```

`data/prompts/lookup/sql_attr/evaluator_contract.md`:
```
Success: answer is <YES> or <NO>, grounding_refs contains a /proc/catalog/.+\.json path.
Fail: grounding_refs has only directory (not specific SKU file), answer missing.
required_evidence: ["/proc/catalog/<specific-SKU>.json"]
```

`data/prompts/lookup/sql_negative/executor_contract.md`:
```
You are an ExecutorAgent for LOOKUP / sql_negative.
Strategy: schema check first — attribute likely absent.

1. FIRST: /bin/sql '.schema' — check if attribute column exists.
2. Non-standard attrs (Bluetooth, app-scheduling, IoT, smart-home, WiFi) are NOT in schema.
   → answer <NO> immediately citing schema result.
3. If attribute IS in schema: run targeted SQL query.
4. SQL timeout: retry once, then use search fallback.

Grounding refs: schema result or specific product file.
```

`data/prompts/lookup/sql_negative/planner_contract.md`:
```
Strategy: sql_negative. search_scope: ["/bin/sql"].
Step 1 is always .schema check. Non-standard attributes → immediate NO.
```

`data/prompts/lookup/sql_negative/evaluator_contract.md`:
```
Success: schema checked first, <NO> with schema citation if attr absent.
Fail: SQL query run without schema check when attr is non-standard, timeout not retried.
required_evidence: ["/bin/sql schema output"]
```

`data/prompts/lookup/sql_broad/executor_contract.md`:
```
You are an ExecutorAgent for LOOKUP / sql_broad.
NEVER read individual catalogue files — thousands of files cause context overflow.

1. SQL only: SELECT sku, properties FROM products
             WHERE kind_id=? AND brand=? AND model=? AND properties LIKE ?
2. Filter results in-memory if needed.
3. Answer <YES>/<NO> with SQL result as grounding.

Grounding refs: ["/bin/sql"]
```

`data/prompts/lookup/sql_broad/planner_contract.md`:
```
Strategy: sql_broad. search_scope: ["/bin/sql"].
NEVER read individual catalogue files. SQL only.
```

`data/prompts/lookup/sql_broad/evaluator_contract.md`:
```
Success: SQL only, no filesystem reads, <YES>/<NO> with SQL grounding.
Fail: any individual catalogue file read, filesystem tree scan.
required_evidence: ["/bin/sql"]
```

- [ ] **Step 4: Create default contract JSON files**

`data/default_contracts/lookup_sql_count.json`:
```json
{
  "plan_steps": ["SELECT id FROM product_kinds WHERE name LIKE '%X%'", "SELECT COUNT(*) FROM products WHERE kind_id = ?", "report_completion with COUNT result"],
  "success_criteria": ["answer in <COUNT:n> format", "grounding_refs includes /bin/sql"],
  "required_evidence": ["/bin/sql"],
  "failure_conditions": ["filesystem reads performed", "answer not in COUNT format", "report before SQL executed"]
}
```

`data/default_contracts/lookup_sql_attr.json`:
```json
{
  "plan_steps": ["SQL query for brand/model/attribute", "answer YES or NO", "cite specific SKU file in grounding_refs"],
  "success_criteria": ["answer is <YES> or <NO>", "grounding_refs contains /proc/catalog/.../SKU.json"],
  "required_evidence": ["/proc/catalog/<SKU>.json"],
  "failure_conditions": ["grounding_refs has only directory path", "answer missing YES/NO token"]
}
```

`data/default_contracts/lookup_sql_negative.json`:
```json
{
  "plan_steps": ["/bin/sql .schema to check attribute existence", "if absent: answer <NO> citing schema", "if present: run targeted SQL"],
  "success_criteria": ["schema checked first", "<NO> with schema citation if attr absent"],
  "required_evidence": ["/bin/sql schema output"],
  "failure_conditions": ["SQL query run without schema check for non-standard attribute", "timeout not retried"]
}
```

`data/default_contracts/lookup_sql_broad.json`:
```json
{
  "plan_steps": ["SQL query across product category", "filter in-memory if needed", "answer YES/NO with SQL grounding"],
  "success_criteria": ["SQL only — no filesystem reads", "<YES>/<NO> with SQL result as grounding"],
  "required_evidence": ["/bin/sql"],
  "failure_conditions": ["individual catalogue file reads", "filesystem tree scan", "answer without SQL"]
}
```

- [ ] **Step 5: Run tests, confirm PASS**

```bash
uv run pytest tests/test_subtype_contract_files.py -v
```

- [ ] **Step 6: Commit**

```bash
git add data/prompts/lookup/ data/default_contracts/lookup_sql_*.json tests/test_subtype_contract_files.py
git commit -m "feat: add subtype-specific contract files for 4 lookup subtypes (FIX-458)"
```

---

## Task 13: `agent/maintenance/subtype_candidates.py` — review CLI

**Files:**
- Create: `agent/maintenance/subtype_candidates.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_subtype_candidates.py
import json, tempfile
from pathlib import Path
from unittest.mock import patch

def test_log_candidates_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "subtype_candidates.jsonl"
        from agent import classifier as cls
        with patch.object(cls, "_SUBTYPE_CANDIDATES_PATH", path):
            cls._log_subtype_candidate("lookup", "new:test_sub", "test reason", "none", "test task")
        records = [json.loads(l) for l in path.read_text().splitlines()]
        assert len(records) == 1
        assert records[0]["proposed_subtype"] == "new:test_sub"

def test_subtype_candidates_module_importable():
    from agent.maintenance import subtype_candidates
    assert hasattr(subtype_candidates, "main")
```

- [ ] **Step 2: Run test, confirm partial FAIL**

```bash
uv run pytest tests/test_subtype_candidates.py -v
```

- [ ] **Step 3: Create `agent/maintenance/__init__.py` if missing**

```bash
touch agent/maintenance/__init__.py
```

- [ ] **Step 4: Create `agent/maintenance/subtype_candidates.py`**

```python
"""CLI for reviewing proposed subtypes from subtype_candidates.jsonl.

Usage: uv run python -m agent.maintenance.subtype_candidates
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

_CANDIDATES_PATH = Path(__file__).parent.parent.parent / "data" / "subtype_candidates.jsonl"
_TASK_TYPES_PATH = Path(__file__).parent.parent.parent / "data" / "task_types.json"


def load_candidates() -> list[dict]:
    if not _CANDIDATES_PATH.exists():
        return []
    return [json.loads(line) for line in _CANDIDATES_PATH.read_text().splitlines() if line.strip()]


def summarise(candidates: list[dict]) -> dict[str, dict]:
    """Group by (task_type, proposed_subtype) with counts and examples."""
    summary: dict[str, dict] = {}
    for c in candidates:
        key = f"{c['task_type']}:{c['proposed_subtype']}"
        if key not in summary:
            summary[key] = {"task_type": c["task_type"], "proposed_subtype": c["proposed_subtype"],
                            "count": 0, "examples": [], "strategy": c.get("suggested_strategy", "standard")}
        summary[key]["count"] += 1
        if len(summary[key]["examples"]) < 3:
            summary[key]["examples"].append(c.get("task_text", "")[:80])
    return summary


def main() -> None:
    candidates = load_candidates()
    if not candidates:
        print("No subtype candidates found.")
        return
    summary = summarise(candidates)
    print(f"\n[SUBTYPE CANDIDATES] {len(summary)} unique proposed subtypes from {len(candidates)} occurrences:\n")
    for entry in sorted(summary.values(), key=lambda x: -x["count"]):
        print(f"  {entry['task_type']} → '{entry['proposed_subtype']}' ({entry['count']} occurrences) — strategy: {entry['strategy']}")
        for ex in entry["examples"]:
            print(f"    example: {ex!r}")
    print(f"\n→ To promote: add subtype to data/task_types.json under {{'subtypes': {{...}}}}")
    print("  Then: uv run python scripts/optimize_prompts.py --target classifier")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests, confirm PASS**

```bash
uv run pytest tests/test_subtype_candidates.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/maintenance/subtype_candidates.py agent/maintenance/__init__.py tests/test_subtype_candidates.py
git commit -m "feat: add subtype_candidates review CLI (FIX-459)"
```

---

## Task 14: Wiki — fix `hash_trajectory` and `_nm_traj`

**Files:**
- Modify: `agent/wiki_graph.py`
- Modify: `main.py`
- Modify: `data/wiki/pages/lookup.md`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_wiki_trajectory_fix.py
from agent.wiki_graph import hash_trajectory

def test_hash_trajectory_works_with_dicts():
    """hash_trajectory must handle both object and dict step_facts."""
    facts_dicts = [{"kind": "exec", "path": "/bin/sql"}, {"kind": "read", "path": "/proc/catalog/x.json"}]
    h = hash_trajectory(facts_dicts)
    assert h != "e3b0c44298fc"  # SHA256 of empty string
    assert len(h) == 12

def test_hash_trajectory_empty_kind_skipped():
    facts = [{"kind": "", "path": "/bin/sql"}, {"kind": "exec", "path": "/bin/sql"}]
    h = hash_trajectory(facts)
    # Only the exec entry with kind counts
    assert h == hash_trajectory([{"kind": "exec", "path": "/bin/sql"}])

def test_hash_trajectory_question_mark_skipped():
    """kind='?' (current bug value) must be skipped."""
    facts = [{"kind": "?", "path": ""}, {"kind": "exec", "path": "/bin/sql"}]
    h = hash_trajectory(facts)
    assert h == hash_trajectory([{"kind": "exec", "path": "/bin/sql"}])
```

- [ ] **Step 2: Run test, confirm FAIL**

```bash
uv run pytest tests/test_wiki_trajectory_fix.py -v
```

- [ ] **Step 3: Fix `hash_trajectory` in `agent/wiki_graph.py`**

```python
def hash_trajectory(step_facts: list) -> str:
    """Stable hash of the tool-call sequence. Handles both object and dict step_facts."""
    parts: list[str] = []
    for f in step_facts or []:
        kind = getattr(f, "kind", None)
        if kind is None and isinstance(f, dict):
            kind = f.get("kind", "")
        path = getattr(f, "path", None)
        if path is None and isinstance(f, dict):
            path = f.get("path", "")
        kind = str(kind or "")
        path = str(path or "")
        if kind and kind != "?":
            parts.append(f"{kind}:{path}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 4: Fix `_nm_traj` in `main.py`** (around line 347)

```python
def _fact_field(f, attr: str, default: str = "") -> str:
    val = getattr(f, attr, None)
    if val is None and isinstance(f, dict):
        val = f.get(attr)
    return str(val or default)

_nm_traj = [
    {
        "tool": _fact_field(f, "kind"),
        "path": _fact_field(f, "path"),
        "summary": _fact_field(f, "summary"),
    }
    for f in _nm_step_facts
]
_nm_traj_meaningful = [s for s in _nm_traj if s["tool"] not in ("", "?")]
if _score_f >= 1.0 and _nm_traj_meaningful:
    # replace _nm_traj with _nm_traj_meaningful in the promote_successful_pattern call
```

- [ ] **Step 5: Run tests, confirm PASS**

```bash
uv run pytest tests/test_wiki_trajectory_fix.py -v
```

- [ ] **Step 6: Clean empty patterns from `data/wiki/pages/lookup.md`**

```bash
uv run python -c "
import re
from pathlib import Path
p = Path('data/wiki/pages/lookup.md')
content = p.read_text()
# Remove sections: ## Successful pattern: ... with trajectory: ?
cleaned = re.sub(r'## Successful pattern:.*?(?=^##|\Z)', '', content, flags=re.DOTALL|re.MULTILINE)
p.write_text(cleaned)
print('Done. Lines:', len(cleaned.splitlines()))
"
```

Verify no `trajectory: ?` remains:
```bash
grep -c "trajectory: ?" data/wiki/pages/lookup.md
```
Expected: `0`

- [ ] **Step 7: Commit**

```bash
git add agent/wiki_graph.py main.py data/wiki/pages/lookup.md tests/test_wiki_trajectory_fix.py
git commit -m "fix: hash_trajectory handles dict step_facts; skip empty/? kinds; remove empty wiki patterns (FIX-460)"
```

---

## Task 15: Integration smoke test + full test suite

- [ ] **Step 1: Run full test suite**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: no new failures vs baseline.

- [ ] **Step 2: Run subtype-specific tests together**

```bash
uv run pytest tests/test_task_types_subtypes.py tests/test_contracts_subtype.py tests/test_classifier_subtype.py tests/agents/test_classifier_agent_subtype.py tests/test_prephase_strategy.py tests/agents/test_orchestrator_subtype.py tests/test_discovery_gate_sql.py tests/test_error_counts_key.py tests/test_prompt_subtype_blocks.py tests/test_evaluator_subtype.py tests/test_dispatch_sql_retry.py tests/test_contract_phase_subtype.py tests/test_subtype_contract_files.py tests/test_subtype_candidates.py tests/test_wiki_trajectory_fix.py -v
```
Expected: all pass.

- [ ] **Step 3: Verify wiki pages clean**

```bash
grep "trajectory: ?" data/wiki/pages/lookup.md && echo FOUND || echo CLEAN
```
Expected: `CLEAN`

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "test: integration smoke — all subtype pipeline tests passing"
```

---

## Post-implementation: DSPy recompilation

After collecting new benchmark run examples:

```bash
# Run benchmark to collect examples with subtype outputs
make run

# Recompile in order
uv run python scripts/optimize_prompts.py --target classifier   # learns subtype prediction
uv run python scripts/optimize_prompts.py --target builder      # subtype-aware addendum
uv run python scripts/optimize_prompts.py --target evaluator    # subtype-aware scoring
```

Existing compiled programs fail-open — agent runs on default prompts until recompiled.
