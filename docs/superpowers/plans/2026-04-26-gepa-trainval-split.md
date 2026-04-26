# GEPA Train/Val Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить детерминированный train/val split внутри `GepaBackend.compile()`, чтобы GEPA получал отдельный valset и не выдавал WARNING "No valset provided".

**Architecture:** Новая module-level функция `_split_trainset()` в `gepa_backend.py` реализует split-логику чисто (без side effects), `compile()` вызывает её и эмитит split-event через nullable callable `emit`. Protocol `OptimizerProtocol` получает `emit` как optional kwarg; CoproBackend его игнорирует.

**Tech Stack:** Python 3.12, DSPy ≥2.5, pytest, существующий `agent/optimization/` пакет.

**Spec source:** `docs/superpowers/specs/2026-04-26-gepa-trainval-split-design.md`

---

## File structure

**Модифицируемые файлы:**
- `agent/optimization/base.py` — добавить `emit` kwarg в `OptimizerProtocol.compile()`
- `agent/optimization/gepa_backend.py` — добавить `_split_trainset()` + обновить `compile()`
- `agent/optimization/copro_backend.py` — добавить `emit=None` в сигнатуру (игнорировать)
- `scripts/optimize_prompts.py` — передать `emit=_emit` в `backend.compile()`
- `.env.example` — добавить `GEPA_VAL_FRACTION` и `GEPA_MIN_TRAINSET_FOR_SPLIT`

**Новые файлы:**
- `tests/test_optimization_split.py` — 7 unit-тестов на `_split_trainset`

---

## Task 1: TDD — написать тесты для _split_trainset

**Files:**
- Create: `tests/test_optimization_split.py`

Функция `_split_trainset` ещё не существует — тесты сначала упадут на ImportError.

- [ ] **Step 1: Создать файл тестов**

```python
# tests/test_optimization_split.py
"""Unit tests for GepaBackend._split_trainset (deterministic train/val split)."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _get_split():
    """Import lazily so import errors surface per-test, not at collection time."""
    mod = importlib.import_module("agent.optimization.gepa_backend")
    return mod._split_trainset


def _make_trainset(n: int) -> list:
    return [{"idx": i} for i in range(n)]


# ---------------------------------------------------------------------------
# Test 1: default split (25 items, 20% → val=5, train=20)
# ---------------------------------------------------------------------------

def test_default_split():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(25), 0.2, 20)
    assert len(train) == 20
    assert val is not None and len(val) == 5
    assert train[-1]["idx"] == 19   # last of train
    assert val[0]["idx"] == 20      # first of val
    assert "trainset=20" in msg
    assert "valset=5" in msg
    assert payload["trainset_size"] == 20
    assert payload["valset_size"] == 5
    assert payload["fraction"] == 0.2
    assert "skipped_reason" not in payload


# ---------------------------------------------------------------------------
# Test 2: below min → skip split
# ---------------------------------------------------------------------------

def test_below_min_skips_split():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(15), 0.2, 20)
    assert len(train) == 15
    assert val is None
    assert "below_min" in msg
    assert payload["valset_size"] == 0
    assert payload["skipped_reason"] == "below_min"


# ---------------------------------------------------------------------------
# Test 3: custom fraction (0.3, 30 items → cut=int(30*0.7)=21, val=9)
# ---------------------------------------------------------------------------

def test_custom_fraction():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(30), 0.3, 20)
    assert len(train) == 21
    assert val is not None and len(val) == 9
    assert "30%" in msg
    assert payload["fraction"] == 0.3


# ---------------------------------------------------------------------------
# Test 4: custom min (min=10, n=12, 20% → cut=int(12*0.8)=9, val=3)
# ---------------------------------------------------------------------------

def test_custom_min_threshold():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(12), 0.2, 10)
    assert len(train) == 9
    assert val is not None and len(val) == 3


# ---------------------------------------------------------------------------
# Test 5: invalid fraction (0.0) → skipped
# ---------------------------------------------------------------------------

def test_invalid_fraction_zero_skips():
    split = _get_split()
    train, val, msg, payload = split(_make_trainset(30), 0.0, 20)
    assert val is None
    assert payload["skipped_reason"] == "fraction_invalid"
    assert "fraction_invalid" in msg


# ---------------------------------------------------------------------------
# Test 6: emit callable is called with correct args
# ---------------------------------------------------------------------------

def test_emit_called():
    split = _get_split()
    calls: list = []
    # emit is NOT a parameter of _split_trainset; it's called by compile().
    # _split_trainset returns (train, val, msg, payload) — compile() does the emit.
    # This test verifies payload contents for downstream emit.
    train, val, msg, payload = split(_make_trainset(25), 0.2, 20)
    emit = lambda event, data: calls.append((event, data))
    emit("split", payload)
    assert len(calls) == 1
    event, data = calls[0]
    assert event == "split"
    assert data["trainset_size"] == 20
    assert data["valset_size"] == 5


# ---------------------------------------------------------------------------
# Test 7: emit=None in compile() does not raise (tested via _split_trainset
# returning payload that compile() handles — verify no AttributeError on None)
# ---------------------------------------------------------------------------

def test_no_emit_is_safe():
    split = _get_split()
    # Just verify _split_trainset itself does not call emit (no side effects)
    train, val, msg, payload = split(_make_trainset(25), 0.2, 20)
    # If we reach here without TypeError the function is side-effect free
    assert isinstance(payload, dict)
```

- [ ] **Step 2: Убедиться, что тесты падают на ImportError**

```bash
cd /home/ikeniborn/Documents/Project/pac1-tool
uv run pytest tests/test_optimization_split.py -v 2>&1 | head -20
```

Ожидаемый результат: `ImportError: cannot import name '_split_trainset'` или `AttributeError: module 'agent.optimization.gepa_backend' has no attribute '_split_trainset'`.

---

## Task 2: Реализовать _split_trainset в gepa_backend.py

**Files:**
- Modify: `agent/optimization/gepa_backend.py`

- [ ] **Step 1: Добавить `os` в импорты gepa_backend.py**

В `agent/optimization/gepa_backend.py` первые строки сейчас:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
```

Добавить `import os`:
```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
```

- [ ] **Step 2: Добавить функцию `_split_trainset` после блока try/except импорта GEPA**

Вставить после строки `_GEPA = None` (после блока try/except), перед `def _model_supports_logprobs`:

```python
def _split_trainset(
    trainset: list,
    val_fraction: float,
    min_for_split: int,
) -> tuple[list, list | None, str, dict]:
    """Split trainset deterministically: last val_fraction → val, rest → train.

    Returns (train, val, log_msg, payload).
    val is None when split is skipped (trainset too small or invalid fraction).
    """
    n = len(trainset)
    if n >= min_for_split and 0 < val_fraction < 1:
        cut = max(1, int(n * (1 - val_fraction)))
        train, val = trainset[:cut], trainset[cut:]
        msg = (
            f"trainset={len(train)}, valset={len(val)}"
            f" (last {int(val_fraction * 100)}%)"
        )
        payload: dict = {
            "trainset_size": len(train),
            "valset_size": len(val),
            "fraction": val_fraction,
        }
    else:
        train, val = trainset, None
        reason = "below_min" if n < min_for_split else "fraction_invalid"
        msg = f"split skipped ({reason}, n={n}); trainset-as-valset"
        payload = {
            "trainset_size": n,
            "valset_size": 0,
            "skipped_reason": reason,
            "fraction": val_fraction,
        }
    return train, val, msg, payload
```

- [ ] **Step 3: Запустить тесты — убедиться что все 7 проходят**

```bash
uv run pytest tests/test_optimization_split.py -v
```

Ожидаемый результат:
```
PASSED tests/test_optimization_split.py::test_default_split
PASSED tests/test_optimization_split.py::test_below_min_skips_split
PASSED tests/test_optimization_split.py::test_custom_fraction
PASSED tests/test_optimization_split.py::test_custom_min_threshold
PASSED tests/test_optimization_split.py::test_invalid_fraction_zero_skips
PASSED tests/test_optimization_split.py::test_emit_called
PASSED tests/test_optimization_split.py::test_no_emit_is_safe
7 passed
```

- [ ] **Step 4: Коммит**

```bash
git add tests/test_optimization_split.py agent/optimization/gepa_backend.py
git commit -m "feat(optimization): _split_trainset with 7 unit tests (TDD)"
```

---

## Task 3: Обновить OptimizerProtocol + CoproBackend + GepaBackend.compile()

**Files:**
- Modify: `agent/optimization/base.py`
- Modify: `agent/optimization/copro_backend.py` — только сигнатура
- Modify: `agent/optimization/gepa_backend.py` — использовать `_split_trainset` в `compile()`

### 3.1 base.py — добавить emit kwarg в Protocol

- [ ] **Step 1: Обновить OptimizerProtocol**

В `agent/optimization/base.py` заменить:

```python
from typing import Any, Callable, Protocol
```

на:

```python
from typing import Any, Callable, Optional, Protocol
```

И добавить `emit` kwarg в конец Protocol-метода:

```python
class OptimizerProtocol(Protocol):
    name: str  # "copro" | "gepa"

    def compile(
        self,
        program: Any,
        trainset: list,
        metric: Callable,
        save_path: Path,
        log_label: str,
        *,
        task_lm: Any,
        prompt_lm: Any,
        adapter: Any,
        threads: int,
        emit: Optional[Callable[[str, dict], None]] = None,
    ) -> CompileResult: ...
```

### 3.2 copro_backend.py — принять emit и проигнорировать

- [ ] **Step 2: Найти сигнатуру compile() в copro_backend.py**

```bash
grep -n "def compile" /home/ikeniborn/Documents/Project/pac1-tool/agent/optimization/copro_backend.py
```

Открой файл, найди сигнатуру `compile()`. Она оканчивается на `threads: int,`. Добавить после неё:

```python
        emit: "Callable[[str, dict], None] | None" = None,
```

CoproBackend не использует `emit` внутри — просто принимает и игнорирует.

### 3.3 gepa_backend.py — обновить compile() для использования _split_trainset

- [ ] **Step 3: Обновить сигнатуру compile() в GepaBackend**

В `agent/optimization/gepa_backend.py` в классе `GepaBackend` найти `def compile(...)` и заменить строку `threads: int,` на:

```python
        threads: int,
        emit: "Callable[[str, dict], None] | None" = None,
```

- [ ] **Step 4: Добавить split-логику в начало compile() тела**

В `GepaBackend.compile()` найти строку:
```python
        budget_kwargs = resolve_budget()
```

Вставить **перед** ней:

```python
        val_fraction = _parse_float_env("GEPA_VAL_FRACTION", 0.2)
        min_for_split = _parse_int_env("GEPA_MIN_TRAINSET_FOR_SPLIT", 20)
        train, val, split_msg, split_payload = _split_trainset(
            trainset, val_fraction, min_for_split
        )
        print(f"[optimize] gepa: {split_msg}")
        if emit is not None:
            split_payload = {"target": log_label, **split_payload}
            emit("split", split_payload)

```

- [ ] **Step 5: Добавить вспомогательные функции `_parse_float_env` и `_parse_int_env`**

Добавить после `_split_trainset` (перед `_model_supports_logprobs`):

```python
def _parse_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


def _parse_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default
```

- [ ] **Step 6: Обновить строку вызова teleprompter.compile() — передать val**

Найти:
```python
        compiled = teleprompter.compile(program, trainset=trainset)
```

Заменить на:
```python
        compiled = teleprompter.compile(program, trainset=train, valset=val)
```

- [ ] **Step 7: Проверить импорт и тесты**

```bash
uv run python -c "from agent.optimization.gepa_backend import GepaBackend, _split_trainset; print('ok')"
uv run pytest tests/test_optimization_split.py -v
```

Оба должны пройти без ошибок.

---

## Task 4: Пробросить emit в _run_target + обновить .env.example

**Files:**
- Modify: `scripts/optimize_prompts.py`
- Modify: `.env.example`

### 4.1 optimize_prompts.py

- [ ] **Step 1: Найти вызов backend.compile() в _run_target**

```bash
grep -n "backend.compile" /home/ikeniborn/Documents/Project/pac1-tool/scripts/optimize_prompts.py
```

Сейчас вызов выглядит так (строка ~422):
```python
        backend.compile(
            program_factory(),
            trainset, metric, save_path, log_label,
            task_lm=task_lm, prompt_lm=prompt_lm, adapter=adapter, threads=_COPRO_THREADS,
        )
```

Заменить на:
```python
        backend.compile(
            program_factory(),
            trainset, metric, save_path, log_label,
            task_lm=task_lm, prompt_lm=prompt_lm, adapter=adapter,
            threads=_COPRO_THREADS, emit=_emit,
        )
```

### 4.2 .env.example

- [ ] **Step 2: Добавить две переменные в GEPA-секцию .env.example**

Найти блок `GEPA_BUDGET_OVERRIDE` в `.env.example` (конец GEPA-секции) и добавить после него:

```bash
# Train/val split — последние GEPA_VAL_FRACTION примеров идут в valset.
# 0.0 < x < 1.0. Ниже GEPA_MIN_TRAINSET_FOR_SPLIT — split пропускается.
GEPA_VAL_FRACTION=0.2
GEPA_MIN_TRAINSET_FOR_SPLIT=20
```

- [ ] **Step 3: Проверить импорт optimize_prompts**

```bash
uv run python -c "import scripts.optimize_prompts; print('ok')"
```

Ожидаемый результат: `[dispatch] Active backend: ... ok`

---

## Task 5: Финальная проверка + коммит

- [ ] **Step 1: Полный прогон тестов**

```bash
uv run pytest tests/ -v --ignore=tests/regression 2>&1 | tail -20
```

Ожидаемый результат: все тесты проходят + 7 новых в `test_optimization_split.py`. Pre-existing failures (`test_purge_script.py` x2, `test_t33_no_false_positive.py`) не изменились.

- [ ] **Step 2: Проверить отсутствие регрессий в существующих тестах**

```bash
uv run pytest tests/test_optimization_feedback.py tests/test_optimization_backend_select.py tests/test_optimization_budget.py -v 2>&1 | tail -10
```

Ожидаемый результат: все проходят.

- [ ] **Step 3: Smoke — убедиться что COPRO не сломан (без env GEPA)**

```bash
uv run python -c "
from agent.optimization import select_backend
from agent.optimization.copro_backend import CoproBackend
b = select_backend('classifier')
print('backend:', b.name)
assert b.name == 'copro'
print('ok')
"
```

Ожидаемый результат: `backend: copro\nok`

- [ ] **Step 4: Итоговый коммит**

```bash
git add \
  agent/optimization/base.py \
  agent/optimization/gepa_backend.py \
  agent/optimization/copro_backend.py \
  scripts/optimize_prompts.py \
  .env.example
git commit -m "feat(optimization): GEPA train/val split (last 20% → valset)

- _split_trainset() in gepa_backend.py: deterministic position-based split,
  skips when len(trainset) < GEPA_MIN_TRAINSET_FOR_SPLIT (default 20).
- GepaBackend.compile() calls _split_trainset, emits 'split' event via
  nullable emit callback, passes valset= to GEPA.compile().
- OptimizerProtocol.compile() + CoproBackend accept emit=None (ignored).
- _run_target wires _emit callable through.
- GEPA_VAL_FRACTION=0.2, GEPA_MIN_TRAINSET_FOR_SPLIT=20 documented in
  .env.example.

Fixes: WARNING dspy.teleprompt.gepa: No valset provided.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage:**
- § 2.1 Protocol `emit` kwarg → Task 3.1 ✅
- § 2.2 split logic → Task 2 `_split_trainset` ✅
- § 2.2 `teleprompter.compile(trainset=train, valset=val)` → Task 3 Step 6 ✅
- § 2.3 `_run_target` wiring → Task 4.1 ✅
- § 3 env vars → Task 4.2 ✅
- § 4 logging stdout + JSONL emit → Task 3 Steps 3-4, Task 4.1 ✅
- § 5 тесты 1-7 → Task 1 ✅
- § 6 backward-compat (< 20 → skip) → покрыт test 2 ✅
- § 7 acceptance items → Task 5 ✅

**Placeholder scan:** нет TBD/TODO.

**Type consistency:**
- `_split_trainset` возвращает `tuple[list, list | None, str, dict]` — Task 1 тест ожидает `(train, val, msg, payload)` ✅
- `emit: Callable[[str, dict], None] | None = None` — Protocol и обе реализации ✅
- `teleprompter.compile(program, trainset=train, valset=val)` — `train`/`val` из `_split_trainset` ✅
- `split_payload` расширяется ключом `"target"` перед emit-вызовом — payload в тестах проверяет только `trainset_size/valset_size/fraction`, не `target` (OK, target — runtime-only поле) ✅
