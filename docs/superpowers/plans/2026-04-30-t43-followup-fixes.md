# T43 Followup Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить три проблемы, выявленных аудитом t43: контракт игнорирует wiki-refusals, evaluator bypassed для всех lookup, error-ingest создаёт дубликаты в графе.

**Architecture:** Три независимые хирургические правки без рефакторинга: (1) `agent/wiki.py` + `agent/contract_phase.py` — добавить загрузку Verified Refusals в контекст контракта; (2) `agent/loop.py` — заменить паушальный bypass точечным; (3) `agent/wiki_graph.py` — добавить dedup-проверку перед вставкой узла. TDD: сначала тест, потом код.

**Tech Stack:** Python 3.11+, pytest, uv. FIX-419 / FIX-420 / FIX-421.

---

## Карта файлов

**Изменить:**
- `agent/wiki.py` — добавить `load_refusal_hints(task_type) -> str`
- `agent/contract_phase.py:146` — вызвать `load_refusal_hints()` и добавить в `context_block`
- `agent/loop.py:2185` — заменить `if task_type == TASK_LOOKUP: _eval_bypass = True` на точечную логику
- `agent/wiki_graph.py` — добавить `_token_overlap()`, `_find_near_duplicate()`, применить в `_upsert()`

**Тесты:**
- `tests/test_contract_phase.py` — добавить тест что refusal_hints попадают в вызов LLM
- `tests/test_loop_mutation_gate.py` — добавить тест lookup bypass с/без exploration steps
- `tests/test_wiki_graph_dedup.py` — новый файл, тесты dedup при error-ingest

---

## Task 1: FIX-419 — Контракт читает Verified Refusals из wiki

**Files:**
- Modify: `agent/wiki.py` (добавить функцию после `load_contract_constraints`)
- Modify: `agent/contract_phase.py:146` (добавить вызов в `negotiate_contract`)
- Test: `tests/test_contract_phase.py` (добавить тест в конец файла)

- [ ] **Step 1: Написать падающий тест**

Добавить в конец `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
@patch("agent.contract_phase._load_refusal_hints")
def test_refusal_hints_injected_into_context(mock_hints, mock_llm):
    """FIX-419: refusal hints from wiki appear in the executor prompt."""
    mock_hints.return_value = "## Verified refusal: t43\nOutcome: OUTCOME_NONE_CLARIFICATION\nWhy refuse: no article on that date."
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    negotiate_contract(
        task_text="which article captured 37 days ago?",
        task_type="lookup",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="test-model",
        cfg={},
        max_rounds=1,
    )
    # The first LLM call is the executor — its user prompt must contain the hint
    first_call_user = mock_llm.call_args_list[0][0][1]
    assert "OUTCOME_NONE_CLARIFICATION" in first_call_user
    assert "Verified refusal" in first_call_user
```

- [ ] **Step 2: Убедиться что тест падает**

```bash
uv run pytest tests/test_contract_phase.py::test_refusal_hints_injected_into_context -v
```

Ожидаем: `FAILED` — `_load_refusal_hints` не существует.

- [ ] **Step 3: Добавить `load_refusal_hints` в `agent/wiki.py`**

Найти строку с `def load_contract_constraints` (~328) и вставить новую функцию **перед** ней:

```python
def load_refusal_hints(task_type: str, max_refusals: int = 3) -> str:
    """FIX-419: extract up to max_refusals Verified Refusal sections from wiki page.

    Returns a compact block for injection into contract context, or '' if none.
    """
    page_name = _TYPE_TO_PAGE.get(task_type, task_type)
    content = _read_page(page_name)
    if not content:
        return ""
    sections = re.split(r"(?m)^## Verified refusal: ", content)
    if len(sections) <= 1:
        return ""
    refusals = sections[1:][-max_refusals:]
    lines = ["VERIFIED REFUSALS (known patterns that must return OUTCOME_NONE_CLARIFICATION):"]
    for r in refusals:
        # Take up to 8 lines per refusal to keep context tight
        snippet = "\n".join(r.splitlines()[:8]).strip()
        lines.append(f"## Verified refusal: {snippet}")
    return "\n\n".join(lines)
```

- [ ] **Step 4: Экспортировать из `contract_phase.py` и добавить в контекст**

В `agent/contract_phase.py` найти строку с импортом `load_contract_constraints`:

```python
from .wiki import load_contract_constraints as _load_contract_constraints
```

Заменить на:

```python
from .wiki import load_contract_constraints as _load_contract_constraints
from .wiki import load_refusal_hints as _load_refusal_hints
```

Затем в теле `negotiate_contract`, после блока `if graph_context:` (~строка 149), добавить:

```python
    # FIX-419: inject verified refusals so contract can generate refusal-plan
    _refusal_hints = _load_refusal_hints(task_type)
    if _refusal_hints:
        context_block += f"\n\n{_refusal_hints}"
```

- [ ] **Step 5: Проверить что тест проходит**

```bash
uv run pytest tests/test_contract_phase.py::test_refusal_hints_injected_into_context -v
```

Ожидаем: `PASSED`.

- [ ] **Step 6: Прогнать все тесты contract_phase**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Ожидаем: все PASSED (без регрессий).

- [ ] **Step 7: Коммит**

```bash
git add agent/wiki.py agent/contract_phase.py tests/test_contract_phase.py
git commit -m "feat(contract): FIX-419 inject wiki Verified Refusals into contract context"
```

---

## Task 2: FIX-420 — Точечный evaluator bypass для lookup

**Files:**
- Modify: `agent/loop.py:~2185`
- Test: `tests/test_loop_mutation_gate.py` (добавить тесты в конец)

- [ ] **Step 1: Написать падающие тесты**

Добавить в конец `tests/test_loop_mutation_gate.py`:

```python
def _make_report(outcome="OUTCOME_OK", steps=None):
    from agent.models import ReportTaskCompletion
    return ReportTaskCompletion(
        completed_steps_laconic=steps or [],
        message="done",
        outcome=outcome,
        grounding_refs=[],
    )


def test_lookup_bypass_when_explored():
    """FIX-420: lookup with exploration steps → bypass evaluator (existing behaviour kept)."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=["listed /01_capture/influential — 5 articles"])
    assert _should_bypass_evaluator_lookup(report) is True


def test_lookup_no_bypass_when_no_exploration():
    """FIX-420: lookup OUTCOME_OK with zero exploration → evaluator must run."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_OK", steps=[])
    assert _should_bypass_evaluator_lookup(report) is False


def test_lookup_bypass_for_clarification():
    """FIX-420: OUTCOME_NONE_CLARIFICATION never needs evaluator regardless of steps."""
    from agent.loop import _should_bypass_evaluator_lookup
    report = _make_report(outcome="OUTCOME_NONE_CLARIFICATION", steps=[])
    assert _should_bypass_evaluator_lookup(report) is True
```

- [ ] **Step 2: Убедиться что тесты падают**

```bash
uv run pytest tests/test_loop_mutation_gate.py::test_lookup_bypass_when_explored tests/test_loop_mutation_gate.py::test_lookup_no_bypass_when_no_exploration tests/test_loop_mutation_gate.py::test_lookup_bypass_for_clarification -v
```

Ожидаем: `FAILED` — `_should_bypass_evaluator_lookup` не существует.

- [ ] **Step 3: Добавить хелпер `_should_bypass_evaluator_lookup` в `agent/loop.py`**

Найти импорты в начале `loop.py`. После них (или рядом с другими `_*` хелперами) добавить:

```python
def _should_bypass_evaluator_lookup(report) -> bool:
    """FIX-420: targeted evaluator bypass for TASK_LOOKUP.

    Bypass only when:
    - outcome is OUTCOME_NONE_CLARIFICATION (no evaluation needed), OR
    - agent actually explored the vault (list/read/search/find/tree in steps)

    If OUTCOME_OK arrived with zero exploration steps → evaluator must run.
    """
    if report.outcome == "OUTCOME_NONE_CLARIFICATION":
        return True
    _steps = report.completed_steps_laconic or []
    _explored = any(
        any(kw in s.lower() for kw in ("list", "read", "search", "find", "tree"))
        for s in _steps
    )
    return _explored
```

- [ ] **Step 4: Заменить паушальный bypass в теле `run_loop` (~строка 2185)**

Найти блок:

```python
        # Lookup tasks: evaluator doesn't understand vault data model well enough
        if task_type == TASK_LOOKUP:
            _eval_bypass = True
```

Заменить на:

```python
        # FIX-420: targeted bypass — only skip evaluator when agent actually explored
        if task_type == TASK_LOOKUP:
            if _should_bypass_evaluator_lookup(job.function):
                _eval_bypass = True
```

- [ ] **Step 5: Проверить что тесты проходят**

```bash
uv run pytest tests/test_loop_mutation_gate.py::test_lookup_bypass_when_explored tests/test_loop_mutation_gate.py::test_lookup_no_bypass_when_no_exploration tests/test_loop_mutation_gate.py::test_lookup_bypass_for_clarification -v
```

Ожидаем: все `PASSED`.

- [ ] **Step 6: Прогнать все тесты loop**

```bash
uv run pytest tests/test_loop_mutation_gate.py tests/test_loop_json_parse.py -v
```

Ожидаем: все PASSED.

- [ ] **Step 7: Коммит**

```bash
git add agent/loop.py tests/test_loop_mutation_gate.py
git commit -m "fix(loop): FIX-420 targeted evaluator bypass for lookup — OUTCOME_OK without exploration runs evaluator"
```

---

## Task 3: FIX-421 — Dedup при error-ingest в граф

**Files:**
- Modify: `agent/wiki_graph.py` (добавить `_token_overlap`, `_find_near_duplicate`, применить в `_upsert`)
- Create: `tests/test_wiki_graph_dedup.py`

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_wiki_graph_dedup.py`:

```python
"""Tests for FIX-421: dedup before antipattern node insertion."""
from agent.wiki_graph import Graph, _token_overlap, _find_near_duplicate, merge_updates


def test_token_overlap_identical():
    assert _token_overlap("relative date queries fail", "relative date queries fail") == 1.0


def test_token_overlap_partial():
    score = _token_overlap("relative date queries fail on lookup", "date queries fail vault")
    assert 0.4 < score < 1.0


def test_token_overlap_disjoint():
    assert _token_overlap("write file to outbox", "search contact by name") < 0.2


def test_find_near_duplicate_finds_match():
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Relative date queries fail because file naming lacks parseable capture dates",
        "tags": ["lookup"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-30",
    }
    dup = _find_near_duplicate(g, "antipattern", "Relative date queries fail; file naming lacks parseable dates")
    assert dup == "a_existing"


def test_find_near_duplicate_no_match():
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Write files only to outbox, never to inbox",
        "tags": ["email"],
        "confidence": 0.6,
        "uses": 1,
        "last_seen": "2026-04-30",
    }
    dup = _find_near_duplicate(g, "antipattern", "Relative date queries fail on lookup tasks")
    assert dup is None


def test_merge_updates_dedup_antipattern():
    """FIX-421: near-duplicate antipattern bumps uses instead of creating new node."""
    g = Graph()
    g.nodes["a_existing"] = {
        "type": "antipattern",
        "text": "Relative date queries fail because file naming lacks parseable capture dates",
        "tags": ["lookup"],
        "confidence": 0.6,
        "uses": 2,
        "last_seen": "2026-04-29",
    }
    before_count = len(g.nodes)

    merge_updates(g, {
        "antipatterns": [{
            "text": "Relative date queries fail; file naming lacks parseable dates in captures",
            "tags": ["lookup"],
        }]
    })

    assert len(g.nodes) == before_count, "near-duplicate should not create a new node"
    assert g.nodes["a_existing"]["uses"] == 3, "uses should be bumped"
```

- [ ] **Step 2: Убедиться что тесты падают**

```bash
uv run pytest tests/test_wiki_graph_dedup.py -v
```

Ожидаем: `FAILED` — `_token_overlap` и `_find_near_duplicate` не существуют.

- [ ] **Step 3: Добавить `_token_overlap` и `_find_near_duplicate` в `agent/wiki_graph.py`**

После функции `_mk_node_id` (~строка 56) добавить:

```python
def _token_overlap(a: str, b: str) -> float:
    """FIX-421: Jaccard overlap of non-stop-word tokens. Used for near-dedup."""
    ta = frozenset(t for t in _NORMALIZE_RE.split(a.lower()) if t and t not in _STOP_WORDS)
    tb = frozenset(t for t in _NORMALIZE_RE.split(b.lower()) if t and t not in _STOP_WORDS)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_DEDUP_THRESHOLD = 0.8


def _find_near_duplicate(g: Graph, kind: str, text: str) -> str | None:
    """FIX-421: return node id of existing node with same type and overlap >= threshold, or None."""
    for nid, node in g.nodes.items():
        if node.get("type") != kind:
            continue
        if _token_overlap(text, node.get("text", "")) >= _DEDUP_THRESHOLD:
            return nid
    return None
```

- [ ] **Step 4: Применить dedup в `_upsert` внутри `merge_updates`**

Найти вложенную функцию `_upsert` (~строка 157) в `merge_updates`:

```python
    def _upsert(kind: str, prefix: str, item: dict) -> str:
        text = (item.get("text") or "").strip()
        if not text:
            return ""
        nid = _mk_node_id(prefix, text)
        tags = item.get("tags") or []
        if nid in g.nodes:
```

Добавить dedup-проверку **после** `nid = _mk_node_id(...)` и **перед** `if nid in g.nodes`:

```python
        nid = _mk_node_id(prefix, text)
        tags = item.get("tags") or []
        # FIX-421: near-dedup — bump uses on existing similar node instead of creating duplicate
        if nid not in g.nodes:
            dup_nid = _find_near_duplicate(g, kind, text)
            if dup_nid:
                nid = dup_nid
        if nid in g.nodes:
```

- [ ] **Step 5: Проверить что тесты проходят**

```bash
uv run pytest tests/test_wiki_graph_dedup.py -v
```

Ожидаем: все `PASSED`.

- [ ] **Step 6: Прогнать все тесты wiki_graph**

```bash
uv run pytest tests/test_wiki_graph_scoring.py tests/test_wiki_graph_edges.py tests/test_wiki_error_ingest.py tests/test_wiki_graph_dedup.py -v
```

Ожидаем: все PASSED.

- [ ] **Step 7: Проверить здоровье графа**

```bash
uv run python scripts/check_graph_health.py
```

Ожидаем: `OK` (либо `WARN` только по contaminated, не по duplicates).

- [ ] **Step 8: Коммит**

```bash
git add agent/wiki_graph.py tests/test_wiki_graph_dedup.py
git commit -m "fix(wiki-graph): FIX-421 dedup antipattern nodes on error-ingest via Jaccard overlap"
```

---

## Task 4: Финальная проверка

- [ ] **Step 1: Прогнать полный тест-сьют**

```bash
uv run python -m pytest tests/ -x -q 2>&1 | tail -20
```

Ожидаем: все PASSED, 0 failed.

- [ ] **Step 2: Проверить здоровье графа**

```bash
uv run python scripts/check_graph_health.py
```

- [ ] **Step 3: Добавить записи в CHANGELOG.md**

Добавить в начало секции `## [Unreleased]` или последнего релиза:

```
- FIX-419: contract_phase инжектирует Verified Refusals из wiki в context_block
- FIX-420: evaluator bypass для lookup стал точечным — OUTCOME_OK без exploration шагов запускает evaluator
- FIX-421: dedup near-duplicate antipattern узлов при error-ingest через Jaccard overlap
```

- [ ] **Step 4: Финальный коммит**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog FIX-419/420/421"
```
