---
wiki_title: "GEPA Integration Implementation Plan"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-04-26-gepa-integration.md"
wiki_updated: "2026-05-06"
tags: [gepa, copro, dspy, optimizer, feedback]
---

# GEPA Integration Implementation Plan

**Источник:** `docs/superpowers/plans/2026-04-26-gepa-integration.md`

## Цель

Внедрить GEPA как альтернативный DSPy-оптимизатор рядом с COPRO для трёх цепочек (`prompt_builder`, `evaluator`, `classifier`) с env-driven per-target переключением, детерминированным feedback и опциональным ConfidenceAdapter для classifier.

## Архитектура

Новый пакет `agent/optimization/` с adapter-протоколом `OptimizerProtocol` и двумя бэкендами (`CoproBackend`, `GepaBackend`). `scripts/optimize_prompts.py` сжимается до CLI + диспатчера. Метрики возвращают `dspy.Prediction(score, feedback)`; feedback строится по правилам без доп LLM-вызовов.

**Tech Stack:** Python 3.12, DSPy ≥2.5 (с extra `[gepa]`), pytest, pydantic.

## Структура файлов

**Новые:**
- `agent/optimization/__init__.py` — re-exports + `select_backend()`
- `agent/optimization/base.py` — `OptimizerProtocol`, `CompileResult`, `BackendError`
- `agent/optimization/logger.py` — `OptimizeLogger`
- `agent/optimization/feedback.py` — детерминированные feedback builders
- `agent/optimization/metrics.py` — метрики, возвращающие `dspy.Prediction`
- `agent/optimization/budget.py` — `resolve_budget()`
- `agent/optimization/copro_backend.py` — `CoproBackend`
- `agent/optimization/gepa_backend.py` — `GepaBackend`
- `tests/test_optimization_feedback.py`
- `tests/test_optimization_backend_select.py`
- `tests/test_optimization_budget.py`
- `tests/test_optimization_smoke.py` (slow-marked)

## Ключевые паттерны

### Backend selection
`select_backend(target_label)` читает `OPTIMIZER_{TARGET}` env, fallback на `OPTIMIZER_DEFAULT=copro`. Label может быть `builder/global` — первый сегмент используется.

### Feedback builders
`build_builder_feedback(ex, pred, score)` — детерминистический (~400 chars): проверяет `bullet_count`, `stall_detected`, `write_scope_violations`, task-type-specific hints. Аналогично для evaluator и classifier.

### Pareto frontier (GEPA)
После compile — `_extract_pareto(compiled, teleprompter)` → `_save_pareto(programs, save_path)`. Сохраняется в `data/<target>_program_pareto/{0..N}.json` + `index.json`. Агент загружает только основную программу.

### ConfidenceAdapter routing
Используется только для classifier + когда модель поддерживает logprobs (OpenRouter/Ollama). Anthropic provider → fallback.

## Задачи (13 tasks)

| Task | Содержание |
|------|-----------|
| 1 | Scaffold optimization package + protocol + logger move |
| 2 | Перенос метрик в `metrics.py` |
| 3 | `feedback.py` + unit tests (TDD) |
| 4 | `stall_detected`/`write_scope_violations` в `record_example` |
| 5 | `CoproBackend` + унификация `_run_target` |
| 6 | `budget.py` + tests (TDD) |
| 7 | `GepaBackend` basic + `dspy[gepa]` dep |
| 8 | Backend selection routing + tests |
| 9 | Pareto frontier persistence |
| 10 | ConfidenceAdapter routing + dispatch.py logprobs |
| 11 | Smoke test (slow) — оба backend |
| 12 | Documentation updates |
| 13 | Final verification |

## Env-переменные

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `OPTIMIZER_DEFAULT` | `copro` | Fallback для всех targets |
| `OPTIMIZER_BUILDER` | inherit | Override для builder |
| `OPTIMIZER_EVALUATOR` | inherit | Override для evaluator |
| `OPTIMIZER_CLASSIFIER` | inherit | Override для classifier |
| `GEPA_AUTO` | `light` | `light\|medium\|heavy` budget preset |
| `GEPA_BUDGET_OVERRIDE` | unset | Fine-grained: `max_full_evals=N` |

## Критерии готовности

- `OPTIMIZER_*=copro` parity с предыдущим поведением
- `OPTIMIZER_BUILDER=gepa` работает, сохраняет main + Pareto
- Unit tests `test_optimization_feedback`, `test_optimization_backend_select`, `test_optimization_budget` — зелёные
- Документация обновлена

## Связанные планы

- [[gepa-trainval-split]] — Task 7: детерминированный train/val split внутри `GepaBackend.compile()`
