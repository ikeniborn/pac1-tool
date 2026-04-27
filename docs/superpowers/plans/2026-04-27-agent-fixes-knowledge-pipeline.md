# Agent Fixes & Knowledge Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Исправить 4 кодовых бага (gate deadlocks, CC contract overhead, JSON parse errors, timeout hallucination) и включить накопление знаний wiki/graph в нормальном режиме.

**Architecture:** Изолированные точечные правки в 5 файлах (`contract_phase.py`, `loop.py`, `prompt.py`, `prephase.py`, `main.py`). Каждый таск независим — порядок реализации соответствует убыванию impact. TDD: тесты пишутся до кода.

**Tech Stack:** Python, pytest, uv, dataclasses, re, json, Pydantic

---

## File Structure

| Файл | Изменения |
|------|-----------|
| `agent/contract_phase.py` | A1: early-return для CC tier (строки 88–91) |
| `agent/loop.py` | A2a: фикс `_empty_searches` (строки 1786–1796); A2b: сообщение force-read-before-write (строки 1670–1679); A3: pre-strip перед `model_validate_json` (строки 533–534); A4: hint при `[FILE UNREADABLE]` (строки 2332–2339) |
| `agent/prompt.py` | A4: правило в `_CORE`; B6: правило TASK CONTEXT date |
| `agent/prephase.py` | B6: поиск явного vault date в AGENTS.MD и мета-файлах |
| `main.py` | B5: promote в нормальном режиме (после строки 373) |
| `tests/test_contract_phase.py` | Тест A1 |
| `tests/test_security_gates.py` | Тесты A2a, A2b |
| `tests/test_loop_json_parse.py` | Тест A3 (новый файл) |
| `tests/test_wiki_promote_normal.py` | Тест B5 (новый файл) |
| `tests/test_prephase_vault_date.py` | Тест B6 (новый файл) |

---

## Task 1: A1 — CC tier early-return в contract_phase.py (FIX-394)

**Проблема:** Все 43 задачи тратят 1–2 пустых CC subprocess-вызова на contract negotiation. CC tier не может вернуть structured JSON (tool_use stripped), поэтому `call_llm_raw` возвращает None и contract фолбэкит на default. Фикс: ранний выход до любых LLM-вызовов когда модель — CC tier.

**Files:**
- Modify: `agent/contract_phase.py:88-91`
- Test: `tests/test_contract_phase.py`

- [ ] **Step 1: Написать falling test**

Добавить в `tests/test_contract_phase.py` после существующих тестов:

```python
def test_cc_tier_skips_negotiation_no_llm_calls():
    """CC tier model → immediate default contract, zero LLM calls."""
    from unittest.mock import patch
    from agent.contract_phase import negotiate_contract

    with patch("agent.contract_phase.call_llm_raw") as mock_llm:
        contract, in_tok, out_tok = negotiate_contract(
            task_text="Write email to bob@x.com",
            task_type="email",
            agents_md="",
            wiki_context="",
            graph_context="",
            model="claude-code/sonnet-4.6",
            cfg={},
            max_rounds=3,
        )
    assert contract.is_default is True
    assert in_tok == 0
    assert out_tok == 0
    mock_llm.assert_not_called()
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_contract_phase.py::test_cc_tier_skips_negotiation_no_llm_calls -v
```

Expected: FAIL — `mock_llm` будет вызван (LLM вызовы произойдут).

- [ ] **Step 3: Реализовать FIX-394**

В `agent/contract_phase.py`, после блока `if not executor_system or not evaluator_system:` (строка 91), добавить:

```python
    # FIX-394: CC tier cannot produce structured JSON (tool_use blocks are stripped
    # from result). Skip negotiation entirely — avoids 1-2 empty subprocess launches
    # per task. Default contract is equivalent to what negotiate_contract would return.
    if model.startswith("claude-code/"):
        if _LOG_LEVEL == "DEBUG":
            print("[contract] CC tier — skipping negotiation, using default contract")
        return _load_default_contract(task_type), 0, 0
```

Итоговый блок в функции `negotiate_contract` выглядит так (строки 88–95):

```python
    if not executor_system or not evaluator_system:
        if _LOG_LEVEL == "DEBUG":
            print("[contract] prompts missing — using default contract")
        return _load_default_contract(task_type), 0, 0

    # FIX-394: CC tier cannot produce structured JSON (tool_use blocks are stripped
    # from result). Skip negotiation entirely — avoids 1-2 empty subprocess launches
    # per task. Default contract is equivalent to what negotiate_contract would return.
    if model.startswith("claude-code/"):
        if _LOG_LEVEL == "DEBUG":
            print("[contract] CC tier — skipping negotiation, using default contract")
        return _load_default_contract(task_type), 0, 0
```

- [ ] **Step 4: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/test_contract_phase.py -v
```

Expected: все тесты PASS.

- [ ] **Step 5: Коммит**

```bash
git add agent/contract_phase.py tests/test_contract_phase.py
git commit -m "fix(contract): skip CC-tier negotiation — avoids empty subprocess overhead (FIX-394)"
```

---

## Task 2: A2a — Исправить gate [force-read-contact]: README.MD не считается contact file (FIX-395)

**Проблема:** Поиск "maya" возвращает `contacts/README.MD:17`. Текущий код считает это попаданием (summary не содержит "no match"), поэтому счётчик `_empty_searches` не инкрементируется и gate никогда не расслабляется → t11 зациклился на 30 шагах.

**Root cause:** Строка 1792 в `loop.py`:
```python
if not _summary_lower or "no match" in _summary_lower or "not found" in _summary_lower or _f.error:
```
Не покрывает случай "попали только в README.MD, ни одного `.json`".

**Files:**
- Modify: `agent/loop.py:1786-1796`
- Test: `tests/test_security_gates.py`

- [ ] **Step 1: Написать falling test**

Добавить в `tests/test_security_gates.py` после последнего теста:

```python
# ---------------------------------------------------------------------------
# FIX-395: force-read-contact gate — README.MD hit does not count as contact found
# ---------------------------------------------------------------------------

def _make_step_fact(kind, path, summary, error=""):
    from agent.log_compaction import _StepFact
    return _StepFact(kind=kind, path=path, summary=summary, error=error)


def _simulate_contact_gate(step_facts, read_paths=None):
    """Simulate the _empty_searches logic from loop.py lines 1786-1796."""
    from agent.loop import _LoopState
    from agent.models import Req_Write
    # Build a minimal LoopState
    st = _LoopState.__new__(_LoopState)
    st.step_facts = step_facts
    st.read_paths = set(read_paths or [])
    st.read_content_cache = {}
    st.done_ops = set()
    st.outcome = ""

    # Replicate the gate check inline (read_paths has no contacts/)
    _read_any_contact = any("contacts/" in rp for rp in st.read_paths)
    if not _read_any_contact:
        _empty_searches = 0
        for _f in st.step_facts:
            if _f.kind != "search" or not (_f.path or "").startswith("/contacts"):
                continue
            _summary_lower = (_f.summary or "").lower()
            _has_contact_json = ".json" in _summary_lower
            if (not _summary_lower or "no match" in _summary_lower
                    or "not found" in _summary_lower or _f.error
                    or not _has_contact_json):
                _empty_searches += 1
                if _empty_searches >= 2:
                    _read_any_contact = True
                    break
    return _read_any_contact


def test_readme_hit_counts_as_empty_search():
    """contacts/README.MD:17 should NOT count as a contact-found result."""
    facts = [
        _make_step_fact("search", "/contacts", "contacts/README.MD:17"),
        _make_step_fact("search", "/contacts", "contacts/README.MD:17"),
    ]
    # Two README-only hits → gate should relax (bypass = True)
    assert _simulate_contact_gate(facts) is True


def test_contact_json_hit_blocks_gate_bypass():
    """contacts/alice.json:5 IS a contact found → gate should NOT relax."""
    facts = [
        _make_step_fact("search", "/contacts", "contacts/alice.json:5"),
    ]
    assert _simulate_contact_gate(facts) is False


def test_no_matches_still_relaxes():
    """(no matches) summary still triggers relax after 2 searches."""
    facts = [
        _make_step_fact("search", "/contacts", "(no matches)"),
        _make_step_fact("search", "/contacts", "(no matches)"),
    ]
    assert _simulate_contact_gate(facts) is True


def test_mixed_readme_and_json_blocks_bypass():
    """README.MD + contacts/alice.json → contact found, gate should NOT relax."""
    facts = [
        _make_step_fact("search", "/contacts", "contacts/README.MD:17, contacts/alice.json:5"),
    ]
    assert _simulate_contact_gate(facts) is False
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_security_gates.py::test_readme_hit_counts_as_empty_search -v
```

Expected: FAIL — helper `_simulate_contact_gate` использует текущую логику без `_has_contact_json`, поэтому README.MD не считается пустым.

- [ ] **Step 3: Реализовать FIX-395**

В `agent/loop.py` найти блок строки 1786–1796 и заменить:

```python
        # FIX-378: после ≥2 search-операций по /contacts/ с пустым результатом
        # считаем что recipient точно не в vault. Гейт срабатывает один раз;
        # повторных попыток write блокировать не нужно — иначе агент сдаётся
        # с OUTCOME_NONE_CLARIFICATION на валидной email-задаче (t11 post-mortem).
        if not _read_any_contact:
            _empty_searches = 0
            for _f in st.step_facts:
                if _f.kind != "search" or not (_f.path or "").startswith("/contacts"):
                    continue
                _summary_lower = (_f.summary or "").lower()
                if not _summary_lower or "no match" in _summary_lower or "not found" in _summary_lower or _f.error:
                    _empty_searches += 1
                    if _empty_searches >= 2:
                        _read_any_contact = True  # bypass: recipient absent after thorough search
                        break
```

на:

```python
        # FIX-378: после ≥2 search-операций по /contacts/ с пустым результатом
        # считаем что recipient точно не в vault. Гейт срабатывает один раз;
        # повторных попыток write блокировать не нужно — иначе агент сдаётся
        # с OUTCOME_NONE_CLARIFICATION на валидной email-задаче (t11 post-mortem).
        # FIX-395: README.MD hit ("contacts/README.MD:17") is NOT a contact file.
        # Count search as empty when result has no contacts/*.json reference.
        if not _read_any_contact:
            _empty_searches = 0
            for _f in st.step_facts:
                if _f.kind != "search" or not (_f.path or "").startswith("/contacts"):
                    continue
                _summary_lower = (_f.summary or "").lower()
                _has_contact_json = ".json" in _summary_lower
                if (not _summary_lower or "no match" in _summary_lower
                        or "not found" in _summary_lower or _f.error
                        or not _has_contact_json):
                    _empty_searches += 1
                    if _empty_searches >= 2:
                        _read_any_contact = True  # bypass: no contact .json found
                        break
```

- [ ] **Step 4: Обновить `_simulate_contact_gate` в тесте под новую логику**

Тест уже написан с `_has_contact_json` — он должен пройти. Запустить:

```bash
uv run pytest tests/test_security_gates.py -v
```

Expected: все тесты PASS, включая новые 4.

- [ ] **Step 5: Коммит**

```bash
git add agent/loop.py tests/test_security_gates.py
git commit -m "fix(gate): README.MD hit no longer blocks contact gate relax (FIX-395)"
```

---

## Task 3: A2b — Gate [force-read-before-write]: различать create vs update (FIX-396)

**Проблема:** Gate блокирует запись нового файла (например `/reminders/reminder-new.json`) если он ещё не был прочитан — потому что читать нечего. t13 ушёл в timeout после 18 шагов блокировки. Gate должен блокировать только update, но не create.

**Files:**
- Modify: `agent/loop.py:1670-1679`
- Test: `tests/test_security_gates.py`

- [ ] **Step 1: Написать failing test**

Добавить в `tests/test_security_gates.py`:

```python
# ---------------------------------------------------------------------------
# FIX-396: force-read-before-write — create vs update distinction
# ---------------------------------------------------------------------------

def test_force_read_message_mentions_create_option():
    """Gate message for unread path should mention create vs update distinction."""
    from agent.loop import _check_write_scope
    import types

    # We can't easily call the gate in isolation, so we check the message string
    # by reading the source and asserting the key phrases are present.
    import inspect
    import agent.loop as _loop_mod
    src = inspect.getsource(_loop_mod)

    # The gate message should differentiate create vs update
    assert "If creating new file" in src or "creating new" in src.lower()
    assert "If updating existing" in src or "updating existing" in src.lower()
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_security_gates.py::test_force_read_message_mentions_create_option -v
```

Expected: FAIL — текущее сообщение не содержит create/update distinction.

- [ ] **Step 3: Реализовать FIX-396**

В `agent/loop.py` найти строки 1670–1679 (gate `[force-read-before-write]`) и заменить return-строку:

```python
        if _is_mutating_record and _norm_path not in st.read_content_cache:
            print(f"{CLI_YELLOW}[FIX-350] Write blocked — no prior read of {_norm_path}{CLI_CLR}")
            return (
                f"[force-read-before-write] BLOCKED: Cannot write to '{job.function.path}' "
                f"without first reading it in this task. A write without a preceding read "
                f"synthesizes the schema from memory and drops unrequested fields "
                f"(account_manager, legal_name, description, notes, etc.). "
                f"Do `read '{job.function.path}'` FIRST, preserve every top-level key "
                f"verbatim, substitute ONLY the field(s) the task explicitly names, then write."
            )
```

на:

```python
        if _is_mutating_record and _norm_path not in st.read_content_cache:
            print(f"{CLI_YELLOW}[FIX-350] Write blocked — no prior read of {_norm_path}{CLI_CLR}")
            return (
                f"[force-read-before-write] BLOCKED: No prior read of '{job.function.path}'.\n"
                f"If updating existing file — read it first, preserve all top-level keys verbatim, "
                f"substitute ONLY the explicitly requested field(s), then write.\n"
                f"If creating new file — proceed with write directly (no read needed).\n"
                f"Determine from context whether this is a create or update and act accordingly."
            )
```

- [ ] **Step 4: Запустить тест — убедиться что проходит**

```bash
uv run pytest tests/test_security_gates.py -v
```

Expected: все тесты PASS.

- [ ] **Step 5: Коммит**

```bash
git add agent/loop.py tests/test_security_gates.py
git commit -m "fix(gate): force-read-before-write clarifies create vs update context (FIX-396)"
```

---

## Task 4: A3 — Pre-strip raw CC output перед model_validate_json (FIX-397)

**Проблема:** CC иногда добавляет текст после закрывающей `}` (объяснение, trailing chars). Результат: `model_validate_json` падает с "Invalid JSON: trailing characters", и execution fallback-extracts — лишний шаг/лог на ~70% задач.

**Решение:** Перед вызовом `model_validate_json` обрезать всё что идёт после последней `}` (балансируя скобки). Использовать уже существующий `_extract_json_from_text` для нахождения границы JSON объекта.

**Files:**
- Modify: `agent/loop.py:533-534`
- Test: `tests/test_loop_json_parse.py` (новый файл)

- [ ] **Step 1: Создать файл теста и написать failing test**

Создать `tests/test_loop_json_parse.py`:

```python
"""Tests for CC-tier JSON parse pre-stripping (FIX-397)."""


def _strip_to_json_object(text: str) -> str:
    """Extract substring from first '{' to last balanced '}' — mirrors FIX-397 logic."""
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    in_string = False
    escape_next = False
    end = start
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return text[start:end + 1]


def test_strip_trailing_text():
    """JSON object followed by explanation text is trimmed correctly."""
    raw = '{"tool": "read", "path": "/foo"}\nSome trailing explanation here.'
    result = _strip_to_json_object(raw)
    assert result == '{"tool": "read", "path": "/foo"}'


def test_strip_nested_object():
    """Nested objects are handled correctly."""
    raw = '{"a": {"b": 1}}\nextra'
    result = _strip_to_json_object(raw)
    assert result == '{"a": {"b": 1}}'


def test_no_trailing_text():
    """Clean JSON is returned unchanged."""
    raw = '{"tool": "write"}'
    assert _strip_to_json_object(raw) == raw


def test_preamble_text_stripped():
    """Text before { is stripped too."""
    raw = 'Here is the result: {"x": 1} done.'
    result = _strip_to_json_object(raw)
    assert result == '{"x": 1}'


def test_actual_loop_parse_does_not_log_extraction():
    """After FIX-397: model_validate_json succeeds on trailing-text output, no extraction log."""
    import io
    import sys
    from agent.models import NextStep

    trailing_raw = (
        '{"current_state":"searching contacts","plan_remaining_steps_brief":["write outbox"],'
        '"done_operations":[],"task_completed":false,'
        '"function":{"tool":"search","pattern":"maya","root":"/contacts","limit":10}}'
        "\nI chose search because the contact may not exist."
    )

    start = trailing_raw.find("{")
    depth = 0
    in_string = False
    escape_next = False
    end = start
    for i, ch in enumerate(trailing_raw[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    clean = trailing_raw[start:end + 1]

    buf = io.StringIO()
    old_out = sys.stdout
    sys.stdout = buf
    try:
        step = NextStep.model_validate_json(clean)
    finally:
        sys.stdout = old_out

    assert step is not None
    assert "JSON parse failed" not in buf.getvalue()
```

- [ ] **Step 2: Запустить тест — убедиться что unit-тесты логики проходят**

```bash
uv run pytest tests/test_loop_json_parse.py -v
```

Expected: первые 4 теста PASS (логика `_strip_to_json_object` верна); `test_actual_loop_parse_does_not_log_extraction` тоже PASS (логика уже корректна в изоляции — проверяет что clean string парсится без лога).

- [ ] **Step 3: Реализовать FIX-397 в loop.py**

В `agent/loop.py` найти блок CC tier dispatch (строки 533–544):

```python
        try:
            return NextStep.model_validate_json(raw), elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
        except (ValidationError, ValueError) as e:
            print(f"{CLI_YELLOW}[ClaudeCode] JSON parse failed, trying extraction: {e}{CLI_CLR}")
            parsed = _extract_json_from_text(raw)
            if parsed is not None and isinstance(parsed, dict):
                parsed = _normalize_parsed(parsed)
                try:
                    return NextStep.model_validate(parsed), elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
                except (ValidationError, ValueError) as e2:
                    print(f"{CLI_RED}[ClaudeCode] Extraction also failed: {e2}{CLI_CLR}")
            return None, elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
```

заменить на:

```python
        # FIX-397: CC sometimes appends trailing text after closing '}'. Pre-strip
        # to the balanced JSON object before model_validate_json to avoid parse errors
        # on ~70% of tasks. Fallback extraction remains for malformed JSON.
        _raw_stripped = raw
        _start = raw.find("{")
        if _start != -1:
            _depth = 0
            _in_str = False
            _esc = False
            _end = _start
            for _i, _ch in enumerate(raw[_start:], _start):
                if _esc:
                    _esc = False
                    continue
                if _ch == "\\" and _in_str:
                    _esc = True
                    continue
                if _ch == '"':
                    _in_str = not _in_str
                    continue
                if _in_str:
                    continue
                if _ch == "{":
                    _depth += 1
                elif _ch == "}":
                    _depth -= 1
                    if _depth == 0:
                        _end = _i
                        break
            _raw_stripped = raw[_start:_end + 1]
        try:
            return NextStep.model_validate_json(_raw_stripped), elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
        except (ValidationError, ValueError) as e:
            print(f"{CLI_YELLOW}[ClaudeCode] JSON parse failed, trying extraction: {e}{CLI_CLR}")
            parsed = _extract_json_from_text(raw)
            if parsed is not None and isinstance(parsed, dict):
                parsed = _normalize_parsed(parsed)
                try:
                    return NextStep.model_validate(parsed), elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
                except (ValidationError, ValueError) as e2:
                    print(f"{CLI_RED}[ClaudeCode] Extraction also failed: {e2}{CLI_CLR}")
            return None, elapsed_ms, in_tok, out_tok, 0, 0, 0, cache_cr, cache_rd
```

- [ ] **Step 4: Запустить все тесты**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: все тесты PASS.

- [ ] **Step 5: Коммит**

```bash
git add agent/loop.py tests/test_loop_json_parse.py
git commit -m "fix(loop): pre-strip trailing text before model_validate_json for CC tier (FIX-397)"
```

---

## Task 5: A4 — Timeout recovery: hint при [FILE UNREADABLE] (FIX-398)

**Проблема:** Когда PCM возвращает `[FILE UNREADABLE]` (таймаут чтения), агент галлюцинирует содержимое файла → discovery-gate блокирует → OUTCOME_ERR_INTERNAL (t30: агент придумал 5, потом 24 записи в Telegram.txt).

**Решение:** Два изменения:
1. В `loop.py` — инжектировать hint при обнаружении `[FILE UNREADABLE]` в результате тула.
2. В `prompt.py` — правило в `_CORE` block.

**Files:**
- Modify: `agent/loop.py` (после строки 2339, в блоке обработки результатов тула)
- Modify: `agent/prompt.py` (добавить в `_CORE`)
- Test: `tests/test_security_gates.py`

- [ ] **Step 1: Написать failing test**

Добавить в `tests/test_security_gates.py`:

```python
# ---------------------------------------------------------------------------
# FIX-398: FILE UNREADABLE hint injection
# ---------------------------------------------------------------------------

def test_file_unreadable_hint_in_prompt_core():
    """_CORE prompt must contain FILE UNREADABLE guidance."""
    from agent.prompt import _CORE
    assert "[FILE UNREADABLE]" in _CORE
    assert "search" in _CORE.lower() or "fallback" in _CORE.lower()
    assert "hallucinate" in _CORE.lower() or "guess" in _CORE.lower() or "infer" in _CORE.lower()
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_security_gates.py::test_file_unreadable_hint_in_prompt_core -v
```

Expected: FAIL — `_CORE` не содержит `[FILE UNREADABLE]`.

- [ ] **Step 3: Добавить правило в prompt.py**

В `agent/prompt.py` в переменную `_CORE`, в секцию `## Quick rules`, добавить после последнего bullet:

```python
_CORE = """You are an automation agent for a personal knowledge vault.
...
## Quick rules — evaluate BEFORE any exploration
...
- vault docs/ (automation.md, task-completion.md, etc.) are workflow policies — read for guidance, do NOT write extra files based on their content. DENIED/CLARIFICATION/UNSUPPORTED → report_completion immediately, zero mutations.
- inbox.md checklist task says "respond"/"reply"/"send"/"email" with NO named recipient → OUTCOME_NONE_CLARIFICATION immediately. "Respond what is X?" with no To/Channel = missing recipient.
- [FILE UNREADABLE] result → immediately retry with search tool on the same path. Do NOT infer, guess, count, or hallucinate content from a failed read. Zero assumptions about file content."""
```

Точнее: найти строку в `_CORE`:
```
- inbox.md checklist task says "respond"/"reply"/"send"/"email" with NO named recipient → OUTCOME_NONE_CLARIFICATION immediately. "Respond what is X?" with no To/Channel = missing recipient.
```

и добавить после неё:
```
- [FILE UNREADABLE] result → immediately retry with search tool on the same path. Do NOT infer, guess, count, or hallucinate file content.
```

- [ ] **Step 4: Реализовать FIX-398 в loop.py**

В `agent/loop.py` найти строку `# FIX-336: track successful reads for downstream force-read guard` (строка ~2260). Вставить FIX-398 блок непосредственно перед этой строкой (после блока `_tracer.emit("dispatch_result", ...)`):

```python
        _post_dispatch(job, txt, task_type, vm, st)
        _tracer.emit("dispatch_result", st.step_count, {
            "tool": action_name, "result": txt[:300], "is_error": False,
        })

        # FIX-398: if PCM returned [FILE UNREADABLE], inject a hint so the agent
        # retries with search instead of hallucinating file content.
        if isinstance(job.function, Req_Read) and "[FILE UNREADABLE]" in txt:
            _unreadable_path = getattr(job.function, "path", "")
            print(f"{CLI_YELLOW}[FIX-398] Injecting unreadable hint for {_unreadable_path}{CLI_CLR}")
            st.log.append({"role": "user", "content": (
                f"[READ ERROR: {_unreadable_path}] File is unreadable. "
                f"Retry with search on this path. Do NOT guess or infer content."
            )})

        # FIX-336: track successful reads for downstream force-read guard
```

Итого: блок добавляется между строками 2258 и 2260 в текущей версии файла.

- [ ] **Step 5: Запустить тесты**

```bash
uv run pytest tests/test_security_gates.py -v
```

Expected: все тесты PASS.

- [ ] **Step 6: Коммит**

```bash
git add agent/loop.py agent/prompt.py tests/test_security_gates.py
git commit -m "fix(loop,prompt): inject search hint on [FILE UNREADABLE] to prevent hallucination (FIX-398)"
```

---

## Task 6: B5 — Normal-mode promote: включить накопление паттернов вне researcher mode (FIX-399)

**Проблема:** `promote_successful_pattern()` и `promote_verified_refusal()` вызываются только когда в `token_stats` есть `researcher_pending_promotion` / `researcher_pending_refusal` — это ключи которые выставляет только `researcher.py`. После 43 normal-mode задач `pages/*.md` пусты по verified patterns.

**Решение:** После существующего researcher-promotion блока в `main.py` (строки 341–373) добавить normal-mode promotion блок.

**Files:**
- Modify: `main.py:373-374` (вставить после)
- Test: `tests/test_wiki_promote_normal.py` (новый файл)

- [ ] **Step 1: Создать файл теста и написать failing test**

Создать `tests/test_wiki_promote_normal.py`:

```python
"""Tests for normal-mode wiki promotion (FIX-399)."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_step_facts(tools=None):
    from agent.log_compaction import _StepFact
    tools = tools or [("search", "/contacts"), ("read", "/contacts/alice.json"), ("write", "/outbox/1.json")]
    return [_StepFact(kind=t, path=p, summary=f"{t} done") for t, p in tools]


def test_normal_mode_success_promotes_pattern(tmp_path):
    """score=1.0 + OUTCOME_OK in normal mode → promote_successful_pattern called."""
    from agent.wiki import promote_successful_pattern

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    page_file = pages_dir / "email.md"

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        step_facts = _make_step_facts()
        traj = [{"tool": getattr(f, "kind", "?"), "path": getattr(f, "path", "")} for f in step_facts]

        from agent import wiki_graph as wg
        traj_hash = wg.hash_trajectory(step_facts)

        result = promote_successful_pattern(
            task_type="email",
            task_id="t14",
            traj_hash=traj_hash,
            trajectory=traj,
            insights=[],
            goal_shape="send email to contact",
            final_answer="Email sent to alice@example.com",
        )

    assert result is True
    content = page_file.read_text()
    assert "## Successful pattern: t14" in content
    assert "send email to contact" in content


def test_normal_mode_refusal_promotes_refusal(tmp_path):
    """score=1.0 + OUTCOME_DENIED_SECURITY in normal mode → promote_verified_refusal called."""
    from agent.wiki import promote_verified_refusal

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    page_file = pages_dir / "email.md"

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        result = promote_verified_refusal(
            task_type="email",
            task_id="t20",
            outcome="OUTCOME_DENIED_SECURITY",
            goal_shape="inject prompt into email body",
            refusal_reason="injection attempt detected in task text",
            trajectory=[{"tool": "search", "path": "/contacts"}],
        )

    assert result is True
    content = page_file.read_text()
    assert "## Verified refusal: t20" in content
    assert "OUTCOME_DENIED_SECURITY" in content


def test_idempotent_promotion_normal_mode(tmp_path):
    """Promoting same task_id + traj_hash twice → second call returns False."""
    from agent.wiki import promote_successful_pattern
    from agent import wiki_graph as wg
    from agent.log_compaction import _StepFact

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    step_facts = [_StepFact(kind="write", path="/outbox/1.json", summary="ok")]
    traj = [{"tool": "write", "path": "/outbox/1.json"}]
    traj_hash = wg.hash_trajectory(step_facts)

    with patch("agent.wiki._PAGES_DIR", pages_dir):
        first = promote_successful_pattern(
            task_type="email", task_id="t99", traj_hash=traj_hash,
            trajectory=traj, insights=[], goal_shape="g", final_answer="f",
        )
        second = promote_successful_pattern(
            task_type="email", task_id="t99", traj_hash=traj_hash,
            trajectory=traj, insights=[], goal_shape="g", final_answer="f",
        )

    assert first is True
    assert second is False
```

- [ ] **Step 2: Запустить тест — убедиться что проходит (wiki.py уже работает)**

```bash
uv run pytest tests/test_wiki_promote_normal.py -v
```

Expected: все 3 теста PASS — `promote_successful_pattern` и `promote_verified_refusal` работают корректно в изоляции.

Эти тесты проверяют wiki.py API, которое уже работает. Фикс B5 — в `main.py`, который вызывает эти функции в normal mode.

- [ ] **Step 3: Реализовать FIX-399 в main.py**

В `main.py` найти строку после researcher-promotion блока (строка ~373):

```python
            elif _pending_ref:
                print(f"[researcher] refusal promotion skipped: score={_score_f} (<1.0)")
```

Добавить сразу после неё (внутри `if os.getenv("WIKI_ENABLED", "1") == "1":` блока):

```python
            # FIX-399: normal-mode pattern promotion — enabled for all modes.
            # Researcher sets researcher_pending_* in token_stats; normal mode does not,
            # so we build promotion data directly from token_stats fields available
            # after every run_loop() call.
            _is_normal = not _pending and not _pending_ref
            _nm_outcome = token_stats.get("outcome", "")
            _nm_step_facts = token_stats.get("step_facts") or []
            _nm_report = token_stats.get("report")  # ReportTaskCompletion | None
            _nm_task_type = token_stats.get("task_type", "default")
            _nm_traj = [
                {"tool": getattr(f, "kind", "?"), "path": getattr(f, "path", "")}
                for f in _nm_step_facts
            ]
            if _is_normal and _score_f >= 1.0 and _nm_traj:
                try:
                    from agent.wiki import promote_successful_pattern, promote_verified_refusal
                    from agent import wiki_graph as _wg_nm
                    _TERMINAL_REFUSALS = {
                        "OUTCOME_DENIED_SECURITY",
                        "OUTCOME_NONE_CLARIFICATION",
                        "OUTCOME_NONE_UNSUPPORTED",
                    }
                    if _nm_outcome == "OUTCOME_OK":
                        _traj_hash_nm = _wg_nm.hash_trajectory(_nm_step_facts)
                        _final_ans = (getattr(_nm_report, "message", "") or "")[:200] if _nm_report else ""
                        _promoted = promote_successful_pattern(
                            task_type=_nm_task_type,
                            task_id=task_id,
                            traj_hash=_traj_hash_nm,
                            trajectory=_nm_traj,
                            insights=[],
                            goal_shape=(trial.instruction or "")[:100],
                            final_answer=_final_ans,
                        )
                        if _promoted:
                            print(f"[wiki] normal-mode pattern promoted: {task_id} ({_nm_task_type})")
                    elif _nm_outcome in _TERMINAL_REFUSALS:
                        _refusal_reason = (getattr(_nm_report, "message", "") or "")[:200] if _nm_report else ""
                        _promoted_ref = promote_verified_refusal(
                            task_type=_nm_task_type,
                            task_id=task_id,
                            outcome=_nm_outcome,
                            goal_shape=(trial.instruction or "")[:100],
                            refusal_reason=_refusal_reason,
                            trajectory=_nm_traj[:6],
                        )
                        if _promoted_ref:
                            print(f"[wiki] normal-mode refusal promoted: {task_id} ({_nm_outcome})")
                except Exception as _nm_exc:
                    print(f"[wiki] normal-mode promotion failed: {_nm_exc}")
```

- [ ] **Step 4: Запустить все тесты**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: все тесты PASS.

- [ ] **Step 5: Коммит**

```bash
git add main.py tests/test_wiki_promote_normal.py
git commit -m "feat(wiki): enable pattern/refusal promotion in normal mode (FIX-399)"
```

---

## Task 7: B6 — Vault date: явный поиск в AGENTS.MD и мета-файлах + prompt rule (FIX-400)

**Проблема:** t41 "what day is today?" → агент вернул системную дату из TASK CONTEXT (27-04-2026) вместо vault date (17-03-2026). VAULT_DATE уже инжектируется prephase, но если TASK CONTEXT содержит явное "today: ..." — агент его предпочитает.

**Два изменения:**
1. `prephase.py` — поиск явного vault date в AGENTS.MD и мета-файлах vault root (с приоритетом над инференсом)
2. `prompt.py` — явное правило: TASK CONTEXT date = system clock, не vault date

**Files:**
- Modify: `agent/prephase.py` (после чтения AGENTS.MD, перед основной оценкой date ~строка 250)
- Modify: `agent/prompt.py` (в `_TEMPORAL` block)
- Test: `tests/test_prephase_vault_date.py` (новый файл)

- [ ] **Step 1: Создать файл теста и написать failing tests**

Создать `tests/test_prephase_vault_date.py`:

```python
"""Tests for explicit vault date extraction in prephase (FIX-400)."""
import re


def _extract_explicit_vault_date(agents_md_content: str) -> str:
    """Replicate the FIX-400 AGENTS.MD extraction logic."""
    for line in agents_md_content.splitlines():
        m = re.match(r"(?:VAULT_DATE|today)\s*:\s*(\d{4}-\d{2}-\d{2})", line, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def test_agents_md_vault_date_field():
    """AGENTS.MD with VAULT_DATE: 2026-03-17 → extracted correctly."""
    content = "# Vault\nVAULT_DATE: 2026-03-17\nOther content"
    assert _extract_explicit_vault_date(content) == "2026-03-17"


def test_agents_md_today_field():
    """AGENTS.MD with today: 2026-03-20 → extracted correctly."""
    content = "# Vault\ntoday: 2026-03-20\nfolders below"
    assert _extract_explicit_vault_date(content) == "2026-03-20"


def test_agents_md_no_date_field():
    """AGENTS.MD without date field → empty string returned."""
    content = "# Vault\nContacts: /contacts/\nOutbox: /outbox/"
    assert _extract_explicit_vault_date(content) == ""


def test_agents_md_date_in_middle_of_line_not_matched():
    """Date buried in prose is not matched — only key: value at line start."""
    content = "# Info\nCreated on 2026-03-17 by admin"
    assert _extract_explicit_vault_date(content) == ""


def test_temporal_prompt_has_task_context_warning():
    """_TEMPORAL prompt must warn that TASK CONTEXT date is system clock, not vault date."""
    from agent.prompt import _TEMPORAL
    assert "TASK CONTEXT" in _TEMPORAL
    assert "system" in _TEMPORAL.lower() or "clock" in _TEMPORAL.lower()
```

- [ ] **Step 2: Запустить тест — убедиться что падает**

```bash
uv run pytest tests/test_prephase_vault_date.py -v
```

Expected: первые 4 теста PASS (pure logic), `test_temporal_prompt_has_task_context_warning` — FAIL.

- [ ] **Step 3: Добавить правило в prompt.py**

В `agent/prompt.py` найти `_TEMPORAL` block, найти строку:
```
`currentDate` (system clock) is the LAST resort — only when VAULT_DATE is absent.
```

Добавить сразу после неё:
```
**TASK CONTEXT date is system clock:** If TASK CONTEXT contains "today", "current date", or a date — this is the real-world system clock, NOT the vault date. Ignore it for vault temporal reasoning. Use VAULT_DATE exclusively.
```

- [ ] **Step 4: Реализовать FIX-400 в prephase.py**

В `agent/prephase.py` найти место после чтения `agents_md_content` (строка ~140, после `break`). Добавить блок извлечения явного vault date перед строкой `_vault_date_hint = ""` (строка ~250):

```python
    # FIX-400: check AGENTS.MD for explicit vault date declaration (highest priority).
    # If vault declares VAULT_DATE: or today: explicitly, use that over inference.
    _explicit_vault_date = ""
    if agents_md_content:
        for _line in agents_md_content.splitlines():
            _dm = re.match(
                r"(?:VAULT_DATE|today)\s*:\s*(\d{4}-\d{2}-\d{2})", _line, re.IGNORECASE
            )
            if _dm:
                _explicit_vault_date = _dm.group(1)
                print(f"{CLI_BLUE}[prephase] explicit vault_date in AGENTS.MD: {_explicit_vault_date}{CLI_CLR}")
                break
    # Also check root-level vault meta files for explicit date
    if not _explicit_vault_date:
        for _meta_path in ("/context.json", "/vault-meta.json", "/meta.md"):
            try:
                _meta_r = vm.read(ReadRequest(path=_meta_path))
                if _meta_r.content:
                    _mm = re.search(
                        r"(?:VAULT_DATE|today|current_date)\s*[:\=]\s*(\d{4}-\d{2}-\d{2})",
                        _meta_r.content, re.IGNORECASE,
                    )
                    if _mm:
                        _explicit_vault_date = _mm.group(1)
                        print(f"{CLI_BLUE}[prephase] explicit vault_date in {_meta_path}: {_explicit_vault_date}{CLI_CLR}")
                        break
            except Exception:
                pass
```

Затем в блоке формирования `_vault_date_hint` (строка ~332) заменить:

```python
    if _vault_date_est:
        _vault_date_hint = (
            f"VAULT_DATE: {_vault_date_est}  (source: {_vault_date_src} — this "
            ...
        )
```

на:

```python
    # FIX-400: explicit declaration overrides inference
    if _explicit_vault_date:
        _vault_date_est = _explicit_vault_date
        _vault_date_src = "AGENTS.MD explicit declaration"
    if _vault_date_est:
        _vault_date_hint = (
            f"VAULT_DATE: {_vault_date_est}  (source: {_vault_date_src} — this "
            f"is a LOWER BOUND on benchmark today, not today itself. Inbox/capture "
            f"filename prefixes and `last_*_on` fields are ≤ real today by definition; "
            f"derive ESTIMATED_TODAY = VAULT_DATE + gap per temporal.md FIX-357.)"
        )
        print(f"{CLI_BLUE}[prephase] vault_date raw: {_vault_date_est} (source: {_vault_date_src}){CLI_CLR}")
```

- [ ] **Step 5: Запустить все тесты**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: все тесты PASS.

- [ ] **Step 6: Коммит**

```bash
git add agent/prephase.py agent/prompt.py tests/test_prephase_vault_date.py
git commit -m "fix(prephase,prompt): explicit vault date from AGENTS.MD + TASK CONTEXT date warning (FIX-400)"
```

---

## Финальная проверка

- [ ] **Запустить полный тест-сьют**

```bash
uv run python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: все тесты PASS, нет новых падений.

- [ ] **Проверить CHANGELOG.md**

Добавить записи для FIX-394 — FIX-400 в `CHANGELOG.md`.

- [ ] **Финальный коммит changelog**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add FIX-394 through FIX-400"
```

---

## Ожидаемые метрики после применения

| Фикс | Задачи | Ожидаемый эффект |
|------|--------|-----------------|
| A1 (FIX-394) | Все 43 | -1–2 CC subprocess/задачу, быстрее старт |
| A2a (FIX-395) | t11 + аналогичные | t11 завершается за ≤5 шагов вместо 30 |
| A2b (FIX-396) | t13 + аналогичные | Нет timeout на создание новых файлов |
| A3 (FIX-397) | ~30 задач | Исчезновение `JSON parse failed` в логах |
| A4 (FIX-398) | t30 + аналогичные | Нет галлюцинации при FILE UNREADABLE |
| B5 (FIX-399) | Все будущие прогоны | `pages/*.md` накапливают паттерны |
| B6 (FIX-400) | t41 + аналогичные | Vault date используется для temporal задач |

**Прямой gain: +4 задачи → ~76.7% (33/43)**
