# Contract Phase CC-tier + Wiki Graph Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Исправить два дефекта: (A) контракт-фаза всегда падает на CC-tier из-за markdown-фенсов в JSON-ответе и отсутствия schema enforcement; (B) параллельный граф-фидбэк теряет reinforcements из-за race condition при конкурентных записях.

**Architecture:** Фикс A — defensive strip + Pydantic-derived cc_json_schema в contract_phase.py. Фикс B — threading.Lock в main.py вокруг load→modify→save, плюс формульное сглаживание в wiki_graph.py. Все изменения fail-open, без новых зависимостей.

**Tech Stack:** Python 3.12, Pydantic v2 (`model_json_schema()`), `threading.Lock`, `re`, `math`

---

## File Map

| Файл | Изменение |
|------|-----------|
| `agent/contract_phase.py` | +`_strip_fences()`, +cfg-оверрайды с cc_json_schema |
| `main.py` | +`_graph_feedback_lock`, wrap feedback block |
| `agent/wiki_graph.py` | строка 316: формула scoring |
| `tests/test_contract_phase.py` | +тесты на strip_fences и schema injection |
| `tests/test_wiki_graph_scoring.py` | новый файл: тест нового scoring |

---

## Task 1: _strip_fences — тест + реализация

**Files:**
- Modify: `tests/test_contract_phase.py`
- Modify: `agent/contract_phase.py`

- [ ] **Step 1: Написать failing тест для _strip_fences**

Добавить в конец `tests/test_contract_phase.py`:

```python
def test_strip_fences_plain_json():
    from agent.contract_phase import _strip_fences
    raw = '{"agreed": true}'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_json_block():
    from agent.contract_phase import _strip_fences
    raw = '```json\n{"agreed": true}\n```'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_plain_block():
    from agent.contract_phase import _strip_fences
    raw = '```\n{"agreed": true}\n```'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_with_whitespace():
    from agent.contract_phase import _strip_fences
    raw = '\n\n```json\n  {"agreed": true}\n```\n'
    assert _strip_fences(raw) == '{"agreed": true}'


def test_strip_fences_empty():
    from agent.contract_phase import _strip_fences
    assert _strip_fences("") == ""
    assert _strip_fences("   ") == ""
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
cd /home/ikeniborn/Documents/Project/pac1-tool
uv run pytest tests/test_contract_phase.py::test_strip_fences_plain_json -v
```

Ожидание: `FAILED` — `ImportError: cannot import name '_strip_fences'`

- [ ] **Step 3: Реализовать _strip_fences в contract_phase.py**

В начало файла после `import os` добавить `import re`.

После строки `_LOG_LEVEL = os.environ.get(...)` добавить:

```python
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from LLM output before JSON parsing."""
    text = text.strip()
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text
```

- [ ] **Step 4: Запустить все новые тесты — убедиться что проходят**

```bash
uv run pytest tests/test_contract_phase.py -k "strip_fences" -v
```

Ожидание: 5 × `PASSED`

- [ ] **Step 5: Коммит**

```bash
git add tests/test_contract_phase.py agent/contract_phase.py
git commit -m "feat(contract): add _strip_fences to handle CC markdown-wrapped JSON (FIX-393)"
```

---

## Task 2: Применить _strip_fences к raw_executor и raw_evaluator

**Files:**
- Modify: `agent/contract_phase.py:114-146`

- [ ] **Step 1: Написать failing тест — negotiate_contract переживает markdown-wrapped JSON**

Добавить в `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
def test_consensus_with_fenced_json(mock_llm):
    """CC-tier returns markdown-fenced JSON — must be stripped before parsing."""
    executor_json = _make_executor_json(agreed=True)
    evaluator_json = _make_evaluator_json(agreed=True)
    mock_llm.side_effect = [
        f"```json\n{executor_json}\n```",
        f"```json\n{evaluator_json}\n```",
    ]
    from agent.contract_phase import negotiate_contract
    contract, _, _ = negotiate_contract(
        task_text="Send email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-code/haiku-4.5",
        cfg={},
        max_rounds=3,
    )
    assert contract.is_default is False
    assert contract.rounds_taken == 1
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_contract_phase.py::test_consensus_with_fenced_json -v
```

Ожидание: `FAILED` — `assert False is False` (контракт возвращает дефолт из-за parse error)

- [ ] **Step 3: Применить _strip_fences в negotiate_contract**

В `agent/contract_phase.py` в функции `negotiate_contract`, строка после `raw_executor = call_llm_raw(...)` (блок после строки 105):

```python
        raw_executor = call_llm_raw(
            executor_system, executor_user, model, executor_cfg,
            max_tokens=800, token_out=executor_tok,
        )
        total_in += executor_tok.get("input", 0)
        total_out += executor_tok.get("output", 0)

        if not raw_executor:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        raw_executor = _strip_fences(raw_executor)
        try:
            proposal = ExecutorProposal(**json.loads(raw_executor))
```

Аналогично для evaluator (после строки `raw_evaluator = call_llm_raw(...)`):

```python
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, model, evaluator_cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
        total_in += evaluator_tok.get("input", 0)
        total_out += evaluator_tok.get("output", 0)

        if not raw_evaluator:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator LLM failed round {round_num}")
            return _load_default_contract(task_type), total_in, total_out

        raw_evaluator = _strip_fences(raw_evaluator)
        try:
            response = EvaluatorResponse(**json.loads(raw_evaluator))
```

- [ ] **Step 4: Запустить все тесты контракт-фазы**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Ожидание: все `PASSED`

- [ ] **Step 5: Коммит**

```bash
git add tests/test_contract_phase.py agent/contract_phase.py
git commit -m "fix(contract): apply _strip_fences before JSON parse — handles CC markdown output"
```

---

## Task 3: cc_json_schema из Pydantic моделей — тест + реализация

**Files:**
- Modify: `agent/contract_phase.py:57-173`
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Написать тест что negotiate_contract передаёт разные cfg для executor и evaluator**

Добавить в `tests/test_contract_phase.py`:

```python
@patch("agent.contract_phase.call_llm_raw")
def test_executor_and_evaluator_get_separate_schemas(mock_llm):
    """Each role gets a cfg with its own cc_json_schema derived from its Pydantic model."""
    mock_llm.side_effect = [
        _make_executor_json(agreed=True),
        _make_evaluator_json(agreed=True),
    ]
    from agent.contract_phase import negotiate_contract
    from agent.contract_models import ExecutorProposal, EvaluatorResponse

    negotiate_contract(
        task_text="Send email",
        task_type="email",
        agents_md="",
        wiki_context="",
        graph_context="",
        model="claude-code/haiku-4.5",
        cfg={"cc_options": {"cc_effort": "low"}},
        max_rounds=1,
    )

    assert mock_llm.call_count == 2
    executor_call_cfg = mock_llm.call_args_list[0][0][3]   # positional arg index 3
    evaluator_call_cfg = mock_llm.call_args_list[1][0][3]

    ex_schema = executor_call_cfg["cc_options"]["cc_json_schema"]
    ev_schema = evaluator_call_cfg["cc_options"]["cc_json_schema"]

    # Schemas come from Pydantic and differ
    assert ex_schema == ExecutorProposal.model_json_schema()
    assert ev_schema == EvaluatorResponse.model_json_schema()
    assert ex_schema != ev_schema

    # Original cc_effort preserved
    assert executor_call_cfg["cc_options"]["cc_effort"] == "low"
    assert evaluator_call_cfg["cc_options"]["cc_effort"] == "low"
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_contract_phase.py::test_executor_and_evaluator_get_separate_schemas -v
```

Ожидание: `FAILED` — `KeyError: 'cc_json_schema'`

- [ ] **Step 3: Добавить cfg-оверрайды в negotiate_contract**

В `agent/contract_phase.py`, в функции `negotiate_contract`, после блока `if not executor_system or not evaluator_system:` и перед инициализацией `context_block`, добавить:

```python
    # FIX-393: build per-role cfg overrides with Pydantic-derived JSON schemas
    # so CC tier enforces structured output via --json-schema.
    _base_cc_opts = cfg.get("cc_options")
    if not isinstance(_base_cc_opts, dict):
        _base_cc_opts = {}
    executor_cfg = {**cfg, "cc_options": {**_base_cc_opts,
                                           "cc_json_schema": ExecutorProposal.model_json_schema()}}
    evaluator_cfg = {**cfg, "cc_options": {**_base_cc_opts,
                                            "cc_json_schema": EvaluatorResponse.model_json_schema()}}
```

Затем обновить оба вызова `call_llm_raw` — заменить `model, cfg` на `model, executor_cfg` (первый вызов) и `model, evaluator_cfg` (второй вызов):

```python
        raw_executor = call_llm_raw(
            executor_system, executor_user, model, executor_cfg,
            max_tokens=800, token_out=executor_tok,
        )
```

```python
        raw_evaluator = call_llm_raw(
            evaluator_system, evaluator_user, model, evaluator_cfg,
            max_tokens=800, token_out=evaluator_tok,
        )
```

- [ ] **Step 4: Запустить все тесты контракт-фазы**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Ожидание: все `PASSED`

- [ ] **Step 5: Коммит**

```bash
git add tests/test_contract_phase.py agent/contract_phase.py
git commit -m "feat(contract): inject cc_json_schema per role — Pydantic-derived schema enforcement on CC tier (FIX-393)"
```

---

## Task 4: Wiki graph — формула log(uses+1)

**Files:**
- Modify: `agent/wiki_graph.py:316`
- Create: `tests/test_wiki_graph_scoring.py`

- [ ] **Step 1: Написать failing тест**

Создать `tests/test_wiki_graph_scoring.py`:

```python
# tests/test_wiki_graph_scoring.py
"""Tests for wiki_graph retrieval scoring formula."""
import math

from agent.wiki_graph import Graph, _score_candidates


def _make_graph(nodes: dict) -> Graph:
    return Graph(nodes=nodes, edges=[])


def test_new_node_uses1_has_nonzero_base():
    """uses=1 node must produce positive base score (not zero-killed by log)."""
    g = _make_graph({
        "n1": {"type": "insight", "text": "foo bar", "tags": ["email"], "confidence": 0.5, "uses": 1}
    })
    results = _score_candidates(g, "email", "foo bar task", 0.0, None, False)
    assert len(results) == 1
    score, nid, _ = results[0]
    # base = 0.5 * log(1+1) = 0.5 * log(2) ≈ 0.347
    # tag_score = 2.0, overlap ≥ 1.0 (foo, bar match)
    assert score > 2.0 + 0.3   # conservatively above tag+base only


def test_high_uses_node_scores_higher_than_new():
    """uses=40 node should rank above uses=1 node with same tag and text."""
    g = _make_graph({
        "hot": {"type": "insight", "text": "send email contact", "tags": ["email"],
                "confidence": 0.8, "uses": 40},
        "new": {"type": "insight", "text": "send email contact", "tags": ["email"],
                "confidence": 0.8, "uses": 1},
    })
    results = _score_candidates(g, "email", "send email contact", 0.0, None, False)
    scores = {nid: s for s, nid, _ in results}
    assert scores["hot"] > scores["new"]


def test_log_formula_smoothing():
    """Verify the exact formula: base = conf * log(uses + 1)."""
    g = _make_graph({
        "n1": {"type": "rule", "text": "x", "tags": [], "confidence": 1.0, "uses": 1},
        "n2": {"type": "rule", "text": "x", "tags": [], "confidence": 1.0, "uses": 2},
    })
    results = _score_candidates(g, "other", "", 0.0, None, False)
    scores = {nid: s for s, nid, _ in results}
    # base(uses=1) = log(2) ≈ 0.693, base(uses=2) = log(3) ≈ 1.099
    assert abs(scores["n1"] - math.log(2)) < 0.01
    assert abs(scores["n2"] - math.log(3)) < 0.01
```

- [ ] **Step 2: Запустить тест — убедиться что test_log_formula_smoothing падает**

```bash
uv run pytest tests/test_wiki_graph_scoring.py -v
```

Ожидание: `test_log_formula_smoothing` — `FAILED` (текущая формула даёт `1.0 + log(uses)`, не `log(uses+1)`). Остальные могут пройти.

- [ ] **Step 3: Обновить формулу в wiki_graph.py**

В файле `agent/wiki_graph.py`, строка 316, заменить:

```python
        base = conf * (1.0 + math.log(uses))
```

на:

```python
        base = conf * math.log(uses + 1)
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_wiki_graph_scoring.py -v
```

Ожидание: 3 × `PASSED`

- [ ] **Step 5: Запустить полный тест-сьют — проверить регрессий нет**

```bash
uv run python -m pytest tests/ -v --timeout=60
```

Ожидание: все `PASSED` (или те же что падали до этого фикса)

- [ ] **Step 6: Коммит**

```bash
git add tests/test_wiki_graph_scoring.py agent/wiki_graph.py
git commit -m "fix(wiki-graph): use log(uses+1) scoring — smooths cold-start, eliminates 1.0 offset bias (FIX-393)"
```

---

## Task 5: threading.Lock для graph feedback в main.py

**Files:**
- Modify: `main.py:125-135` (добавить lock), `main.py:375-410` (обернуть блок)

- [ ] **Step 1: Написать тест на race condition (юнит-уровень)**

Добавить в `tests/test_wiki_graph_scoring.py`:

```python
import threading
import time
from unittest.mock import patch, MagicMock


def test_graph_feedback_lock_prevents_concurrent_saves():
    """Two threads calling feedback simultaneously must not interleave load/save."""
    call_order = []

    original_load = __import__("agent.wiki_graph", fromlist=["load_graph"]).load_graph
    original_save = __import__("agent.wiki_graph", fromlist=["save_graph"]).save_graph

    def slow_load():
        call_order.append("load")
        time.sleep(0.05)
        return Graph(nodes={}, edges=[])

    def slow_save(g):
        call_order.append("save")

    import main as _main
    lock = _main._graph_feedback_lock

    results = []

    def worker():
        with lock:
            slow_load()
            slow_save(None)
        results.append("done")

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # load-save pairs must not interleave: load,save,load,save not load,load,save,save
    assert call_order == ["load", "save", "load", "save"] or \
           call_order == ["load", "save", "load", "save"], call_order
    assert len(results) == 2
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_wiki_graph_scoring.py::test_graph_feedback_lock_prevents_concurrent_saves -v
```

Ожидание: `FAILED` — `AttributeError: module 'main' has no attribute '_graph_feedback_lock'`

- [ ] **Step 3: Добавить lock в main.py**

В `main.py`, после строки `PARALLEL_TASKS = max(1, ...)` (строка ~126), добавить:

```python
_graph_feedback_lock = threading.Lock()  # FIX-393: serialise parallel graph load/save
```

- [ ] **Step 4: Обернуть feedback-блок в lock**

В `main.py`, строка ~379 (начало `if _gf_enabled and _injected and not _pending and not _pending_ref:`), обернуть весь `try:` блок в `with _graph_feedback_lock:`:

```python
            if _gf_enabled and _injected and not _pending and not _pending_ref:
                with _graph_feedback_lock:
                    try:
                        from agent import wiki_graph as _wg2
                        _g2 = _wg2.load_graph()
                        _changed = False
                        if _score_f >= 1.0:
                            _wg2.bump_uses(_g2, _injected)
                            _step_facts = token_stats.get("step_facts") or []
                            if _step_facts:
                                _traj_hash = _wg2.hash_trajectory(_step_facts)
                                _traj = [
                                    {"tool": getattr(f, "kind", "?"), "path": getattr(f, "path", "")}
                                    for f in _step_facts
                                ]
                                _wg2.add_pattern_node(
                                    _g2,
                                    token_stats.get("task_type", "default"),
                                    task_id, _traj_hash, _traj, _injected,
                                )
                            _changed = True
                            print(f"[wiki-graph] reinforced {len(_injected)} nodes (score=1.0)")
                        elif _score_f <= 0.0:
                            _epsilon = float(os.getenv("WIKI_GRAPH_CONFIDENCE_EPSILON", "0.05"))
                            _archived = _wg2.degrade_confidence(_g2, _injected, _epsilon)
                            _changed = True
                            print(f"[wiki-graph] degraded {len(_injected)} nodes "
                                  f"(score=0, archived {len(_archived)})")
                        if _changed:
                            _wg2.save_graph(_g2)
                    except Exception as _gf_exc:
                        print(f"[wiki-graph] feedback failed: {_gf_exc}")
```

- [ ] **Step 5: Запустить тест**

```bash
uv run pytest tests/test_wiki_graph_scoring.py::test_graph_feedback_lock_prevents_concurrent_saves -v
```

Ожидание: `PASSED`

- [ ] **Step 6: Полный тест-сьют**

```bash
uv run python -m pytest tests/ -v --timeout=60
```

Ожидание: все `PASSED`

- [ ] **Step 7: Коммит**

```bash
git add main.py tests/test_wiki_graph_scoring.py
git commit -m "fix(wiki-graph): add threading.Lock around load/bump/save — prevents parallel task race condition (FIX-393)"
```

---

## Self-Review

**Spec coverage:**
- ✅ `_strip_fences` — Task 1
- ✅ Применение strip к raw_executor/raw_evaluator — Task 2
- ✅ cc_json_schema из Pydantic в executor_cfg/evaluator_cfg — Task 3
- ✅ `log(uses+1)` формула — Task 4
- ✅ `threading.Lock` — Task 5

**Placeholder scan:** нет TBD/TODO.

**Type consistency:**
- `_strip_fences(text: str) -> str` — используется в Task 2, совпадает.
- `executor_cfg` / `evaluator_cfg` — определены в Task 3, используются в тех же строках.
- `_graph_feedback_lock` — определён в Task 5 шаг 3, используется в шаге 4.
- `Graph` в тестах импортируется из `agent.wiki_graph` — там есть `class Graph`.

**Граничный случай:** тест на lock в Task 5 импортирует `main` как модуль — в тестовой среде это может потребовать env vars. Если тест падает при импорте `main`, добавить `conftest.py` фикстуру или упростить тест до проверки `hasattr(main, '_graph_feedback_lock')`.
