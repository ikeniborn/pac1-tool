# Multi-Agent Hub-and-Spoke Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рефакторинг монолитного агента в 10 изолированных агентов с типизированными Pydantic-контрактами (in-process, никакой переписки с нуля).

**Architecture:** Hub-and-Spoke: Orchestrator вызывает агентов напрямую, агенты изолированы через `agent/contracts/__init__.py`. Существующие модули (`loop.py`, `security.py`, `stall.py` и т.д.) остаются — агенты являются тонкими обёртками. `loop.py` очищается от прямых вызовов, получает DI-параметры.

**Tech Stack:** Python 3.11+, Pydantic v2, существующие модули agent/, ThreadPoolExecutor для параллелизма в оркестраторе.

---

## Карта файлов

**Создать:**
- `agent/contracts/__init__.py` — все типизированные контракты (единственный shared import)
- `agent/agents/__init__.py` — пустой (пакет)
- `agent/agents/security_agent.py` — обёртка над `agent.security`
- `agent/agents/stall_agent.py` — обёртка над `agent.stall._check_stall`
- `agent/agents/compaction_agent.py` — обёртка над `agent.log_compaction._compact_log`
- `agent/agents/step_guard_agent.py` — обёртка над `agent.contract_monitor.check_step`
- `agent/agents/classifier_agent.py` — обёртка над `agent.classifier.ModelRouter`
- `agent/agents/wiki_graph_agent.py` — обёртка над `agent.wiki` + `agent.wiki_graph`
- `agent/agents/verifier_agent.py` — обёртка над `agent.evaluator.evaluate_completion`
- `agent/agents/planner_agent.py` — обёртка над `contract_phase` + `prompt_builder` + `_route_task`
- `agent/agents/executor_agent.py` — обёртка над `run_loop` с DI
- `agent/orchestrator.py` — новый pipeline (заменяет логику `agent/__init__.py`)
- `tests/agents/__init__.py`
- `tests/agents/test_contracts.py`
- `tests/agents/test_security_agent.py`
- `tests/agents/test_stall_agent.py`
- `tests/agents/test_compaction_agent.py`
- `tests/agents/test_step_guard_agent.py`
- `tests/agents/test_classifier_agent.py`
- `tests/agents/test_wiki_graph_agent.py`
- `tests/agents/test_verifier_agent.py`
- `tests/agents/test_planner_agent.py`
- `tests/agents/test_executor_agent.py`
- `tests/agents/test_orchestrator.py`

**Изменить:**
- `agent/loop.py` — добавить DI-параметры для security/stall/compaction/verifier/step_guard; убрать `_route_task` из начала цикла
- `agent/__init__.py` — заменить pipeline на `from .orchestrator import run_agent, write_wiki_fragment`

---

## Task 0: Contracts Module

**Files:**
- Create: `agent/contracts/__init__.py`
- Create: `tests/agents/__init__.py`
- Create: `tests/agents/test_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_contracts.py
def test_imports():
    from agent.contracts import (
        TaskInput, ClassificationResult,
        WikiReadRequest, WikiContext,
        PlannerInput, ExecutionPlan,
        SecurityRequest, SecurityCheck,
        StepGuardRequest, StepValidation,
        StallRequest, StallResult,
        CompactionRequest, CompactedLog,
        CompletionRequest, VerificationResult,
        ExecutorInput, ExecutionResult,
        WikiFeedbackRequest,
    )

def test_task_input_fields():
    from agent.contracts import TaskInput
    t = TaskInput(task_text="do X", harness_url="http://localhost", trial_id="t01")
    assert t.task_text == "do X"
    assert t.trial_id == "t01"

def test_security_check_passed():
    from agent.contracts import SecurityCheck
    c = SecurityCheck(passed=True)
    assert c.passed is True
    assert c.violation_type is None

def test_security_check_violation():
    from agent.contracts import SecurityCheck
    c = SecurityCheck(passed=False, violation_type="write_scope", detail="blocked /docs/")
    assert c.passed is False
    assert c.violation_type == "write_scope"

def test_execution_result_status_literal():
    from agent.contracts import ExecutionResult
    import pytest
    with pytest.raises(Exception):
        ExecutionResult(status="unknown", outcome="x", token_stats={},
                        step_facts=[], injected_node_ids=[], rejection_count=0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_contracts.py -v
```
Expected: `ImportError: cannot import name 'TaskInput' from 'agent.contracts'`

- [ ] **Step 3: Create `tests/agents/__init__.py`**

```python
# tests/agents/__init__.py
```

- [ ] **Step 4: Create `agent/contracts/__init__.py`**

```python
# agent/contracts/__init__.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# Re-export existing types so consumers only import from agent.contracts
from agent.contract_models import Contract
from agent.models import ReportTaskCompletion
from agent.prephase import PrephaseResult


class TaskInput(BaseModel):
    task_text: str
    harness_url: str
    trial_id: str


class ClassificationResult(BaseModel):
    task_type: str
    model: str
    model_cfg: dict
    confidence: float


class WikiReadRequest(BaseModel):
    task_type: str
    task_text: str


class WikiContext(BaseModel):
    patterns_text: str
    graph_section: str
    injected_node_ids: list[str]


class PlannerInput(BaseModel):
    task_input: TaskInput
    classification: ClassificationResult
    wiki_context: WikiContext
    prephase: PrephaseResult

    model_config = {"arbitrary_types_allowed": True}


class ExecutionPlan(BaseModel):
    base_prompt: str
    addendum: str
    contract: Contract | None
    route: Literal["EXECUTE", "DENY_SECURITY", "CLARIFY", "UNSUPPORTED"]
    in_tokens: int
    out_tokens: int


class SecurityRequest(BaseModel):
    tool_name: str
    tool_args: dict
    task_type: str
    message_text: str | None = None


class SecurityCheck(BaseModel):
    passed: bool
    violation_type: str | None = None
    detail: str | None = None


class StepGuardRequest(BaseModel):
    step_index: int
    tool_name: str
    tool_args: dict
    contract: Contract

    model_config = {"arbitrary_types_allowed": True}


class StepValidation(BaseModel):
    valid: bool
    deviation: str | None = None
    suggestion: str | None = None


class StallRequest(BaseModel):
    step_index: int
    fingerprints: list[str]
    error_counts: dict[str, int]
    steps_without_write: int
    step_facts_dicts: list[dict] = []
    contract_plan_steps: list[str] | None = None


class StallResult(BaseModel):
    detected: bool
    hint: str | None = None
    escalation_level: int = 0


class CompactionRequest(BaseModel):
    messages: list[dict]
    preserve_prefix: list[dict]
    step_facts_dicts: list[dict]
    token_limit: int


class CompactedLog(BaseModel):
    messages: list[dict]
    tokens_saved: int


class CompletionRequest(BaseModel):
    """Passed from ExecutorAgent to VerifierAgent at each ReportTaskCompletion."""
    report: ReportTaskCompletion
    task_type: str
    task_text: str
    wiki_context: WikiContext
    contract: Contract | None
    # Fields needed by evaluate_completion() — populated from loop state
    done_ops: list[str] = []
    digest_str: str = ""
    evaluator_model: str = ""
    evaluator_cfg: dict = {}
    rejection_count: int = 0

    model_config = {"arbitrary_types_allowed": True}


class VerificationResult(BaseModel):
    approved: bool
    feedback: str | None = None
    rejection_count: int = 0
    hard_gate_triggered: str | None = None


class ExecutorInput(BaseModel):
    task_input: TaskInput
    plan: ExecutionPlan
    wiki_context: WikiContext
    prephase: PrephaseResult
    harness_url: str          # ExecutorAgent creates vm from this
    task_type: str
    evaluator_model: str
    evaluator_cfg: dict

    model_config = {"arbitrary_types_allowed": True}


class ExecutionResult(BaseModel):
    status: Literal["completed", "denied", "timeout", "error"]
    outcome: str
    token_stats: dict[str, int]
    step_facts: list[dict]
    injected_node_ids: list[str]
    rejection_count: int


class WikiFeedbackRequest(BaseModel):
    task_type: str
    task_text: str
    execution_result: ExecutionResult
    wiki_context: WikiContext
    score: float
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_contracts.py -v
```
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add agent/contracts/__init__.py tests/agents/__init__.py tests/agents/test_contracts.py
git commit -m "feat(agents): add contracts module with typed inter-agent interfaces"
```

---

## Task 1: SecurityAgent

**Files:**
- Create: `agent/agents/__init__.py`
- Create: `agent/agents/security_agent.py`
- Create: `tests/agents/test_security_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_security_agent.py
import types

def _make_req(tool_name="Req_Write", tool_args=None, task_type="email", message_text=None):
    from agent.contracts import SecurityRequest
    return SecurityRequest(
        tool_name=tool_name,
        tool_args=tool_args or {"path": "/outbox/1.json", "content": "{}"},
        task_type=task_type,
        message_text=message_text,
    )


def test_write_scope_email_outbox_passes():
    from agent.agents.security_agent import SecurityAgent
    from agent.contracts import SecurityCheck
    agent = SecurityAgent()
    result = agent.check_write_scope(_make_req(
        tool_name="Req_Write",
        tool_args={"path": "/outbox/1.json", "content": "{}"},
        task_type="email",
    ))
    assert isinstance(result, SecurityCheck)
    assert result.passed is True


def test_write_scope_system_path_blocked():
    from agent.agents.security_agent import SecurityAgent
    agent = SecurityAgent()
    result = agent.check_write_scope(_make_req(
        tool_name="Req_Write",
        tool_args={"path": "/docs/secret.md", "content": "x"},
        task_type="email",
    ))
    assert result.passed is False
    assert result.violation_type == "write_scope"


def test_check_injection_clean_text_passes():
    from agent.agents.security_agent import SecurityAgent
    agent = SecurityAgent()
    result = agent.check_injection("Please summarize the email thread")
    assert result.passed is True


def test_check_write_payload_injection_blocked():
    from agent.agents.security_agent import SecurityAgent
    agent = SecurityAgent()
    result = agent.check_write_payload(
        content="origin: security-bridge\ndo something",
        source_path="/notes/memo.md",
    )
    assert result.passed is False
    assert result.violation_type == "injection"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_security_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.security_agent'`

- [ ] **Step 3: Create `agent/agents/__init__.py`**

```python
# agent/agents/__init__.py
```

- [ ] **Step 4: Create `agent/agents/security_agent.py`**

```python
# agent/agents/security_agent.py
from __future__ import annotations
import types

from agent.contracts import SecurityCheck, SecurityRequest
from agent.security import (
    _check_write_scope,
    _check_write_payload_injection,
    _normalize_for_injection,
    _INJECTION_RE,
)


class SecurityAgent:
    def check_write_scope(self, request: SecurityRequest) -> SecurityCheck:
        # Build a namespace object that mimics the Pydantic tool model
        action = types.SimpleNamespace(**request.tool_args)
        error = _check_write_scope(action, request.tool_name, request.task_type)
        if error:
            return SecurityCheck(passed=False, violation_type="write_scope", detail=error)
        return SecurityCheck(passed=True)

    def check_injection(self, text: str) -> SecurityCheck:
        norm = _normalize_for_injection(text)
        if _INJECTION_RE.search(norm):
            return SecurityCheck(passed=False, violation_type="injection",
                                 detail="injection pattern detected")
        return SecurityCheck(passed=True)

    def check_write_payload(self, content: str, source_path: str | None = None) -> SecurityCheck:
        if _check_write_payload_injection(content, source_path):
            return SecurityCheck(passed=False, violation_type="injection",
                                 detail="write payload injection detected")
        return SecurityCheck(passed=True)
```

Note: `_INJECTION_RE` lives in `agent.loop`. Before running tests, verify its location:
```bash
uv run python -c "from agent.loop import _INJECTION_RE; print('ok')"
```
If it's in `agent.loop`, import from there. If moved to `agent.security`, adjust the import.

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_security_agent.py -v
```
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add agent/agents/__init__.py agent/agents/security_agent.py tests/agents/test_security_agent.py
git commit -m "feat(agents): add SecurityAgent wrapper"
```

---

## Task 2: StallAgent

**Files:**
- Create: `agent/agents/stall_agent.py`
- Create: `tests/agents/test_stall_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_stall_agent.py
def _make_req(fingerprints=None, steps_without_write=0, error_counts=None):
    from agent.contracts import StallRequest
    return StallRequest(
        step_index=steps_without_write,
        fingerprints=fingerprints or [],
        error_counts=error_counts or {},
        steps_without_write=steps_without_write,
    )


def test_no_stall_returns_not_detected():
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=2))
    assert result.detected is False
    assert result.hint is None


def test_repeated_fingerprint_detected():
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(
        fingerprints=["Req_Read:/notes/x.md:ok"] * 3,
        steps_without_write=2,
    ))
    assert result.detected is True
    assert result.hint is not None
    assert "Req_Read" in result.hint


def test_exploration_stall_at_6_steps():
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=6))
    assert result.detected is True
    assert result.hint is not None


def test_escalation_at_12_steps():
    from agent.agents.stall_agent import StallAgent
    agent = StallAgent()
    result = agent.check(_make_req(steps_without_write=12))
    assert result.detected is True
    assert result.escalation_level >= 2
    assert "ESCALATION" in (result.hint or "")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_stall_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.stall_agent'`

- [ ] **Step 3: Create `agent/agents/stall_agent.py`**

```python
# agent/agents/stall_agent.py
from __future__ import annotations

from collections import Counter, deque

from agent.contracts import StallRequest, StallResult
from agent.log_compaction import _StepFact
from agent.stall import _check_stall


class StallAgent:
    def check(self, request: StallRequest) -> StallResult:
        fp = deque(request.fingerprints, maxlen=10)
        ec: Counter = Counter(request.error_counts)
        facts = [
            _StepFact(
                kind=d.get("kind", ""),
                path=d.get("path", ""),
                summary=d.get("summary", ""),
                error=d.get("error", ""),
            )
            for d in request.step_facts_dicts
        ]
        hint = _check_stall(
            fp,
            request.steps_without_write,
            ec,
            facts or None,
            request.contract_plan_steps,
        )
        if hint is None:
            return StallResult(detected=False)
        escalation = 1
        if request.steps_without_write >= 12:
            escalation = 2
        if request.steps_without_write >= 18:
            escalation = 3
        return StallResult(detected=True, hint=hint, escalation_level=escalation)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_stall_agent.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/stall_agent.py tests/agents/test_stall_agent.py
git commit -m "feat(agents): add StallAgent wrapper"
```

---

## Task 3: CompactionAgent

**Files:**
- Create: `agent/agents/compaction_agent.py`
- Create: `tests/agents/test_compaction_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_compaction_agent.py
def _make_messages(n=20):
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"msg {i} " + "x" * 100})
    return msgs


def test_returns_compacted_log_type():
    from agent.agents.compaction_agent import CompactionAgent
    from agent.contracts import CompactionRequest, CompactedLog
    agent = CompactionAgent()
    msgs = _make_messages(20)
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=300,
    )
    result = agent.compact(req)
    assert isinstance(result, CompactedLog)
    assert isinstance(result.messages, list)


def test_compaction_reduces_messages():
    from agent.agents.compaction_agent import CompactionAgent
    from agent.contracts import CompactionRequest
    agent = CompactionAgent()
    msgs = _make_messages(30)
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=200,
    )
    result = agent.compact(req)
    assert len(result.messages) < len(msgs)


def test_no_compaction_when_within_budget():
    from agent.agents.compaction_agent import CompactionAgent
    from agent.contracts import CompactionRequest
    agent = CompactionAgent()
    msgs = [{"role": "user", "content": "hi"}]
    req = CompactionRequest(
        messages=msgs,
        preserve_prefix=msgs[:1],
        step_facts_dicts=[],
        token_limit=100_000,
    )
    result = agent.compact(req)
    assert len(result.messages) == len(msgs)
    assert result.tokens_saved == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_compaction_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.compaction_agent'`

- [ ] **Step 3: Create `agent/agents/compaction_agent.py`**

```python
# agent/agents/compaction_agent.py
from __future__ import annotations

from agent.contracts import CompactedLog, CompactionRequest
from agent.log_compaction import _StepFact, _compact_log, _estimate_tokens


class CompactionAgent:
    def compact(self, request: CompactionRequest) -> CompactedLog:
        facts = [
            _StepFact(
                kind=d.get("kind", ""),
                path=d.get("path", ""),
                summary=d.get("summary", ""),
                error=d.get("error", ""),
            )
            for d in request.step_facts_dicts
        ]
        before = len(request.messages)
        compacted = _compact_log(
            request.messages,
            preserve_prefix=request.preserve_prefix,
            step_facts=facts or None,
            token_limit=request.token_limit,
        )
        tokens_saved = max(0, _estimate_tokens(request.messages) - _estimate_tokens(compacted))
        return CompactedLog(messages=compacted, tokens_saved=tokens_saved)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_compaction_agent.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/compaction_agent.py tests/agents/test_compaction_agent.py
git commit -m "feat(agents): add CompactionAgent wrapper"
```

---

## Task 4: StepGuardAgent

**Files:**
- Create: `agent/agents/step_guard_agent.py`
- Create: `tests/agents/test_step_guard_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_step_guard_agent.py
def _make_contract(plan_steps=None):
    from agent.contract_models import Contract
    return Contract(
        plan_steps=plan_steps or ["write /outbox/1.json"],
        success_criteria=["email written"],
        required_evidence=["/outbox/1.json"],
        failure_conditions=[],
        is_default=False,
        rounds_taken=1,
    )


def test_no_deviation_returns_valid():
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.contracts import StepGuardRequest
    agent = StepGuardAgent()
    req = StepGuardRequest(
        step_index=4,
        tool_name="Req_Write",
        tool_args={"path": "/outbox/1.json", "content": "{}"},
        contract=_make_contract(["write /outbox/"]),
    )
    result = agent.check(req)
    assert result.valid is True
    assert result.deviation is None


def test_unexpected_delete_returns_deviation():
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.contracts import StepGuardRequest
    agent = StepGuardAgent()
    req = StepGuardRequest(
        step_index=5,
        tool_name="Req_Delete",
        tool_args={"path": "/important/file.md"},
        contract=_make_contract(["write /outbox/1.json"]),
    )
    result = agent.check(req)
    assert result.valid is False
    assert result.deviation is not None


def test_no_contract_always_valid():
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.contracts import StepGuardRequest, StepValidation
    agent = StepGuardAgent()
    result = agent.check_optional(
        step_index=5,
        tool_name="Req_Delete",
        tool_args={"path": "/important/file.md"},
        done_operations=["DELETED: /important/file.md"],
        contract=None,
    )
    assert result.valid is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_step_guard_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.step_guard_agent'`

- [ ] **Step 3: Create `agent/agents/step_guard_agent.py`**

```python
# agent/agents/step_guard_agent.py
from __future__ import annotations

from agent.contract_models import Contract
from agent.contract_monitor import check_step
from agent.contracts import StepGuardRequest, StepValidation


class StepGuardAgent:
    def check(self, request: StepGuardRequest) -> StepValidation:
        # Reconstruct done_operations from tool_args for the monitor
        path = request.tool_args.get("path", request.tool_args.get("from_name", ""))
        if request.tool_name == "Req_Delete":
            done_ops = [f"DELETED: {path}"]
        elif request.tool_name in ("Req_Write", "Req_MkDir"):
            done_ops = [f"WRITTEN: {path}"]
        else:
            done_ops = []

        warning = check_step(request.contract, done_ops, step_num=request.step_index)
        if warning:
            return StepValidation(valid=False, deviation=warning,
                                  suggestion="Verify this operation matches your contract plan.")
        return StepValidation(valid=True)

    def check_optional(
        self,
        step_index: int,
        tool_name: str,
        tool_args: dict,
        done_operations: list[str],
        contract: Contract | None,
    ) -> StepValidation:
        if contract is None:
            return StepValidation(valid=True)
        warning = check_step(contract, done_operations, step_num=step_index)
        if warning:
            return StepValidation(valid=False, deviation=warning)
        return StepValidation(valid=True)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_step_guard_agent.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/step_guard_agent.py tests/agents/test_step_guard_agent.py
git commit -m "feat(agents): add StepGuardAgent wrapper"
```

---

## Task 5: ClassifierAgent

**Files:**
- Create: `agent/agents/classifier_agent.py`
- Create: `tests/agents/test_classifier_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_classifier_agent.py
import pytest


def _make_router():
    """Build a minimal ModelRouter using models.json."""
    from agent.classifier import ModelRouter
    import json
    from pathlib import Path
    configs = json.loads((Path("data/models.json")).read_text())
    default = next(iter(configs))
    return ModelRouter(
        default=default,
        classifier=default,
        configs=configs,
    )


def test_returns_classification_result_type():
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import ClassificationResult, TaskInput
    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="Send an email to alice@example.com about the meeting",
        harness_url="http://localhost:50051",
        trial_id="t01",
    )
    result = agent.run(task)
    assert isinstance(result, ClassificationResult)
    assert result.task_type in ("email", "default")
    assert result.model
    assert isinstance(result.model_cfg, dict)


def test_preject_task_classified():
    from agent.agents.classifier_agent import ClassifierAgent
    from agent.contracts import TaskInput
    router = _make_router()
    agent = ClassifierAgent(router=router)
    task = TaskInput(
        task_text="",
        harness_url="http://localhost:50051",
        trial_id="t01",
    )
    result = agent.run(task)
    assert isinstance(result.task_type, str)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_classifier_agent.py::test_returns_classification_result_type -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.classifier_agent'`

- [ ] **Step 3: Create `agent/agents/classifier_agent.py`**

```python
# agent/agents/classifier_agent.py
from __future__ import annotations

from agent.classifier import ModelRouter
from agent.contracts import ClassificationResult, TaskInput
from agent.prephase import PrephaseResult


class ClassifierAgent:
    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    def run(self, task: TaskInput, prephase: PrephaseResult | None = None) -> ClassificationResult:
        """Classify task type and select model.

        prephase is optional: if provided, vault hints improve classification accuracy.
        Without prephase, regex fast-path and LLM classify with no vault context.
        """
        if prephase is not None:
            model, cfg, task_type = self._router.resolve_after_prephase(task.task_text, prephase)
        else:
            # Regex fast-path without vault hints
            from agent.classifier import classify_task
            task_type = classify_task(task.task_text)
            model = self._router.default
            cfg = self._router.configs.get(model, {})

        return ClassificationResult(
            task_type=task_type,
            model=model,
            model_cfg=cfg,
            confidence=1.0 if prephase is not None else 0.8,
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_classifier_agent.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/classifier_agent.py tests/agents/test_classifier_agent.py
git commit -m "feat(agents): add ClassifierAgent wrapper"
```

---

## Task 6: WikiGraphAgent

**Files:**
- Create: `agent/agents/wiki_graph_agent.py`
- Create: `tests/agents/test_wiki_graph_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_wiki_graph_agent.py
import os


def test_read_returns_wiki_context_type():
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import WikiContext, WikiReadRequest
    agent = WikiGraphAgent()
    req = WikiReadRequest(task_type="email", task_text="send email to alice")
    result = agent.read(req)
    assert isinstance(result, WikiContext)
    assert isinstance(result.patterns_text, str)
    assert isinstance(result.graph_section, str)
    assert isinstance(result.injected_node_ids, list)


def test_read_disabled_when_wiki_off(monkeypatch):
    monkeypatch.setenv("WIKI_ENABLED", "0")
    monkeypatch.setenv("WIKI_GRAPH_ENABLED", "0")
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import WikiReadRequest
    agent = WikiGraphAgent(wiki_enabled=False, graph_enabled=False)
    result = agent.read(WikiReadRequest(task_type="email", task_text="x"))
    assert result.patterns_text == ""
    assert result.graph_section == ""
    assert result.injected_node_ids == []


def test_write_feedback_does_not_raise():
    from agent.agents.wiki_graph_agent import WikiGraphAgent
    from agent.contracts import ExecutionResult, WikiContext, WikiFeedbackRequest
    agent = WikiGraphAgent()
    req = WikiFeedbackRequest(
        task_type="email",
        task_text="send email",
        execution_result=ExecutionResult(
            status="completed",
            outcome="OUTCOME_OK",
            token_stats={},
            step_facts=[],
            injected_node_ids=[],
            rejection_count=0,
        ),
        wiki_context=WikiContext(
            patterns_text="",
            graph_section="",
            injected_node_ids=[],
        ),
        score=1.0,
    )
    agent.write_feedback(req)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_wiki_graph_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.wiki_graph_agent'`

- [ ] **Step 3: Create `agent/agents/wiki_graph_agent.py`**

```python
# agent/agents/wiki_graph_agent.py
from __future__ import annotations

import os

from agent.contracts import WikiContext, WikiFeedbackRequest, WikiReadRequest

_WIKI_ENABLED = os.getenv("WIKI_ENABLED", "1") == "1"
_GRAPH_ENABLED = os.getenv("WIKI_GRAPH_ENABLED", "1") == "1"
_GRAPH_TOP_K = int(os.getenv("WIKI_GRAPH_TOP_K", "5"))


class WikiGraphAgent:
    def __init__(
        self,
        wiki_enabled: bool | None = None,
        graph_enabled: bool | None = None,
    ) -> None:
        self._wiki = _WIKI_ENABLED if wiki_enabled is None else wiki_enabled
        self._graph = _GRAPH_ENABLED if graph_enabled is None else graph_enabled

    def read(self, request: WikiReadRequest) -> WikiContext:
        patterns_text = ""
        graph_section = ""
        injected_ids: list[str] = []

        if self._wiki:
            try:
                from agent.wiki import load_wiki_patterns
                patterns_text = load_wiki_patterns(request.task_type) or ""
            except Exception as exc:
                print(f"[wiki-agent] load_wiki_patterns failed ({exc})")

        if self._graph:
            try:
                from agent import wiki_graph
                g = wiki_graph.load_graph()
                if g.nodes:
                    graph_section, injected_ids = wiki_graph.retrieve_relevant_with_ids(
                        g, request.task_type, request.task_text, top_k=_GRAPH_TOP_K,
                    )
            except Exception as exc:
                print(f"[wiki-agent] graph retrieval failed ({exc})")

        return WikiContext(
            patterns_text=patterns_text,
            graph_section=graph_section,
            injected_node_ids=injected_ids,
        )

    def write_feedback(self, request: WikiFeedbackRequest) -> None:
        """Update wiki graph confidence based on execution score. Fail-open."""
        if not self._graph:
            return
        try:
            from agent import wiki_graph
            g = wiki_graph.load_graph()
            node_ids = request.wiki_context.injected_node_ids
            if not node_ids:
                return
            epsilon = float(os.getenv("WIKI_GRAPH_CONFIDENCE_EPSILON", "0.05"))
            if request.score >= 1.0:
                wiki_graph.bump_uses(g, node_ids)
            else:
                wiki_graph.degrade_confidence(g, node_ids, epsilon)
            wiki_graph.save_graph(g)
        except Exception as exc:
            print(f"[wiki-agent] write_feedback failed ({exc})")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_wiki_graph_agent.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/wiki_graph_agent.py tests/agents/test_wiki_graph_agent.py
git commit -m "feat(agents): add WikiGraphAgent wrapper"
```

---

## Task 7: VerifierAgent

**Files:**
- Create: `agent/agents/verifier_agent.py`
- Create: `tests/agents/test_verifier_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_verifier_agent.py
from agent.models import ReportTaskCompletion
from agent.contracts import WikiContext


def _make_report(outcome="OUTCOME_OK", message="Done", grounding_refs=None):
    return ReportTaskCompletion(
        tool="report_completion",
        completed_steps_laconic=["wrote /outbox/1.json"],
        message=message,
        grounding_refs=grounding_refs or ["/outbox/1.json"],
        outcome=outcome,
    )


def _make_wiki_ctx():
    return WikiContext(patterns_text="", graph_section="", injected_node_ids=[])


def test_returns_verification_result_type():
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest, VerificationResult
    agent = VerifierAgent(enabled=False)  # disabled → auto-approve
    req = CompletionRequest(
        report=_make_report(),
        task_type="email",
        task_text="send email",
        wiki_context=_make_wiki_ctx(),
        contract=None,
    )
    result = agent.verify(req)
    assert isinstance(result, VerificationResult)
    assert result.approved is True


def test_disabled_evaluator_auto_approves():
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest
    agent = VerifierAgent(enabled=False)
    req = CompletionRequest(
        report=_make_report(outcome="OUTCOME_DENIED_SECURITY"),
        task_type="email",
        task_text="x",
        wiki_context=_make_wiki_ctx(),
        contract=None,
    )
    result = agent.verify(req)
    assert result.approved is True


def test_verify_with_model_returns_result():
    """VerifierAgent with a real model must return VerificationResult without raising."""
    import json
    from pathlib import Path
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import CompletionRequest
    configs = json.loads(Path("data/models.json").read_text())
    default = next(iter(configs))
    agent = VerifierAgent(
        enabled=True,
        model=default,
        cfg=configs[default],
    )
    req = CompletionRequest(
        report=_make_report(),
        task_type="email",
        task_text="send email to alice",
        wiki_context=_make_wiki_ctx(),
        contract=None,
        done_ops=["WRITTEN: /outbox/1.json"],
        digest_str="State digest:\nDONE:\n  WRITTEN: /outbox/1.json",
        evaluator_model=default,
        evaluator_cfg=configs[default],
    )
    result = agent.verify(req)
    assert isinstance(result.approved, bool)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_verifier_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.verifier_agent'`

- [ ] **Step 3: Create `agent/agents/verifier_agent.py`**

The real signature of `evaluate_completion` (verified from `agent/evaluator.py:387`):
```
evaluate_completion(task_text, task_type, report, done_ops, digest_str,
                    model, cfg, skepticism="mid", efficiency="mid",
                    account_evidence="", inbox_evidence="", fail_closed=False,
                    contract=None) → EvalVerdict(approved, issues, correction_hint)
```

```python
# agent/agents/verifier_agent.py
from __future__ import annotations

import os

from agent.contracts import CompletionRequest, VerificationResult

_EVALUATOR_ENABLED = os.getenv("EVALUATOR_ENABLED", "1") == "1"
_EVAL_SKEPTICISM = os.getenv("EVAL_SKEPTICISM", "mid")
_EVAL_EFFICIENCY = os.getenv("EVAL_EFFICIENCY", "mid")


class VerifierAgent:
    def __init__(
        self,
        enabled: bool | None = None,
        model: str = "",
        cfg: dict | None = None,
    ) -> None:
        self._enabled = _EVALUATOR_ENABLED if enabled is None else enabled
        self._model = model
        self._cfg = cfg or {}

    def verify(self, request: CompletionRequest) -> VerificationResult:
        if not self._enabled:
            return VerificationResult(approved=True, rejection_count=request.rejection_count)

        model = request.evaluator_model or self._model
        cfg = request.evaluator_cfg or self._cfg
        if not model:
            return VerificationResult(approved=True, rejection_count=request.rejection_count)

        try:
            from agent.evaluator import evaluate_completion
            verdict = evaluate_completion(
                task_text=request.task_text,
                task_type=request.task_type,
                report=request.report,
                done_ops=request.done_ops,
                digest_str=request.digest_str,
                model=model,
                cfg=cfg,
                skepticism=_EVAL_SKEPTICISM,
                efficiency=_EVAL_EFFICIENCY,
                contract=request.contract,
            )
            new_count = request.rejection_count if verdict.approved else request.rejection_count + 1
            return VerificationResult(
                approved=verdict.approved,
                feedback=verdict.correction_hint if not verdict.approved else None,
                rejection_count=new_count,
            )
        except Exception as exc:
            print(f"[verifier] evaluate_completion failed ({exc}) — auto-approving")
            return VerificationResult(approved=True, rejection_count=request.rejection_count)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_verifier_agent.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/verifier_agent.py tests/agents/test_verifier_agent.py
git commit -m "feat(agents): add VerifierAgent wrapper"
```

---

## Task 8: PlannerAgent

**Files:**
- Create: `agent/agents/planner_agent.py`
- Create: `tests/agents/test_planner_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_planner_agent.py
from agent.contracts import (
    ClassificationResult, ExecutionPlan, PlannerInput, TaskInput, WikiContext
)
from agent.prephase import PrephaseResult


def _make_planner_input(task_type="email"):
    pre = PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[{"role": "system", "content": "sys"}],
    )
    return PlannerInput(
        task_input=TaskInput(
            task_text="Send email to alice@example.com about meeting",
            harness_url="http://localhost",
            trial_id="t01",
        ),
        classification=ClassificationResult(
            task_type=task_type,
            model="claude-haiku-4-5",
            model_cfg={},
            confidence=1.0,
        ),
        wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
        prephase=pre,
    )


def test_returns_execution_plan_type():
    from agent.agents.planner_agent import PlannerAgent
    import json
    from pathlib import Path
    configs = json.loads(Path("data/models.json").read_text())
    default = next(iter(configs))

    agent = PlannerAgent(
        model=default,
        cfg=configs[default],
        prompt_builder_enabled=False,
        contract_enabled=False,
    )
    result = agent.run(_make_planner_input())
    assert isinstance(result, ExecutionPlan)
    assert result.base_prompt
    assert result.route in ("EXECUTE", "DENY_SECURITY", "CLARIFY", "UNSUPPORTED")
    assert result.contract is None  # contract_enabled=False


def test_plan_contains_base_prompt():
    from agent.agents.planner_agent import PlannerAgent
    import json
    from pathlib import Path
    configs = json.loads(Path("data/models.json").read_text())
    default = next(iter(configs))
    agent = PlannerAgent(
        model=default,
        cfg=configs[default],
        prompt_builder_enabled=False,
        contract_enabled=False,
    )
    result = agent.run(_make_planner_input(task_type="email"))
    assert "email" in result.base_prompt.lower() or len(result.base_prompt) > 100
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_planner_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.planner_agent'`

- [ ] **Step 3: Create `agent/agents/planner_agent.py`**

```python
# agent/agents/planner_agent.py
from __future__ import annotations

import os

from agent.contracts import ExecutionPlan, PlannerInput
from agent.prompt import build_system_prompt

_PROMPT_BUILDER_MAX_TOKENS = int(os.getenv("PROMPT_BUILDER_MAX_TOKENS", "500"))
_CONTRACT_MAX_ROUNDS = int(os.getenv("CONTRACT_MAX_ROUNDS", "3"))


class PlannerAgent:
    def __init__(
        self,
        model: str,
        cfg: dict,
        prompt_builder_enabled: bool | None = None,
        contract_enabled: bool | None = None,
    ) -> None:
        self._model = model
        self._cfg = cfg
        self._builder = (os.getenv("PROMPT_BUILDER_ENABLED", "1") == "1"
                         if prompt_builder_enabled is None else prompt_builder_enabled)
        self._contract = (os.getenv("CONTRACT_ENABLED", "0") == "1"
                          if contract_enabled is None else contract_enabled)

    def run(self, inp: PlannerInput) -> ExecutionPlan:
        task_type = inp.classification.task_type
        task_text = inp.task_input.task_text

        # 1. Base system prompt
        base_prompt = build_system_prompt(task_type)

        # 2. Inject knowledge graph section
        if inp.wiki_context.graph_section:
            base_prompt = base_prompt + "\n\n" + inp.wiki_context.graph_section

        # 3. Dynamic addendum (DSPy prompt builder)
        addendum = ""
        builder_in = builder_out = 0
        if self._builder:
            try:
                from agent.prompt_builder import build_dynamic_addendum
                addendum, builder_in, builder_out = build_dynamic_addendum(
                    task_text=task_text,
                    task_type=task_type,
                    model=self._model,
                    cfg=self._cfg,
                    max_tokens=_PROMPT_BUILDER_MAX_TOKENS,
                    graph_context=inp.wiki_context.graph_section,
                )
            except Exception as exc:
                print(f"[planner] prompt_builder failed ({exc})")

        # Inject addendum into prompt
        if addendum:
            base_prompt = base_prompt + "\n\n## TASK-SPECIFIC GUIDANCE\n" + addendum

        # Update prephase log to use final prompt
        if inp.prephase.log:
            inp.prephase.log[0]["content"] = base_prompt
        if inp.prephase.preserve_prefix:
            inp.prephase.preserve_prefix[0]["content"] = base_prompt

        # 4. Contract negotiation (optional)
        contract = None
        contract_in = contract_out = 0
        if self._contract:
            try:
                from agent.contract_phase import negotiate_contract
                contract, contract_in, contract_out, _rounds = negotiate_contract(
                    task_text=task_text,
                    task_type=task_type,
                    agents_md=inp.prephase.agents_md_content or "",
                    wiki_context=inp.wiki_context.patterns_text,
                    graph_context=inp.wiki_context.graph_section,
                    vault_date_hint=inp.prephase.vault_date_est or "",
                    vault_tree=inp.prephase.vault_tree_text or "",
                    model=self._model,
                    cfg=self._cfg,
                    max_rounds=_CONTRACT_MAX_ROUNDS,
                )
            except Exception as exc:
                print(f"[planner] contract negotiation failed ({exc})")

        return ExecutionPlan(
            base_prompt=base_prompt,
            addendum=addendum,
            contract=contract,
            route="EXECUTE",
            in_tokens=builder_in + contract_in,
            out_tokens=builder_out + contract_out,
        )
```

Note: The `route` field is always `"EXECUTE"` from PlannerAgent. The actual routing decision (`_route_task` / `DENY_SECURITY` / `CLARIFY`) happens inside `run_loop` at the start of the loop. Extracting that to PlannerAgent is done in Task 9.

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_planner_agent.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add agent/agents/planner_agent.py tests/agents/test_planner_agent.py
git commit -m "feat(agents): add PlannerAgent wrapper"
```

---

## Task 9: ExecutorAgent + loop.py DI

**Files:**
- Create: `agent/agents/executor_agent.py`
- Modify: `agent/loop.py` — add DI params, expose `_INJECTION_RE` from `agent.security`
- Create: `tests/agents/test_executor_agent.py`

- [ ] **Step 1: Check where `_INJECTION_RE` lives**

```bash
uv run python -c "from agent.loop import _INJECTION_RE; print('loop')" 2>/dev/null || \
uv run python -c "from agent.security import _INJECTION_RE; print('security')"
```

If it's in `agent.loop`, add it to `agent/security.py`:

```python
# In agent/security.py, add near the top with the other regexes:
import re as _re
_INJECTION_RE = _re.compile(
    r"(ignore (previous|all) instructions?|system (override|prompt)|"
    r"you are now|forget (your|the) rules|new (role|persona|instructions)|"
    r"disregard (your|all)|pretend (you are|to be)|act as (an? )?(ai|gpt|llm)|"
    r"(admin|developer|root) (mode|access|override))",
    _re.IGNORECASE,
)
```

Then update `agent/loop.py` to import from `agent.security` instead of defining locally:

```python
# In agent/loop.py, replace the local _INJECTION_RE definition with:
from .security import _INJECTION_RE
```

Run existing security tests to confirm nothing broke:
```bash
uv run pytest tests/test_security_gates.py -v
```

- [ ] **Step 2: Write the failing test**

```python
# tests/agents/test_executor_agent.py
import pytest


def test_executor_agent_imports():
    from agent.agents.executor_agent import ExecutorAgent
    from agent.agents.security_agent import SecurityAgent
    from agent.agents.stall_agent import StallAgent
    from agent.agents.compaction_agent import CompactionAgent
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.agents.verifier_agent import VerifierAgent
    agent = ExecutorAgent(
        security=SecurityAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        step_guard=StepGuardAgent(),
        verifier=VerifierAgent(enabled=False),
    )
    assert agent is not None


def test_executor_agent_accepts_executor_input():
    from agent.agents.executor_agent import ExecutorAgent
    from agent.agents.security_agent import SecurityAgent
    from agent.agents.stall_agent import StallAgent
    from agent.agents.compaction_agent import CompactionAgent
    from agent.agents.step_guard_agent import StepGuardAgent
    from agent.agents.verifier_agent import VerifierAgent
    from agent.contracts import (
        ExecutorInput, TaskInput, ExecutionPlan, WikiContext
    )
    from agent.prephase import PrephaseResult
    # Verify ExecutorInput is accepted without type errors
    pre = PrephaseResult(
        log=[{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}],
        preserve_prefix=[{"role": "system", "content": "sys"}],
    )
    inp = ExecutorInput(
        task_input=TaskInput(
            task_text="test",
            harness_url="http://localhost",
            trial_id="t01",
        ),
        plan=ExecutionPlan(
            base_prompt="sys",
            addendum="",
            contract=None,
            route="EXECUTE",
            in_tokens=0,
            out_tokens=0,
        ),
        wiki_context=WikiContext(patterns_text="", graph_section="", injected_node_ids=[]),
        prephase=pre,
        evaluator_model="test-model",
        evaluator_cfg={},
    )
    assert inp.plan.route == "EXECUTE"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_executor_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.agents.executor_agent'`

- [ ] **Step 4: Create `agent/agents/executor_agent.py`**

`run_loop` real signature (from `agent/loop.py:2413`):
```
run_loop(vm, model, _task_text, pre, cfg, task_type="default",
         evaluator_model="", evaluator_cfg=None, max_steps=None, contract=None) → dict
```
DI params `_security_agent`, etc. are added to this signature in Step 5.

```python
# agent/agents/executor_agent.py
from __future__ import annotations

from agent.agents.compaction_agent import CompactionAgent
from agent.agents.security_agent import SecurityAgent
from agent.agents.stall_agent import StallAgent
from agent.agents.step_guard_agent import StepGuardAgent
from agent.agents.verifier_agent import VerifierAgent
from agent.contracts import ExecutionResult, ExecutorInput


class ExecutorAgent:
    def __init__(
        self,
        security: SecurityAgent,
        stall: StallAgent,
        compaction: CompactionAgent,
        step_guard: StepGuardAgent,
        verifier: VerifierAgent,
    ) -> None:
        self._security = security
        self._stall = stall
        self._compaction = compaction
        self._step_guard = step_guard
        self._verifier = verifier

    def run(self, inp: ExecutorInput) -> ExecutionResult:
        from bitgn.vm.pcm_connect import PcmRuntimeClientSync
        from agent.loop import run_loop

        # Create vm from harness_url (ExecutorAgent owns the connection for its run)
        vm = PcmRuntimeClientSync(inp.harness_url)

        stats = run_loop(
            vm,
            inp.plan.base_prompt,   # model string — corrected below
            inp.task_input.task_text,
            inp.prephase,
            {},                     # cfg — corrected below
            task_type=inp.task_type,
            evaluator_model=inp.evaluator_model,
            evaluator_cfg=inp.evaluator_cfg,
            contract=inp.plan.contract,
            # DI agents (added to run_loop signature in Step 5)
            _security_agent=self._security,
            _stall_agent=self._stall,
            _compaction_agent=self._compaction,
            _step_guard_agent=self._step_guard,
            _verifier_agent=self._verifier,
        )
        return ExecutionResult(
            status=_status_from_outcome(stats.get("outcome", "")),
            outcome=stats.get("outcome", ""),
            token_stats={k: v for k, v in stats.items() if "tok" in k},
            step_facts=stats.get("step_facts", []),
            injected_node_ids=stats.get("graph_injected_node_ids", []),
            rejection_count=stats.get("eval_rejection_count", 0),
        )
```

**Important:** `run_loop`'s second argument is `model: str`, not `base_prompt`. The base_prompt is already injected into `pre.log[0]["content"]` by PlannerAgent. The ExecutorAgent must pass `model` and `cfg` from `inp` — add these two fields to `ExecutorInput` in Task 0's contracts:

```python
# In agent/contracts/__init__.py, update ExecutorInput:
class ExecutorInput(BaseModel):
    task_input: TaskInput
    plan: ExecutionPlan
    wiki_context: WikiContext
    prephase: PrephaseResult
    harness_url: str
    task_type: str
    model: str           # ← add this
    model_cfg: dict      # ← add this
    evaluator_model: str
    evaluator_cfg: dict
    model_config = {"arbitrary_types_allowed": True}
```

And update `executor_agent.py` accordingly:
```python
stats = run_loop(
    vm,
    inp.model,         # ← use inp.model
    inp.task_input.task_text,
    inp.prephase,
    inp.model_cfg,     # ← use inp.model_cfg
    task_type=inp.task_type,
    ...
)
```

Update the failing test in Step 2 to match the updated ExecutorInput fields.

```python
def _status_from_outcome(outcome: str) -> str:
    if outcome == "OUTCOME_OK":
        return "completed"
    if outcome == "OUTCOME_DENIED_SECURITY":
        return "denied"
    if outcome == "OUTCOME_ERR_INTERNAL":
        return "error"
    return "error"
```

Note: `run_loop` must be updated to accept `_security_agent`, `_stall_agent`, `_compaction_agent`, `_step_guard_agent`, `_verifier_agent` as optional kwargs. Step 5 covers this.

- [ ] **Step 5: Add DI parameters to `agent/loop.py`**

Find the `run_loop` function signature:
```bash
grep -n "^def run_loop" agent/loop.py
```

Add agent parameters at the end of the signature (all default to None for backward compatibility):

```python
def run_loop(
    vm,
    model: str,
    task_text: str,
    pre,
    cfg: dict,
    *,
    task_type: str | None = None,
    evaluator_model: str | None = None,
    evaluator_cfg: dict | None = None,
    contract=None,
    # DI agents — None means use direct imports (backward-compatible)
    _security_agent=None,
    _stall_agent=None,
    _compaction_agent=None,
    _step_guard_agent=None,
    _verifier_agent=None,
) -> dict:
```

Then, in the loop body, replace the direct calls with agent calls when agent is provided. For example:

Find `_check_write_scope(` in loop.py:
```bash
grep -n "_check_write_scope\|_handle_stall_retry\|_compact_log\|evaluate_completion\|check_step" agent/loop.py | head -30
```

For each call, add a conditional:

```python
# Example: replacing _check_write_scope
if _security_agent is not None:
    from agent.contracts import SecurityRequest
    _sc = _security_agent.check_write_scope(SecurityRequest(
        tool_name=action_name,
        tool_args=job.function.model_dump() if hasattr(job.function, "model_dump") else {},
        task_type=task_type or "",
    ))
    if not _sc.passed:
        _result_txt = _sc.detail or "Scope violation"
        # continue with error handling as before
else:
    _scope_err = _check_write_scope(job.function, action_name, task_type)
    # existing handling
```

This is the most complex step. Make surgical changes — don't rewrite the loop logic.

- [ ] **Step 6: Run all existing tests to verify nothing broke**

```bash
uv run pytest tests/ -v --ignore=tests/agents -x
```
Expected: All existing tests pass (or the same failures as before this task)

- [ ] **Step 7: Run new executor tests**

```bash
uv run pytest tests/agents/test_executor_agent.py -v
```
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add agent/agents/executor_agent.py agent/loop.py agent/security.py \
        tests/agents/test_executor_agent.py
git commit -m "feat(agents): add ExecutorAgent with DI params in run_loop"
```

---

## Task 10: Orchestrator

**Files:**
- Create: `agent/orchestrator.py`
- Modify: `agent/__init__.py`
- Create: `tests/agents/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_orchestrator.py


def test_orchestrator_imports():
    from agent.orchestrator import run_agent
    assert callable(run_agent)


def test_orchestrator_signature():
    import inspect
    from agent.orchestrator import run_agent
    sig = inspect.signature(run_agent)
    params = list(sig.parameters)
    # Must accept same args as the old run_agent in __init__.py
    assert "router" in params
    assert "harness_url" in params
    assert "task_text" in params


def test_write_wiki_fragment_importable():
    from agent.orchestrator import write_wiki_fragment
    assert callable(write_wiki_fragment)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/agents/test_orchestrator.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent.orchestrator'`

- [ ] **Step 3: Create `agent/orchestrator.py`**

```python
# agent/orchestrator.py
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from bitgn.vm.pcm_connect import PcmRuntimeClientSync

from agent.agents.classifier_agent import ClassifierAgent
from agent.agents.compaction_agent import CompactionAgent
from agent.agents.executor_agent import ExecutorAgent
from agent.agents.planner_agent import PlannerAgent
from agent.agents.security_agent import SecurityAgent
from agent.agents.stall_agent import StallAgent
from agent.agents.step_guard_agent import StepGuardAgent
from agent.agents.verifier_agent import VerifierAgent
from agent.agents.wiki_graph_agent import WikiGraphAgent
from agent.classifier import ModelRouter, TASK_PREJECT
from agent.contracts import (
    ExecutorInput, PlannerInput, TaskInput, WikiReadRequest
)
from agent.loop import run_loop
from agent.prephase import run_prephase
from agent.prompt import build_system_prompt
from agent.wiki import format_fragment, write_fragment


def run_agent(router: ModelRouter, harness_url: str, task_text: str) -> dict:
    """Execute a single PAC1 benchmark task. Drop-in replacement for agent.__init__.run_agent."""
    task_input = TaskInput(
        task_text=task_text,
        harness_url=harness_url,
        trial_id="",
    )
    vm = PcmRuntimeClientSync(harness_url)

    # 1. Prephase — needed for vault hints before classification
    pre = run_prephase(vm, task_text, "")

    # 2. Classification (uses vault hints from prephase)
    classification = ClassifierAgent(router=router).run(task_input, prephase=pre)

    # 3. PREJECT early exit (preserve existing behavior)
    if classification.task_type == TASK_PREJECT:
        pre.log[0]["content"] = build_system_prompt(TASK_PREJECT)
        pre.preserve_prefix[0]["content"] = pre.log[0]["content"]
        evaluator_model = router.evaluator or classification.model
        evaluator_cfg = router._adapt_config(
            router.configs.get(evaluator_model, {}), "evaluator"
        )
        stats = run_loop(vm, classification.model, task_text, pre,
                         classification.model_cfg, task_type=TASK_PREJECT,
                         evaluator_model=evaluator_model, evaluator_cfg=evaluator_cfg)
        stats.update({
            "model_used": classification.model, "task_type": TASK_PREJECT,
            "builder_used": False, "builder_in_tok": 0,
            "builder_out_tok": 0, "builder_addendum": "",
        })
        return stats

    # 4. Parallel: wiki read (prephase already done)
    wiki_agent = WikiGraphAgent()
    wiki_context = wiki_agent.read(WikiReadRequest(
        task_type=classification.task_type,
        task_text=task_text,
    ))

    # Inject wiki patterns into prephase log (preserve existing behavior)
    if wiki_context.patterns_text:
        for i in range(len(pre.preserve_prefix) - 1, -1, -1):
            if pre.preserve_prefix[i].get("role") == "user":
                pre.preserve_prefix[i]["content"] += f"\n\n{wiki_context.patterns_text}"
                pre.log[i]["content"] = pre.preserve_prefix[i]["content"]
                break

    # 5. Plan
    evaluator_model = router.evaluator or classification.model
    evaluator_cfg = router._adapt_config(
        router.configs.get(evaluator_model, {}), "evaluator"
    )
    builder_model = router.prompt_builder or router.classifier or classification.model
    builder_cfg = router._adapt_config(router.configs.get(builder_model, {}), "classifier")

    planner = PlannerAgent(
        model=builder_model,
        cfg=builder_cfg,
    )
    plan = planner.run(PlannerInput(
        task_input=task_input,
        classification=classification,
        wiki_context=wiki_context,
        prephase=pre,
    ))

    # 6. Execute
    executor = ExecutorAgent(
        security=SecurityAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        step_guard=StepGuardAgent(),
        verifier=VerifierAgent(),
    )
    result = executor.run(ExecutorInput(
        task_input=task_input,
        plan=plan,
        wiki_context=wiki_context,
        prephase=pre,
        harness_url=harness_url,
        task_type=classification.task_type,
        model=classification.model,
        model_cfg=classification.model_cfg,
        evaluator_model=evaluator_model,
        evaluator_cfg=evaluator_cfg,
    ))

    # 7. Wiki graph feedback
    from agent.contracts import WikiFeedbackRequest
    wiki_agent.write_feedback(WikiFeedbackRequest(
        task_type=classification.task_type,
        task_text=task_text,
        execution_result=result,
        wiki_context=wiki_context,
        score=1.0 if result.status == "completed" else 0.0,
    ))

    # Return stats dict compatible with main.py expectations
    return {
        **result.token_stats,
        "model_used": classification.model,
        "task_type": classification.task_type,
        "builder_used": bool(plan.addendum),
        "builder_in_tok": plan.in_tokens,
        "builder_out_tok": plan.out_tokens,
        "builder_addendum": plan.addendum,
        "graph_injected_node_ids": result.injected_node_ids,
        "graph_context": wiki_context.graph_section,
        "contract_rounds_taken": getattr(plan.contract, "rounds_taken", 0) if plan.contract else 0,
        "contract_is_default": getattr(plan.contract, "is_default", True) if plan.contract else True,
        "contract_in_tok": 0,
        "contract_out_tok": 0,
        "outcome": result.outcome,
        "step_facts": result.step_facts,
        "eval_rejection_count": result.rejection_count,
    }


def write_wiki_fragment(
    task_text: str,
    task_type: str,
    stats: dict,
    task_id: str,
    score: float,
) -> None:
    """Preserve write_wiki_fragment for main.py (unchanged behavior)."""
    outcome = stats.get("outcome", "")
    try:
        task_id = task_id or task_text[:20].replace(" ", "_")
        fragments = format_fragment(
            outcome=outcome,
            task_type=task_type,
            task_id=task_id,
            task_text=task_text,
            step_facts=stats.get("step_facts", []),
            done_ops=stats.get("done_ops", []),
            stall_hints=stats.get("stall_hints", []),
            eval_last_call=stats.get("eval_last_call"),
            score=score,
        )
        for content, category in fragments:
            if content and category:
                write_fragment(task_id, category, content)
    except Exception as e:
        print(f"[wiki] fragment write failed: {e}")
```

- [ ] **Step 4: Update `agent/__init__.py` to re-export from orchestrator**

```python
# agent/__init__.py
# Pipeline delegated to orchestrator. Kept for backward compatibility.
from .orchestrator import run_agent, write_wiki_fragment  # noqa: F401
```

- [ ] **Step 5: Run orchestrator tests**

```bash
uv run pytest tests/agents/test_orchestrator.py -v
```
Expected: 3 passed

- [ ] **Step 6: Run full test suite to verify nothing broke**

```bash
uv run pytest tests/ -v -x
```
Expected: All tests that passed before Task 9 still pass.

- [ ] **Step 7: Smoke test: verify `main.py` can import `run_agent`**

```bash
uv run python -c "from agent import run_agent; print('ok')"
```
Expected: `ok`

- [ ] **Step 8: Commit**

```bash
git add agent/orchestrator.py agent/__init__.py tests/agents/test_orchestrator.py
git commit -m "feat(agents): add Orchestrator — complete multi-agent Hub-and-Spoke refactor"
```

---

## Self-Review Checklist

After all tasks are complete:

```bash
# Verify all agent modules exist
ls agent/agents/

# Verify contracts module imports cleanly
uv run python -c "from agent.contracts import TaskInput, ExecutionResult; print('contracts ok')"

# Verify agents can be imported
uv run python -c "
from agent.agents.security_agent import SecurityAgent
from agent.agents.stall_agent import StallAgent
from agent.agents.compaction_agent import CompactionAgent
from agent.agents.step_guard_agent import StepGuardAgent
from agent.agents.classifier_agent import ClassifierAgent
from agent.agents.wiki_graph_agent import WikiGraphAgent
from agent.agents.verifier_agent import VerifierAgent
from agent.agents.planner_agent import PlannerAgent
from agent.agents.executor_agent import ExecutorAgent
from agent.orchestrator import run_agent
print('all agents ok')
"

# Verify main.py interface unchanged
uv run python -c "from agent import run_agent, write_wiki_fragment; print('__init__ ok')"

# Full test suite
uv run pytest tests/ -v
```
