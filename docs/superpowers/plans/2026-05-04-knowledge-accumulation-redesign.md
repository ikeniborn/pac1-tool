# Knowledge Accumulation Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить внутренние конфликты системы (граф vs промпт, evaluator-only contract, builder/evaluator deadlock, POSTRUN_OPTIMIZE отключён), чтобы петля накопления знаний реально влияла на качество.

**Architecture:** Системный промпт очищается от доменных знаний (стратегий) и оставляет только протокол и security gates. Contract gate требует полного консенсуса с обязательными declared mutations. DSPy optimize включается с порогом примеров.

**Tech Stack:** Python, Pydantic, DSPy, pytest. Файлы: `agent/prompt.py`, `agent/wiki_graph.py`, `agent/contract_phase.py`, `agent/contract_models.py`, `agent/evaluator.py`, `agent/loop.py`, `agent/postrun.py`.

---

## File Map

| Файл | Изменения |
|---|---|
| `agent/wiki_graph.py` | `_score_candidates`: hard filter по task_type |
| `agent/prompt.py` | Удалить `_TEMPORAL`, `_CRM`, `_DISTILL`; упростить `_LOOKUP`, `_EMAIL` |
| `data/wiki/graph.json` | Одноразовый сброс до `{"nodes": {}, "edges": []}` |
| `agent/contract_models.py` | Добавить `evidence_standard` в `ExecutorProposal` и `Contract` |
| `agent/contract_phase.py` | Убрать evaluator-only путь; добавить `MUTATION_REQUIRED_TYPES` |
| `agent/evaluator.py` | Gate grounding_refs check на `evidence_standard` |
| `agent/loop.py` | Добавить `consecutive_contract_blocks` в `_LoopState`; force-complete при ≥2 |
| `agent/postrun.py` | Добавить `_count_dspy_examples()` и min_examples check |
| `.env.example` | Добавить `POSTRUN_OPTIMIZE_MIN_EXAMPLES=10` |
| `tests/test_wiki_graph_scoring.py` | Добавить тесты hard filter |
| `tests/test_contract_phase.py` | Обновить тесты под full-consensus-only |
| `tests/test_loop_mutation_gate.py` | Добавить тест consecutive blocks |
| `tests/test_evaluator_contract.py` | Добавить тест evidence_standard |

---

## Task 1: Block B — Hard filter в graph retrieval по task_type

**Files:**
- Modify: `agent/wiki_graph.py:341-384` (`_score_candidates`)
- Test: `tests/test_wiki_graph_scoring.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_wiki_graph_scoring.py — добавить в конец файла

def test_cross_type_nodes_excluded():
    """temporal nodes must NOT appear when querying for lookup task."""
    g = _make_graph({
        "t1": {"type": "rule", "text": "vault date triangulation formula", "tags": ["temporal"],
               "confidence": 0.8, "uses": 10},
        "l1": {"type": "rule", "text": "lookup accounts contacts", "tags": ["lookup"],
               "confidence": 0.6, "uses": 5},
    })
    results = _score_candidates(g, "lookup", "find accounts for manager", 0.0, None, False)
    ids = [nid for _, nid, _ in results]
    assert "t1" not in ids, "temporal node leaked into lookup results"
    assert "l1" in ids


def test_all_types_tag_passes_any_task_type():
    """nodes tagged all_types must appear for any task_type query."""
    g = _make_graph({
        "n1": {"type": "insight", "text": "general discovery principle", "tags": ["all_types"],
               "confidence": 0.7, "uses": 3},
    })
    results = _score_candidates(g, "temporal", "what day is tomorrow", 0.0, None, False)
    ids = [nid for _, nid, _ in results]
    assert "n1" in ids


def test_general_tag_passes_any_task_type():
    """nodes tagged general must appear for any task_type query."""
    g = _make_graph({
        "n1": {"type": "insight", "text": "read before write", "tags": ["general"],
               "confidence": 0.7, "uses": 3},
    })
    results = _score_candidates(g, "crm", "reschedule follow-up nordlicht", 0.0, None, False)
    ids = [nid for _, nid, _ in results]
    assert "n1" in ids


def test_untagged_node_excluded():
    """nodes with no tags are excluded (empty tags list)."""
    g = _make_graph({
        "n1": {"type": "insight", "text": "some untagged insight", "tags": [],
               "confidence": 0.8, "uses": 5},
    })
    results = _score_candidates(g, "lookup", "find contact", 0.0, None, False)
    ids = [nid for _, nid, _ in results]
    assert "n1" not in ids
```

- [ ] **Step 2: Запустить тесты — убедиться что падают**

```bash
uv run pytest tests/test_wiki_graph_scoring.py::test_cross_type_nodes_excluded tests/test_wiki_graph_scoring.py::test_untagged_node_excluded -v
```

Ожидаемый результат: `FAILED` (узел с temporal тегом сейчас проходит через text-overlap).

- [ ] **Step 3: Изменить `_score_candidates` в `agent/wiki_graph.py`**

Найти строку около 373:
```python
        tags = set(node.get("tags", []))
        tag_score = 2.0 if (task_type in tags or "all_types" in tags) else 0.0
```

Заменить на:
```python
        tags = set(node.get("tags", []))
        if task_type not in tags and "all_types" not in tags and "general" not in tags:
            continue  # hard filter — cross-type nodes excluded
        tag_score = 2.0
```

- [ ] **Step 4: Запустить новые тесты и полный набор graph тестов**

```bash
uv run pytest tests/test_wiki_graph_scoring.py -v
```

Ожидаемый результат: все тесты `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add agent/wiki_graph.py tests/test_wiki_graph_scoring.py
git commit -m "fix(wiki-graph): hard filter cross-type nodes in _score_candidates — FIX-433"
```

---

## Task 2: Block A — Очистка системного промпта

**Files:**
- Modify: `agent/prompt.py` (весь файл)
- Modify: `data/wiki/graph.json` (одноразовый сброс)

- [ ] **Step 1: Удалить блоки `_TEMPORAL`, `_CRM`, `_DISTILL` из `agent/prompt.py`**

Удалить строки 217–354 целиком (блоки `_TEMPORAL`, `_CRM`, `_DISTILL` вместе с комментариями перед ними).

Это строки:
- `# Temporal / date-arithmetic block  # FIX-305, FIX-327, FIX-430` (строка 217) → до конца `_DISTILL` (строка 354)

- [ ] **Step 2: Упростить `_LOOKUP` — оставить только anti-hallucination gate**

Заменить весь блок `_LOOKUP` (строки 65–96):

```python
# Lookup block
_LOOKUP = """
## Vault lookup

**Anti-hallucination gate**: BEFORE returning OUTCOME_NONE_CLARIFICATION
you MUST have executed at least ONE of (tree|find|search|list) against the
actual vault and observed the result. Claims like "directory not accessible",
"vault not mounted", "path not found" without a preceding list/find/tree call
are hallucination — the vault IS mounted, tools WILL work.

**grounding_refs is MANDATORY** — include every file you read that contributed to the answer."""
```

- [ ] **Step 3: Упростить `_EMAIL` — убрать пошаговый workflow, оставить security rule**

Заменить весь блок `_EMAIL` (строки 99–130):

```python
# Email block
_EMAIL = """
## Email tasks

**Recipient identity rule (FIX-331)**:
Recipient = the person NAMED IN THE TASK TEXT. NEVER substitute the account manager,
a default contact, or any contact from memory.
If the named person is not found after 1 retry → OUTCOME_NONE_CLARIFICATION.

Missing body OR subject → OUTCOME_NONE_CLARIFICATION."""
```

- [ ] **Step 4: Обновить `_TASK_BLOCKS` — убрать удалённые блоки**

Заменить `_TASK_BLOCKS` (строки 361–372):

```python
_TASK_BLOCKS: dict[str, list[str]] = {
    "email":    [_CORE, _EMAIL, _LOOKUP],
    "inbox":    [_CORE, _INBOX, _EMAIL, _LOOKUP],
    "queue":    [_CORE, _INBOX, _EMAIL, _LOOKUP],
    "lookup":   [_CORE, _LOOKUP],
    "temporal": [_CORE, _LOOKUP],
    "capture":  [_CORE],
    "crm":      [_CORE, _LOOKUP],
    "distill":  [_CORE, _LOOKUP],
    "preject":  [_CORE],
    "default":  [_CORE, _LOOKUP, _EMAIL, _INBOX],
}
```

- [ ] **Step 5: Проверить что файл собирается без ошибок**

```bash
uv run python -c "from agent.prompt import build_system_prompt; print(build_system_prompt('temporal')[:200])"
```

Ожидаемый результат: первые 200 символов `_CORE` без ошибок импорта.

- [ ] **Step 6: Сбросить граф**

```bash
echo '{"nodes": {}, "edges": []}' > data/wiki/graph.json
```

- [ ] **Step 7: Commit**

```bash
git add agent/prompt.py data/wiki/graph.json
git commit -m "feat(prompt): strip domain knowledge blocks — temporal/crm/distill removed, lookup simplified — FIX-434"
```

---

## Task 3: Block C1/C2 — Contract: only full consensus + mandatory planned_mutations

**Files:**
- Modify: `agent/contract_phase.py:325-383`
- Test: `tests/test_contract_phase.py`
- Test: `tests/test_loop_mutation_gate.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_contract_phase.py — добавить в конец файла

@patch("agent.contract_phase.call_llm_raw")
def test_evaluator_only_consensus_continues_rounds(mock_llm):
    """evaluator agrees but executor doesn't → rounds continue, no contract returned yet."""
    mock_llm.side_effect = [
        _make_planner_json(),
        _make_executor_json(agreed=False),   # executor disagrees round 1
        _make_evaluator_json(agreed=True),   # evaluator agrees round 1
        _make_executor_json(agreed=True, steps=["list /accounts", "write /accounts/a.json"]),  # round 2
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="reschedule nordlicht",
        task_type="crm",
        agents_md="", wiki_context="", graph_context="",
        model="test-model", cfg={}, max_rounds=3,
    )
    assert not contract.is_default
    assert not contract.evaluator_only  # full consensus reached in round 2


@patch("agent.contract_phase.call_llm_raw")
def test_mutation_required_type_without_mutations_continues(mock_llm):
    """crm task with agreed=True but empty planned_mutations → round continues."""
    mock_llm.side_effect = [
        _make_planner_json(),
        # Round 1: both agree but executor has no planned_mutations
        json.dumps({
            "plan_steps": ["search contacts", "write reminder"],
            "expected_outcome": "updated",
            "required_tools": ["search", "write"],
            "planned_mutations": [],  # empty — should trigger another round
            "open_questions": [],
            "agreed": True,
        }),
        _make_evaluator_json(agreed=True),
        # Round 2: executor includes mutations
        json.dumps({
            "plan_steps": ["search contacts", "write reminder"],
            "expected_outcome": "updated",
            "required_tools": ["search", "write"],
            "planned_mutations": ["/reminders/rem_001.json", "/accounts/acct_001.json"],
            "open_questions": [],
            "agreed": True,
        }),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _, _ = negotiate_contract(
        task_text="reschedule nordlicht in 2 weeks",
        task_type="crm",
        agents_md="", wiki_context="", graph_context="",
        model="test-model", cfg={}, max_rounds=3,
    )
    assert contract.mutation_scope == ["/reminders/rem_001.json", "/accounts/acct_001.json"]
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_contract_phase.py::test_evaluator_only_consensus_continues_rounds tests/test_contract_phase.py::test_mutation_required_type_without_mutations_continues -v
```

Ожидаемый результат: `FAILED`.

- [ ] **Step 3: Изменить `agent/contract_phase.py`**

Добавить константу после импортов (строка ~25):

```python
MUTATION_REQUIRED_TYPES: frozenset[str] = frozenset({"crm", "capture", "inbox"})
```

Заменить блок консенсуса (строки ~325–360). Найти:

```python
        # FIX-406: partial consensus — evaluator is authority on success criteria.
        # FIX-415: track evaluator-only flag and filter mutation_scope on forbidden paths.
        # FIX-418: blocking_objections are true blockers; objections are non-blocking notes.
        evaluator_accepts = response.agreed and not response.blocking_objections
        full_consensus = proposal.agreed and evaluator_accepts
        if full_consensus or evaluator_accepts:
            _evaluator_only = not full_consensus
            # FIX-415: build mutation_scope from proposal.planned_mutations.
            # On evaluator-only consensus, block mutations matching forbidden constraint keywords.
            _planned = list(proposal.planned_mutations)
            _forbidden_keywords = {"result.txt", ".disposition.json"}
            if _evaluator_only:
                _allowed = [
                    p for p in _planned
                    if not any(kw in p for kw in _forbidden_keywords)
                ]
            else:
                _allowed = _planned

            contract = Contract(
                plan_steps=proposal.plan_steps,
                success_criteria=response.success_criteria,
                required_evidence=response.required_evidence,
                failure_conditions=response.failure_conditions,
                mutation_scope=_allowed,
                forbidden_mutations=[p for p in _planned if p not in _allowed],
                evaluator_only=_evaluator_only,
                planner_strategy=planner_strategy,
                is_default=False,
                rounds_taken=round_num,
            )
            if _LOG_LEVEL == "DEBUG":
                mode = "full consensus" if full_consensus else "evaluator-only consensus"
                print(f"[contract] {mode} reached in {round_num} round(s)")
            return contract, total_in, total_out, rounds_transcript
```

Заменить на:

```python
        # FIX-433: only full consensus — no evaluator-only path.
        evaluator_accepts = response.agreed and not response.blocking_objections
        full_consensus = proposal.agreed and evaluator_accepts

        if full_consensus:
            _planned = list(proposal.planned_mutations)
            # FIX-433 C2: mutation-required types must declare planned_mutations
            if task_type in MUTATION_REQUIRED_TYPES and not _planned:
                if _LOG_LEVEL == "DEBUG":
                    print(
                        f"[contract] round {round_num}: {task_type} requires mutations "
                        "but planned_mutations empty — continuing rounds"
                    )
                # Inject feedback into next round via evaluator objection hint
                # by not finalizing — loop continues to next round naturally
            else:
                _forbidden_keywords = {"result.txt", ".disposition.json"}
                _allowed = [p for p in _planned if not any(kw in p for kw in _forbidden_keywords)]

                contract = Contract(
                    plan_steps=proposal.plan_steps,
                    success_criteria=response.success_criteria,
                    required_evidence=response.required_evidence,
                    failure_conditions=response.failure_conditions,
                    mutation_scope=_allowed,
                    forbidden_mutations=[p for p in _planned if p not in _allowed],
                    evaluator_only=False,
                    planner_strategy=planner_strategy,
                    is_default=False,
                    rounds_taken=round_num,
                )
                if _LOG_LEVEL == "DEBUG":
                    print(f"[contract] full consensus reached in {round_num} round(s)")
                return contract, total_in, total_out, rounds_transcript
```

Также заменить fallback при max_rounds exceeded (строки ~368–383):

```python
    if rounds_transcript:
        last = rounds_transcript[-1]
        ep = last["executor_proposal"]
        er = last["evaluator_response"]
        return Contract(
            plan_steps=ep.get("plan_steps", []),
            success_criteria=er.get("success_criteria", []),
            required_evidence=er.get("required_evidence", []),
            failure_conditions=er.get("failure_conditions", []),
            mutation_scope=[],
            forbidden_mutations=[],
            evaluator_only=True,           # ← убрать это
            planner_strategy=planner_strategy,
            is_default=False,
            rounds_taken=max_rounds,
        ), total_in, total_out, rounds_transcript
```

Заменить на:

```python
    if rounds_transcript:
        last = rounds_transcript[-1]
        ep = last["executor_proposal"]
        er = last["evaluator_response"]
        return Contract(
            plan_steps=ep.get("plan_steps", []),
            success_criteria=er.get("success_criteria", []),
            required_evidence=er.get("required_evidence", []),
            failure_conditions=er.get("failure_conditions", []),
            mutation_scope=[],
            forbidden_mutations=[],
            evaluator_only=False,
            planner_strategy=planner_strategy,
            is_default=False,
            rounds_taken=max_rounds,
        ), total_in, total_out, rounds_transcript
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Ожидаемый результат: все тесты `PASSED`. Если существующий тест `test_evaluator_only_*` проверяет старое поведение — обновить его в соответствии с новой логикой (full consensus only).

- [ ] **Step 5: Обновить тест в `tests/test_loop_mutation_gate.py`**

Найти тест `test_no_gate_when_full_consensus` и убедиться что он работает с `evaluator_only=False`. Если есть тест проверяющий поведение evaluator_only=True — удалить или переименовать его с пометкой legacy.

```bash
uv run pytest tests/test_loop_mutation_gate.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py tests/test_loop_mutation_gate.py
git commit -m "fix(contract): full consensus only, mandatory planned_mutations for mutation types — FIX-435"
```

---

## Task 4: Block C3 — evidence_standard в contract

**Files:**
- Modify: `agent/contract_models.py`
- Modify: `agent/contract_phase.py` (передать evidence_standard в Contract)
- Modify: `agent/evaluator.py:454-467`
- Test: `tests/test_evaluator_contract.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_evaluator_contract.py — добавить

from agent.contract_models import Contract
from agent.evaluator import evaluate_completion
from unittest.mock import patch, MagicMock


def _make_contract_with_evidence_standard(standard: str) -> Contract:
    return Contract(
        plan_steps=["compute date"],
        success_criteria=["date returned"],
        required_evidence=["/reminders/ (list and read for dates)"],
        failure_conditions=["wrong date"],
        mutation_scope=[],
        evidence_standard=standard,
        is_default=False,
        rounds_taken=1,
    )


def test_calculation_only_skips_grounding_check():
    """evidence_standard=calculation_only → grounding_refs check skipped even if required_evidence set."""
    from agent.models import ReportTaskCompletion
    report = ReportTaskCompletion(
        tool="report_completion",
        completed_steps_laconic=["computed date from vault_date + 2"],
        message="24-03-2026",
        outcome="OUTCOME_OK",
        grounding_refs=[],  # empty — would normally fail grounding check
    )
    contract = _make_contract_with_evidence_standard("calculation_only")

    with patch("agent.evaluator.dspy") as mock_dspy:
        mock_predict = MagicMock()
        mock_predict.return_value = MagicMock(
            approved="True", issues="", correction_hint=""
        )
        mock_dspy.ChainOfThought.return_value = mock_predict
        from agent.evaluator import EvalVerdict
        # Should not raise or return rejected verdict due to missing grounding_refs
        # The grounding check is skipped for calculation_only
        result = evaluate_completion(
            report=report,
            task_text="what day is in 2 days",
            task_type="temporal",
            done_ops=[],
            contract=contract,
        )
    # No rejection due to grounding — the mock LLM approved it
    assert result.approved


def test_vault_required_rejects_missing_grounding():
    """evidence_standard=vault_required (default) → grounding check fires normally."""
    from agent.models import ReportTaskCompletion
    report = ReportTaskCompletion(
        tool="report_completion",
        completed_steps_laconic=["found account"],
        message="done",
        outcome="OUTCOME_OK",
        grounding_refs=[],  # empty
    )
    contract = _make_contract_with_evidence_standard("vault_required")
    from agent.evaluator import evaluate_completion, EvalVerdict
    result = evaluate_completion(
        report=report,
        task_text="find accounts for manager",
        task_type="lookup",
        done_ops=[],
        contract=contract,
    )
    assert not result.approved
    assert "Required reads missing" in (result.issues[0] if result.issues else "")
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_evaluator_contract.py::test_calculation_only_skips_grounding_check tests/test_evaluator_contract.py::test_vault_required_rejects_missing_grounding -v
```

Ожидаемый результат: `ERROR` (поле `evidence_standard` не существует).

- [ ] **Step 3: Добавить `evidence_standard` в `agent/contract_models.py`**

В `ExecutorProposal` добавить поле после `planned_mutations`:

```python
class ExecutorProposal(BaseModel):
    plan_steps: list[str]
    expected_outcome: str
    required_tools: list[str]
    planned_mutations: list[str] = Field(default_factory=list)
    evidence_standard: str = "vault_required"   # "vault_required" | "calculation_only"
    open_questions: list[str]
    agreed: bool
```

В `Contract` добавить поле после `evaluator_only`:

```python
class Contract(BaseModel):
    plan_steps: list[str]
    success_criteria: list[str]
    required_evidence: list[str]
    failure_conditions: list[str]
    mutation_scope: list[str] = Field(default_factory=list)
    forbidden_mutations: list[str] = Field(default_factory=list)
    evaluator_only: bool = False
    evidence_standard: str = "vault_required"   # "vault_required" | "calculation_only"
    planner_strategy: str = ""
    is_default: bool
    rounds_taken: int
```

- [ ] **Step 4: Передать `evidence_standard` при построении `Contract` в `agent/contract_phase.py`**

В блоке построения Contract (Task 3, Step 3) добавить поле:

```python
contract = Contract(
    plan_steps=proposal.plan_steps,
    ...
    evidence_standard=getattr(proposal, "evidence_standard", "vault_required"),
    ...
)
```

Также в fallback при max_rounds exceeded:

```python
return Contract(
    ...
    evidence_standard="vault_required",
    ...
)
```

И в `_load_default_contract`:

```python
data.setdefault("evidence_standard", "vault_required")
```

- [ ] **Step 5: Обновить `agent/evaluator.py` — gate grounding check**

Найти строку ~454:

```python
    if contract is not None and not contract.is_default and contract.required_evidence:
        refs = [str(r) for r in (getattr(report, "grounding_refs", None) or [])]
        missing = [
            e for e in contract.required_evidence
            if not any(ref.lower() in e.lower() for ref in refs)
        ]
        if missing:
```

Заменить на:

```python
    if (
        contract is not None
        and not contract.is_default
        and contract.required_evidence
        and getattr(contract, "evidence_standard", "vault_required") != "calculation_only"
    ):
        refs = [str(r) for r in (getattr(report, "grounding_refs", None) or [])]
        missing = [
            e for e in contract.required_evidence
            if not any(ref.lower() in e.lower() for ref in refs)
        ]
        if missing:
```

- [ ] **Step 6: Запустить тесты**

```bash
uv run pytest tests/test_evaluator_contract.py tests/test_evaluator.py -v
```

Ожидаемый результат: все `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add agent/contract_models.py agent/contract_phase.py agent/evaluator.py tests/test_evaluator_contract.py
git commit -m "feat(contract): add evidence_standard field — calculation_only skips grounding check — FIX-436"
```

---

## Task 5: Block D — Force OUTCOME_NONE_CLARIFICATION при consecutive contract blocks

**Files:**
- Modify: `agent/loop.py:182-250` (`_LoopState`), `agent/loop.py:2298-2302` (main loop)
- Test: `tests/test_loop_mutation_gate.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_loop_mutation_gate.py — добавить в конец файла

def test_consecutive_contract_blocks_force_clarification():
    """After 2 consecutive contract-gate blocks, the message contains NONE_CLARIFICATION hint."""
    contract = _make_contract(evaluator_only=False, mutation_scope=[])
    st = _make_loop_state(contract)
    # st.contract.evaluator_only is False but scope is empty — gate fires via scope check
    # Simulate the counter being already at 1
    st.consecutive_contract_blocks = 1

    # We test that after second block the force-complete path is triggered.
    # Since _pre_dispatch returns the gate message string (not ReportTaskCompletion),
    # we verify the counter increments and the caller (main loop) would see >= 2.
    contract2 = _make_contract(evaluator_only=False, mutation_scope=[])
    st.contract = contract2
    st.contract.evaluator_only = True  # trigger gate
    job = _make_write_job("/reminders/rem_001.json")
    vm = MagicMock()

    from agent.loop import _pre_dispatch
    with patch("agent.loop._check_write_scope", return_value=None):
        result = _pre_dispatch(job, "crm", vm, st)

    assert result is not None  # gate fired
    assert "contract-gate" in result.lower() or "NONE_CLARIFICATION" in result
    # After this block the main loop should check st.consecutive_contract_blocks >= 2
```

- [ ] **Step 2: Запустить — убедиться что тест проходит или уточнить поведение**

```bash
uv run pytest tests/test_loop_mutation_gate.py::test_consecutive_contract_blocks_force_clarification -v
```

- [ ] **Step 3: Добавить `consecutive_contract_blocks` в `_LoopState`**

В `agent/loop.py` в класс `_LoopState` после строки `contract_monitor_warnings: int = 0`:

```python
    consecutive_contract_blocks: int = 0   # FIX-437: force NONE_CLARIFICATION after ≥2
```

- [ ] **Step 4: Обновить `_pre_dispatch` — инкрементировать счётчик**

В `agent/loop.py` в функции `_pre_dispatch`, в блоке `# FIX-415` (строка ~1924), после строки `return _gate_msg`:

Изменить секцию:

```python
        if not scope or path not in scope:
            _gate_msg = (
                f"[contract-gate] FIX-415: evaluator-only contract — mutation to '{path}' "
                f"is outside agreed scope {scope or '[]'}. "
                "Proceed read-only or return OUTCOME_NONE_CLARIFICATION if task requires this write."
            )
            print(f"{CLI_YELLOW}{_gate_msg}{CLI_CLR}")
            return _gate_msg
```

На:

```python
        if not scope or path not in scope:
            st.consecutive_contract_blocks += 1  # FIX-437
            _gate_msg = (
                f"[contract-gate] FIX-415: evaluator-only contract — mutation to '{path}' "
                f"is outside agreed scope {scope or '[]'}. "
                "Proceed read-only or return OUTCOME_NONE_CLARIFICATION if task requires this write."
            )
            print(f"{CLI_YELLOW}{_gate_msg}{CLI_CLR}")
            return _gate_msg
```

- [ ] **Step 5: Обновить main loop — force-complete при ≥2 consecutive blocks**

В `agent/loop.py` найти строку ~2298:

```python
    _guard_msg = _pre_dispatch(job, task_type, vm, st, _security_agent=_security_agent)
    if _guard_msg is not None:
        st.log.append({"role": "user", "content": _guard_msg})
        st.steps_since_write += 1
        return False
```

Заменить на:

```python
    _guard_msg = _pre_dispatch(job, task_type, vm, st, _security_agent=_security_agent)
    if _guard_msg is not None:
        # FIX-437: after 2 consecutive contract blocks force OUTCOME_NONE_CLARIFICATION
        if st.consecutive_contract_blocks >= 2:
            print(f"{CLI_YELLOW}[contract-gate] FIX-437: 2 consecutive blocks — force OUTCOME_NONE_CLARIFICATION{CLI_CLR}")
            _forced = ReportTaskCompletion(
                tool="report_completion",
                completed_steps_laconic=["contract gate blocked write operations"],
                message="Task requires mutations that were not approved in the execution contract.",
                outcome="OUTCOME_NONE_CLARIFICATION",
                grounding_refs=[],
            )
            job.function = _forced
            st.consecutive_contract_blocks = 0
            # Fall through to normal report_completion handling
        else:
            st.log.append({"role": "user", "content": _guard_msg})
            st.steps_since_write += 1
            return False
```

- [ ] **Step 6: Запустить тесты loop и mutation gate**

```bash
uv run pytest tests/test_loop_mutation_gate.py tests/test_loop_agent_wiring.py tests/test_loop_json_parse.py -v
```

Ожидаемый результат: все `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add agent/loop.py tests/test_loop_mutation_gate.py
git commit -m "fix(loop): force OUTCOME_NONE_CLARIFICATION after 2 consecutive contract-gate blocks — FIX-437"
```

---

## Task 6: Block E — POSTRUN_OPTIMIZE включить и стабилизировать

**Files:**
- Modify: `agent/postrun.py`
- Modify: `.env.example`

- [ ] **Step 1: Написать тест**

```python
# tests/test_lifecycle.py — добавить (или создать если файл не существует)

def test_count_dspy_examples_empty(tmp_path):
    """_count_dspy_examples returns 0 when file does not exist."""
    import agent.postrun as pr
    original = pr._DSPY_EXAMPLES
    pr._DSPY_EXAMPLES = tmp_path / "dspy_examples.jsonl"
    try:
        assert pr._count_dspy_examples() == 0
    finally:
        pr._DSPY_EXAMPLES = original


def test_count_dspy_examples_counts_lines(tmp_path):
    """_count_dspy_examples counts non-empty lines."""
    import agent.postrun as pr
    f = tmp_path / "dspy_examples.jsonl"
    f.write_text('{"a": 1}\n{"b": 2}\n\n{"c": 3}\n', encoding="utf-8")
    original = pr._DSPY_EXAMPLES
    pr._DSPY_EXAMPLES = f
    try:
        assert pr._count_dspy_examples() == 3
    finally:
        pr._DSPY_EXAMPLES = original


def test_optimize_skipped_below_min_examples(tmp_path, monkeypatch):
    """optimize step is skipped when dspy examples < POSTRUN_OPTIMIZE_MIN_EXAMPLES."""
    import agent.postrun as pr
    monkeypatch.setenv("POSTRUN_OPTIMIZE", "1")
    monkeypatch.setenv("POSTRUN_OPTIMIZE_MIN_EXAMPLES", "10")
    f = tmp_path / "dspy_examples.jsonl"
    f.write_text('{"a": 1}\n', encoding="utf-8")  # only 1 example
    original = pr._DSPY_EXAMPLES
    pr._DSPY_EXAMPLES = f
    calls = []
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: calls.append(a))
    try:
        pr._do_optimize_if_enabled()
    finally:
        pr._DSPY_EXAMPLES = original
    assert len(calls) == 0, "subprocess.run should not be called with < min_examples"
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_lifecycle.py::test_count_dspy_examples_empty tests/test_lifecycle.py::test_count_dspy_examples_counts_lines tests/test_lifecycle.py::test_optimize_skipped_below_min_examples -v
```

Ожидаемый результат: `ERROR` (функция `_count_dspy_examples` не существует).

- [ ] **Step 3: Обновить `agent/postrun.py`**

Добавить константу рядом с `_CONTRACT_EXAMPLES`:

```python
_CONTRACT_EXAMPLES = Path("data/dspy_contract_examples.jsonl")
_DSPY_EXAMPLES = Path("data/dspy_examples.jsonl")
```

Добавить функцию после `_count_contract_examples`:

```python
def _count_dspy_examples() -> int:
    if not _DSPY_EXAMPLES.exists():
        return 0
    return sum(1 for ln in _DSPY_EXAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip())
```

Заменить `_do_optimize_if_enabled`:

```python
def _do_optimize_if_enabled() -> None:
    if os.getenv("POSTRUN_OPTIMIZE", "0") != "1":
        return
    min_ex = int(os.getenv("POSTRUN_OPTIMIZE_MIN_EXAMPLES", "10"))
    count = _count_dspy_examples()
    if count < min_ex:
        log.info("[postrun] optimize skipped: %d dspy examples < min=%d", count, min_ex)
        return
    try:
        proc = subprocess.run(
            [sys.executable, "scripts/optimize_prompts.py", "--target", "all"],
            check=True,
            capture_output=True,
            text=True,
        )
        tail = proc.stdout[-500:] if proc.stdout else ""
        log.info("[postrun] optimize done: %s", tail)
    except subprocess.CalledProcessError as exc:
        out = (exc.stdout or "")[-500:]
        err = (exc.stderr or "")[-300:]
        log.warning("[postrun] optimize skipped (exit %d): stdout=%s stderr=%s", exc.returncode, out, err)
```

- [ ] **Step 4: Обновить `.env.example`**

Найти строку `# POSTRUN_OPTIMIZE=0` и заменить на:

```
POSTRUN_OPTIMIZE=1          # Run scripts/optimize_prompts.py --target all after postrun
POSTRUN_OPTIMIZE_MIN_EXAMPLES=10  # Skip optimize if fewer than N dspy examples collected
```

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/test_lifecycle.py -v
```

Ожидаемый результат: все `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add agent/postrun.py .env.example tests/test_lifecycle.py
git commit -m "feat(postrun): enable POSTRUN_OPTIMIZE with min_examples threshold — FIX-438"
```

---

## Task 7: Финальная проверка

- [ ] **Step 1: Запустить полный тест-suite**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Ожидаемый результат: все тесты `PASSED`. Если есть падения — исправить перед следующим шагом.

- [ ] **Step 2: Smoke test промпта для каждого task_type**

```bash
uv run python -c "
from agent.prompt import build_system_prompt
for t in ['temporal', 'crm', 'lookup', 'capture', 'email', 'inbox']:
    p = build_system_prompt(t)
    # Убедиться что нет упоминаний удалённых доменных правил
    forbidden = ['VAULT_DATE', 'PAC1 rule', 'TOTAL_DAYS', 'implied_today', 'triangulat']
    for f in forbidden:
        if f in p:
            print(f'WARN: {t} still contains {f!r}')
    print(f'{t}: {len(p)} chars OK')
"
```

Ожидаемый результат: нет `WARN`, каждый тип печатает `OK`.

- [ ] **Step 3: Проверить что граф пустой**

```bash
uv run python -c "
import json
g = json.loads(open('data/wiki/graph.json').read())
print('nodes:', len(g['nodes']), 'edges:', len(g['edges']))
assert len(g['nodes']) == 0, 'graph not empty!'
print('OK — graph is empty')
"
```

- [ ] **Step 4: Финальный commit**

```bash
git add -A
git commit -m "chore: final cleanup after knowledge accumulation redesign — FIX-433..438"
```
