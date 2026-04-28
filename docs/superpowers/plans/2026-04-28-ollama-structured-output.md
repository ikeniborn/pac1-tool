# Ollama Structured Output Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить три структурных дефекта, мешающих надёжной работе pipeline на Ollama open-weight моделях: хрупкий JSON recovery, проглатывание `<think>`-блоков DSPy-парсером, нестабильная извлечение graph_deltas из wiki-синтеза.

**Architecture:** FIX-401 расширяет существующий `json_extract.py` json5-fallback'ом и bracket-repair'ом, затем подключает это к `contract_phase.py`. FIX-402 добавляет одну строку strip-regex в `DispatchLM.forward()` до вызова `_coerce_to_json`. FIX-403 переписывает `_split_markdown_and_deltas` в `wiki.py` — итерация по всем fence-матчам с поиском нужного ключа + json5 + bare-marker fallback.

**Tech Stack:** Python 3.12, `json5` (новая зависимость), `pytest`, существующий `dspy.BaseLM`, `pydantic`.

---

## Карта файлов

| Файл | Действие | FIX |
|------|----------|-----|
| `pyproject.toml` | Modify: добавить `json5` в dependencies | 401 |
| `agent/json_extract.py` | Modify: json5-fallback в bracket scan (строки 106–116) + bracket-balance repair в else (строки 117–118) | 401 |
| `agent/contract_phase.py` | Modify: заменить `json.loads(raw_executor/raw_evaluator)` на `_extract_json_from_text()` (строки 183–189, 211–217) | 401 |
| `agent/dspy_lm.py` | Modify: strip `<think>` после `call_llm_raw` перед `_coerce_to_json` (после строки 150) | 402 |
| `agent/wiki.py` | Modify: переписать `_split_markdown_and_deltas` (строки 811–837) | 403 |
| `tests/test_json_extraction.py` | Modify: добавить тесты для json5 и bracket-repair | 401 |
| `tests/test_dspy_lm_think_strip.py` | Create: тесты strip-логики | 402 |
| `tests/regression/test_wiki_graph_deltas.py` | Create: тесты нового `_split_markdown_and_deltas` | 403 |

---

## Task 1: FIX-401a — Добавить json5 и расширить json_extract.py

**Files:**
- Modify: `pyproject.toml`
- Modify: `agent/json_extract.py:100–118`
- Modify: `tests/test_json_extraction.py`

- [ ] **Step 1: Написать падающие тесты для json5 и bracket-repair**

Добавить в `tests/test_json_extraction.py`:

```python
# --- FIX-401: json5 fallback ---

def test_json5_trailing_comma():
    """Model emits trailing comma — json.loads fails, json5 succeeds."""
    text = '{"tool": "read", "path": "/x.md",}'
    result = _extract()(text)
    assert result is not None
    assert result["tool"] == "read"


def test_json5_single_quotes():
    """Model emits single-quoted JSON."""
    text = "{'tool': 'list', 'path': '/'}"
    result = _extract()(text)
    assert result is not None
    assert result["tool"] == "list"


# --- FIX-401: bracket-balance repair ---

def test_bracket_balance_repair_truncated():
    """Truncated JSON at EOF (missing closing brace)."""
    text = '{"tool": "read", "path": "/x.md"'
    result = _extract()(text)
    assert result is not None
    assert result["path"] == "/x.md"


def test_bracket_balance_repair_nested_truncated():
    """Nested object truncated."""
    text = '{"current_state": "working", "function": {"tool": "read"'
    result = _extract()(text)
    assert result is not None
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_json_extraction.py::test_json5_trailing_comma tests/test_json_extraction.py::test_json5_single_quotes tests/test_json_extraction.py::test_bracket_balance_repair_truncated tests/test_json_extraction.py::test_bracket_balance_repair_nested_truncated -v
```

Ожидается: FAIL (json5 не установлен, bracket-repair не реализован).

- [ ] **Step 3: Добавить json5 в pyproject.toml**

Найти блок `dependencies` в `pyproject.toml` и добавить `"json5>=0.9.0"`:

```toml
dependencies = [
    "connect-python>=0.8.1",
    "protobuf>=4.25.0",
    "httpx>=0.27.0",
    "openai>=2.26.0",
    "pydantic>=2.12.5",
    "annotated-types>=0.7.0",
    "anthropic>=0.86.0",
    "dspy-ai[gepa]>=2.5",
    "gepa>=0.0.26",
    "json5>=0.9.0",
]
```

- [ ] **Step 4: Установить зависимость**

```bash
uv sync
```

Ожидается: `json5` появляется в `.venv`.

- [ ] **Step 5: Добавить вспомогательную функцию и расширить bracket scan в json_extract.py**

Добавить после строки 11 (после `import re`):

```python
def _try_json5(text: str):
    """Try json5 parse; raises on failure (ImportError or parse error)."""
    import json5 as _j5  # optional dep, guarded by try/except at call sites
    return _j5.loads(text)
```

Заменить **строки 106–118** (внутренний try-block и else-clause):

```python
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
```

- [ ] **Step 6: Запустить тесты — убедиться что проходят**

```bash
uv run pytest tests/test_json_extraction.py -v
```

Ожидается: все тесты PASS (включая 4 новых и все старые).

- [ ] **Step 7: Коммит**

```bash
git add pyproject.toml agent/json_extract.py tests/test_json_extraction.py
git commit -m "fix(json_extract): FIX-401 json5 fallback + bracket-balance repair"
```

---

## Task 2: FIX-401b — Подключить json_extract к contract_phase.py

**Files:**
- Modify: `agent/contract_phase.py:183–189, 211–217`
- Modify: `tests/test_contract_phase.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_contract_phase.py`:

```python
def test_executor_proposal_json5_trailing_comma(monkeypatch):
    """Contract negotiation survives trailing comma in executor JSON."""
    from unittest.mock import patch
    import agent.contract_phase as cp

    # Executor returns trailing-comma JSON, evaluator returns valid JSON
    executor_response = '{"plan_steps": ["discover", "execute"], "expected_outcome": "done", "required_tools": ["read"], "open_questions": [], "agreed": true,}'
    evaluator_response = '{"success_criteria": ["task done"], "failure_conditions": ["no action"], "required_evidence": [], "objections": [], "counter_proposal": null, "agreed": true}'

    call_count = 0
    def fake_llm(system, user, model, cfg, **kwargs):
        nonlocal call_count
        call_count += 1
        tok = kwargs.get("token_out", {})
        if tok is not None:
            tok["input"] = 10
            tok["output"] = 10
        return executor_response if call_count % 2 == 1 else evaluator_response

    with patch("agent.contract_phase.call_llm_raw", side_effect=fake_llm):
        with patch("agent.contract_phase._load_prompt", return_value="system prompt"):
            contract, _, _, _ = cp.negotiate_contract(
                task_text="do the thing",
                task_type="email",
                agents_md="",
                wiki_context="",
                graph_context="",
                model="qwen3.5:cloud",
                cfg={},
                max_rounds=1,
            )
    assert not contract.is_default
    assert "discover" in contract.plan_steps
```

- [ ] **Step 2: Запустить — убедиться что падает**

```bash
uv run pytest tests/test_contract_phase.py::test_executor_proposal_json5_trailing_comma -v
```

Ожидается: FAIL (bare `json.loads` не справляется с trailing comma).

- [ ] **Step 3: Подключить _extract_json_from_text в contract_phase.py**

Добавить импорт после строки 19:

```python
from .json_extract import _extract_json_from_text
```

Заменить **строки 183–189** (executor parse):

```python
        # FIX-401: use multi-level JSON extractor instead of bare json.loads
        extracted_executor = _extract_json_from_text(raw_executor)
        try:
            proposal = ExecutorProposal(**(extracted_executor or {}))
        except (ValidationError, TypeError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] executor parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript
```

Заменить **строки 211–217** (evaluator parse):

```python
        # FIX-401: use multi-level JSON extractor instead of bare json.loads
        extracted_evaluator = _extract_json_from_text(raw_evaluator)
        try:
            response = EvaluatorResponse(**(extracted_evaluator or {}))
        except (ValidationError, TypeError) as e:
            if _LOG_LEVEL == "DEBUG":
                print(f"[contract] evaluator parse error round {round_num}: {e}")
            return _load_default_contract(task_type), total_in, total_out, rounds_transcript
```

Удалить `_strip_fences` из строк 183 и 211 (теперь `_extract_json_from_text` обрабатывает fenced блоки сам).

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Ожидается: все тесты PASS.

- [ ] **Step 5: Коммит**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "fix(contract): FIX-401b wire _extract_json_from_text into negotiate_contract"
```

---

## Task 3: FIX-402 — Strip \<think\> блоков в DispatchLM

**Files:**
- Modify: `agent/dspy_lm.py:150–151`
- Create: `tests/test_dspy_lm_think_strip.py`

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_dspy_lm_think_strip.py`:

```python
"""FIX-402: DispatchLM.forward() strips <think>...</think> before DSPy field parser."""
import pytest
from unittest.mock import patch


def _make_lm():
    from agent.dspy_lm import DispatchLM
    return DispatchLM(model="qwen3.5:cloud", cfg={}, max_tokens=100)


def _forward(lm, completion: str) -> str:
    """Call forward() with a mocked call_llm_raw and return the response content."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    with patch("agent.dspy_lm.call_llm_raw", return_value=completion):
        resp = lm.forward(messages=messages)
    return resp.choices[0].message.content


def test_think_block_stripped():
    lm = _make_lm()
    result = _forward(lm, "<think>internal reasoning</think>\n{\"addendum\": \"use read first\"}")
    assert "<think>" not in result
    assert "addendum" in result


def test_multiline_think_stripped():
    lm = _make_lm()
    result = _forward(lm, "<think>\nline1\nline2\n</think>\n{\"field\": \"value\"}")
    assert "<think>" not in result
    assert "field" in result


def test_no_think_unchanged():
    lm = _make_lm()
    result = _forward(lm, '{"field": "value"}')
    assert result == '{"field": "value"}'


def test_think_only_response_becomes_empty():
    """If entire response is a think block, result is empty string (coerce_to_json handles it)."""
    lm = _make_lm()
    result = _forward(lm, "<think>only reasoning, no output</think>")
    assert "<think>" not in result
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/test_dspy_lm_think_strip.py -v
```

Ожидается: FAIL (`<think>` не стрипается).

- [ ] **Step 3: Добавить strip в dspy_lm.py**

Заменить **строку 151** (`raw = _coerce_to_json(raw or "", user_msg)`):

```python
        # FIX-402: strip <think> blocks emitted by Ollama reasoning models before DSPy field parser
        if raw and "<think>" in raw:
            raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
        raw = _coerce_to_json(raw or "", user_msg)
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/test_dspy_lm_think_strip.py -v
```

Ожидается: все тесты PASS.

- [ ] **Step 5: Запустить полный suite чтобы нет регрессий**

```bash
uv run pytest tests/ -v --tb=short -q
```

Ожидается: все тесты PASS.

- [ ] **Step 6: Коммит**

```bash
git add agent/dspy_lm.py tests/test_dspy_lm_think_strip.py
git commit -m "fix(dspy_lm): FIX-402 strip <think> blocks before DSPy field parser"
```

---

## Task 4: FIX-403 — Robust graph_deltas extraction в wiki.py

**Files:**
- Modify: `agent/wiki.py:811–837`
- Create: `tests/regression/test_wiki_graph_deltas.py`

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/regression/test_wiki_graph_deltas.py`:

```python
"""FIX-403: _split_markdown_and_deltas handles non-trailing fence, bare markers, json5."""
import pytest
from unittest.mock import patch


def _split(response: str) -> tuple:
    # Enable WIKI_GRAPH_AUTOBUILD for tests
    with patch("agent.wiki._GRAPH_AUTOBUILD", True):
        from agent.wiki import _split_markdown_and_deltas
        return _split_markdown_and_deltas(response)


def test_fence_at_end_baseline():
    """Existing behaviour: fenced block at end."""
    resp = 'Some markdown text.\n```json\n{"graph_deltas": {"new_insights": []}}\n```'
    markdown, deltas = _split(resp)
    assert "graph_deltas" not in markdown
    assert deltas == {"new_insights": []}


def test_fence_in_middle():
    """FIX-403: fenced block in the middle of response (not at end)."""
    resp = (
        'Intro text.\n'
        '```json\n{"graph_deltas": {"new_rules": [{"text": "use list first"}]}}\n```\n'
        'Trailing paragraph.'
    )
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)
    assert "new_rules" in deltas


def test_fence_json5_trailing_comma():
    """FIX-403: json5 fallback for trailing comma inside fenced block."""
    resp = '```json\n{"graph_deltas": {"new_insights": [],},}\n```'
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)


def test_bare_graph_deltas_marker():
    """FIX-403: no fence, just graph_deltas: {...} in text."""
    resp = 'Some synthesis.\ngraph_deltas: {"new_insights": [{"text": "tip"}]}'
    markdown, deltas = _split(resp)
    assert isinstance(deltas, dict)
    assert "new_insights" in deltas


def test_invalid_json_fail_open():
    """Malformed JSON → fail-open: returns original response and empty dict."""
    resp = '```json\n{totally invalid{{{\n```'
    markdown, deltas = _split(resp)
    assert deltas == {}
    assert markdown == resp


def test_no_fence_fail_open():
    """No fence at all → fail-open."""
    resp = "Just plain text, no JSON block."
    markdown, deltas = _split(resp)
    assert deltas == {}
    assert markdown == resp
```

- [ ] **Step 2: Запустить — убедиться что падают**

```bash
uv run pytest tests/regression/test_wiki_graph_deltas.py -v
```

Ожидается: `test_fence_in_middle`, `test_fence_json5_trailing_comma`, `test_bare_graph_deltas_marker` — FAIL.

- [ ] **Step 3: Переписать _split_markdown_and_deltas в wiki.py**

Заменить **строки 811–837** полностью:

```python
def _split_markdown_and_deltas(response: str) -> tuple[str, dict]:
    """FIX-403: extract graph_deltas from synthesis response.

    Search order:
    1. Any ```json ... ``` fenced block containing graph_deltas key (any position).
    2. Bare `graph_deltas: {...}` marker in response text.
    3. Fail-open: return (response, {}).

    Tries json.loads first, json5.loads as fallback (trailing commas / single quotes).
    """
    if not _GRAPH_AUTOBUILD:
        return response, {}
    import json as _json

    def _parse(raw: str) -> dict | None:
        try:
            return _json.loads(raw)
        except Exception:
            pass
        try:
            from agent.json_extract import _try_json5
            return _try_json5(raw)
        except Exception:
            return None

    # 1. Fenced ```json ... ``` block — search any position
    for m in _JSON_FENCE_RE.finditer(response):
        parsed = _parse(m.group(1))
        if isinstance(parsed, dict) and isinstance(parsed.get("graph_deltas"), dict):
            markdown = (response[:m.start()] + response[m.end():]).strip()
            return markdown, parsed["graph_deltas"]

    # 2. Bare graph_deltas: {...} marker (no fence)
    import re as _re_local
    bare = _re_local.search(r'"?graph_deltas"?\s*:\s*(\{.*?\})\s*$', response, _re_local.DOTALL)
    if bare:
        parsed = _parse(bare.group(1))
        if isinstance(parsed, dict):
            print("[wiki-graph] fence: found bare graph_deltas marker")
            return response, parsed

    print("[wiki-graph] fence: missing — LLM did not emit ```json block")
    return response, {}
```

- [ ] **Step 4: Запустить тесты**

```bash
uv run pytest tests/regression/test_wiki_graph_deltas.py -v
```

Ожидается: все тесты PASS.

- [ ] **Step 5: Запустить полный suite**

```bash
uv run pytest tests/ -v --tb=short -q
```

Ожидается: все тесты PASS.

- [ ] **Step 6: Коммит**

```bash
git add agent/wiki.py tests/regression/test_wiki_graph_deltas.py
git commit -m "fix(wiki): FIX-403 robust graph_deltas extraction (any position + json5 + bare marker)"
```

---

## Self-Review

**Spec coverage:**
- FIX-401 (JSON repair pipeline): Task 1 (json_extract) + Task 2 (contract_phase) ✓
- FIX-402 (think-block strip): Task 3 ✓
- FIX-403 (graph_deltas extraction): Task 4 ✓
- `json5` dependency: Task 1 Step 3 ✓

**Placeholder scan:** нет TBD/TODO/placeholder — все шаги содержат конкретный код.

**Type consistency:**
- `_try_json5` определяется в Task 1 (json_extract.py) и используется в Task 4 (wiki.py) через `from agent.json_extract import _try_json5` ✓
- `_extract_json_from_text` → `dict | None`; используется как `**(extracted or {})` → TypeError перехватывается ✓
- `_split_markdown_and_deltas` → `tuple[str, dict]` — возвращаемый тип не изменился ✓

**Порядок задач:** Task 1 (json_extract) должен быть выполнен до Task 2 (contract_phase) — Task 2 импортирует `_extract_json_from_text` и `_try_json5` из json_extract. Task 3 и Task 4 независимы.
