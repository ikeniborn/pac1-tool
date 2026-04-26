# GEPA Train/Val Split — Design Spec

**Date:** 2026-04-26
**Scope:** Add deterministic train/val split inside `GepaBackend.compile()` to silence DSPy's "No valset provided" warning and improve generalization of GEPA-optimized prompts.

**Source warning:**
```
WARNING dspy.teleprompt.gepa.gepa: No valset provided; Using trainset as valset.
This is useful as an inference-time scaling strategy ... overfit prompts to the
provided trainset. In order to ensure generalization ... please provide separate
trainset and valset.
```

## 1. Goals / Non-Goals

**Goals:**
- Передавать `valset` в `GEPA.compile()` когда `len(trainset) ≥ GEPA_MIN_TRAINSET_FOR_SPLIT`.
- Сохранить recency: последние `GEPA_VAL_FRACTION` примеров идут в val, остальное — train.
- Логировать факт split'а в stdout и в `optimize_runs.jsonl`.
- Не трогать CoproBackend и OptimizerProtocol (Copro не использует valset).

**Non-goals:**
- Cross-validation, k-fold, hold-out test set.
- Stratified-by-task_type split (рассмотрено, отклонено: per-task_type passes уже узкие).
- Случайное перемешивание (детерминированное по позиции достаточно).
- Изменение поведения CoproBackend.

## 2. Architecture

Изменения локализованы в `agent/optimization/gepa_backend.py`. OptimizerProtocol получает один новый optional kwarg `emit` для логирования split-event'а.

### 2.1 Protocol change

```python
# agent/optimization/base.py
class OptimizerProtocol(Protocol):
    def compile(
        self,
        program,
        trainset,
        metric,
        save_path,
        log_label,
        *,
        task_lm,
        prompt_lm,
        adapter,
        threads,
        emit: Callable[[str, dict], None] | None = None,  # NEW
    ) -> CompileResult: ...
```

CoproBackend получает `emit=None` по умолчанию — не использует.

### 2.2 GepaBackend split logic

В начале `compile()` (до `dspy.configure`):

```python
val_fraction = float(os.environ.get("GEPA_VAL_FRACTION", "0.2"))
min_for_split = int(os.environ.get("GEPA_MIN_TRAINSET_FOR_SPLIT", "20"))
n = len(trainset)

if n >= min_for_split and 0 < val_fraction < 1:
    cut = max(1, int(n * (1 - val_fraction)))
    train, val = trainset[:cut], trainset[cut:]
    msg = f"trainset={len(train)}, valset={len(val)} (last {int(val_fraction*100)}%)"
    payload = {"target": log_label, "trainset_size": len(train),
               "valset_size": len(val), "fraction": val_fraction}
else:
    train, val = trainset, None
    reason = "below_min" if n < min_for_split else "fraction_invalid"
    msg = f"split skipped ({reason}, n={n}); trainset-as-valset"
    payload = {"target": log_label, "trainset_size": n, "valset_size": 0,
               "skipped_reason": reason, "fraction": val_fraction}

print(f"[optimize] gepa: {msg}")
if emit is not None:
    emit("split", payload)

# далее: configure adapter, build teleprompter
compiled = teleprompter.compile(program, trainset=train, valset=val)
```

Защитные проверки (clamping):
- `val_fraction <= 0` или `>= 1` → split skipped (`fraction_invalid`).
- `int(n * (1 - val_fraction)) == 0` → cut = 1 (минимум 1 пример в train).

### 2.3 _run_target wiring

`scripts/optimize_prompts.py:_run_target` пробрасывает `emit=_emit`:

```python
backend.compile(
    program_factory(),
    trainset, metric, save_path, log_label,
    task_lm=task_lm, prompt_lm=prompt_lm, adapter=adapter,
    threads=_COPRO_THREADS, emit=_emit,
)
```

`_emit` — существующий module-level helper (`OptimizeLogger.emit` через guard).

## 3. Configuration

Две новые env-переменные в `.env.example` (секция GEPA):

```bash
# Доля trainset, попадающая в valset (детерминированно: последние N%).
# 0.0 < x < 1.0. Применяется только в GepaBackend.
GEPA_VAL_FRACTION=0.2

# Минимальный размер trainset, ниже которого split не делается
# (val=None → GEPA фолбэчит на trainset-as-valset с warning'ом).
GEPA_MIN_TRAINSET_FOR_SPLIT=20
```

**Resolution:** оба читаются на каждом вызове `compile()`. Невалидные значения (`ValueError` при float/int) → используется default.

## 4. Logging

**stdout:**
- Split применён: `[optimize] gepa: trainset=80, valset=20 (last 20%)`
- Split пропущен: `[optimize] gepa: split skipped (below_min, n=12); trainset-as-valset`

**JSONL** (`data/optimize_runs.jsonl`):
```json
{"event": "split", "target": "builder/global", "trainset_size": 80, "valset_size": 20, "fraction": 0.2}
{"event": "split", "target": "builder/email", "trainset_size": 12, "valset_size": 0, "fraction": 0.2, "skipped_reason": "below_min"}
```

## 5. Tests

Новый файл `tests/test_optimization_split.py` (быстрый, не slow):

| # | Сценарий | Env | Trainset | Ожидание |
|---|----------|-----|----------|----------|
| 1 | Default split | — | 25 | train=20, val=5 |
| 2 | Below min | — | 15 | train=15, val=None, skipped=below_min |
| 3 | Custom fraction | `GEPA_VAL_FRACTION=0.3` | 30 | train=21, val=9 |
| 4 | Custom min | `GEPA_MIN_TRAINSET_FOR_SPLIT=10` | 12 | train=9, val=3 (`int(12*0.8)=9`) |
| 5 | Invalid fraction | `GEPA_VAL_FRACTION=0` | 30 | skipped=fraction_invalid |
| 6 | Emit called | — | 25 | emit получил (`"split"`, payload-dict) |
| 7 | Emit None safe | — | 25 | без emit ничего не падает |

Реализация через прямую функцию `_split_trainset(trainset, val_fraction, min_for_split) -> tuple[list, list | None, str, dict]` в `gepa_backend.py` (module-level, не метод). Возвращает `(train, val, log_msg, payload)`. `compile()` вызывает её, печатает `log_msg`, эмитит `payload`. Тесты вызывают `_split_trainset` напрямую — без `dspy.teleprompt.GEPA`, без `emit`-callable.

## 6. Migration / Rollback

- **Backward-compat:** при `len(trainset) < 20` поведение идентично текущему.
- **Disable:** `GEPA_VAL_FRACTION=0` отключает split (skipped=fraction_invalid).
- **Rollback:** один git revert по точечному коммиту.

## 7. Acceptance

- [ ] Прогон GEPA с trainset ≥ 20 не печатает WARNING про "No valset provided".
- [ ] Прогон с trainset < 20 печатает `split skipped (below_min, ...)` и WARNING сохраняется (это OK).
- [ ] Все 7 unit-тестов в `test_optimization_split.py` проходят.
- [ ] `optimize_runs.jsonl` содержит event `"split"` после прогона GEPA.
- [ ] Существующие тесты не падают, pre-existing failures без изменений.

## 8. Out of scope / Follow-ups

- Stratified split по task_type — добавить если global-pass начнёт выдавать неравномерное распределение типов в val.
- Random shuffle с seed — добавить если будет наблюдаться смещение по recency (например, последние 20% корпуса все одного task_type).
- Отдельный валидационный корпус (`data/dspy_eval_examples_holdout.jsonl`) — текущий split берёт из того же файла.
