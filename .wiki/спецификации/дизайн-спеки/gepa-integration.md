---
wiki_title: "GEPA Integration & Extensions"
wiki_type: design-spec
wiki_status: developing
wiki_sources:
  - docs/superpowers/specs/2026-04-26-gepa-integration-design.md
  - docs/superpowers/specs/2026-04-26-gepa-trainval-split-design.md
wiki_updated: 2026-05-05
tags: [dspy, gepa, optimization, copro, design]
---

# GEPA Integration & Extensions

## Цель

Прозрачное переключение между COPRO и GEPA на уровне env-переменных (`OPTIMIZER_BUILDER`, `OPTIMIZER_EVALUATOR`, `OPTIMIZER_CLASSIFIER`) для A/B-сравнения и постепенной миграции.

## Архитектурный подход

**Adapter-протокол + два бэкенда** в `agent/optimization/`:

- `OptimizerProtocol` — единый контракт: `compile(program, trainset, metric, save_path, ...)` → `CompileResult`
- `CoproBackend` — переезд существующего `_run_copro_*` без логических изменений
- `GepaBackend` — GEPA с Pareto-фронтиром, ConfidenceAdapter (для open-weight с logprobs), budget resolution

Выбор бэкенда per-target: `OPTIMIZER_<TARGET>` > `OPTIMIZER_DEFAULT` (default `copro`).

## Метрики и feedback

Единый контракт метрики: `dspy.Prediction(score, feedback)`. COPRO берёт только `.score`, GEPA использует оба поля.

Feedback детерминированный (без LLM-вызовов):
- **builder**: сигналы stall/write_scope_violations + score
- **evaluator**: false approve / false reject по типам задач
- **classifier**: misclassified pairs + hint per type

## Train/Val Split для GEPA

При `len(trainset) >= GEPA_MIN_TRAINSET_FOR_SPLIT` (default 20): последние `GEPA_VAL_FRACTION` (default 20%) идут в valset. Логируется в stdout и `optimize_runs.jsonl`.

## Pareto Frontier

GEPA сохраняет `data/<target>_program_pareto/0.json ... index.json` для оффлайн-анализа. Агент загружает только main-программу — без изменений.

## ConfidenceAdapter

Активируется только для `classifier` при `provider in {openrouter_openweight, ollama}`. Для Anthropic/CC — JSONAdapter (нет logprobs в публичном API).

## Env-переменные

```
OPTIMIZER_DEFAULT=copro
OPTIMIZER_BUILDER=gepa
OPTIMIZER_EVALUATOR=copro
OPTIMIZER_CLASSIFIER=gepa
GEPA_AUTO=light          # light|medium|heavy (auto budget)
GEPA_BUDGET_OVERRIDE=    # "max_full_evals=30" или "max_metric_calls=400"
GEPA_VAL_FRACTION=0.2
GEPA_MIN_TRAINSET_FOR_SPLIT=20
```

## Критерии успеха

- `OPTIMIZER_*=copro` — поведение эквивалентно pre-миграции
- `OPTIMIZER_BUILDER=gepa` — сохраняет main + Pareto, загружается в `agent/prompt_builder.py`
- Юнит-тесты `test_optimization_feedback.py`, `test_optimization_backend_select.py`, `test_optimization_budget.py` зелёные
