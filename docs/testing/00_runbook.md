# Testing Runbook — pac1-tool

Последовательность для запуска перед `make run`. Каждый шаг — gate; не переходить к следующему пока текущий не зелёный.

| Шаг | Файл | Время | Gate |
|---|---|---|---|
| 1 | 01_preflight.md | 30 сек | Все unit/regression тесты pass |
| 2 | 02_smoke.md | 5 мин | 5 normal-mode задач = 1.00 |
| 3 | 03_researcher_canary.md | 15 мин | 3 researcher-задачи = 1.00 |
| 4 | 04_failure_replay.md | 30 мин | ≥6/8 fail-задач прошлого прогона исправлены |
| 5 | 05_full_benchmark.md | 6-8 час | score ≥ 80% |
| (опц) | 06_dspy_compilation.md | 1 час | evaluator/builder скомпилированы |

## Зачем

8-часовой полный прогон стоит дорого. Цепочка выше ловит регрессии за минуты:
unit-тесты → smoke (canonical normal-mode tasks) → researcher canary → failure
replay (задачи которые исторически фейлили) → full run.

## Quick-run

```bash
uv run pytest tests/ -v && \
uv run python main.py --tasks t01,t02,t10,t14,t34 && \
RESEARCHER_MODE=1 PARALLEL_TASKS=1 uv run python main.py --tasks t04,t06,t12 && \
uv run python main.py --tasks t11,t19,t24,t36,t23,t40,t28,t33 && \
make run
```

## Критерии успеха

- **Step 1 (preflight)**: 100% тестов pass за ≤ 30 сек.
- **Step 2 (smoke)**: 5/5 score=1.00. Любой fail = регрессия в normal-mode pipeline.
- **Step 3 (researcher canary)**: 3/3 score=1.00 + 0 occurrences `INVALID_ARGUMENT` в логах.
- **Step 4 (failure replay)**: ≥6 из 8 fail-задач прошлого прогона теперь green.
- **Step 5 (full run)**: total score ≥ 80% (≥34/43). Регрессия = task которая раньше была 1.0 а стала 0.0.

## Не пропускать

- Шаг 1 — обязателен. Сломанный импорт ломает все 43 задачи в make run.
- Шаг 3 — обязателен если катаешь researcher mode. Smoke в normal mode не покрывает researcher.py.
- Шаги 4 и 6 — опциональны если нет соответствующих изменений (fix-ов в targeting задачах / нового корпуса для DSPy).
