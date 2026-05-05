---
wiki_sources:
  - docs/architecture/04-dspy-optimization.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, dspy, copro, gepa, optimization, evaluator]
---

# DSPy и оптимизация промптов

Подсистема на базе DSPy, компилирующая три сигнатуры через COPRO/GEPA по собранным примерам.

## Три DSPy-сигнатуры

| Сигнатура | Input | Output | Цель |
|---|---|---|---|
| `ClassifyTask` | `task_text`, `vault_hint` | `task_type` | Классификация |
| `PromptAddendum` | `task_text`, `vault_tree_text`, `vault_context_summary` | `addendum (3-6 bullets)` | Guidance builder |
| `EvaluateCompletion` | `proposed_outcome`, `done_operations`, `task_text`, `skepticism_level` | `approved`, `issues`, `correction_hint` | Reviewer |

## Workflow

```
make run → agент выполняет → собирает примеры:
  data/dspy_examples.jsonl        (builder)
  data/dspy_eval_examples.jsonl   (evaluator)
  data/dspy_contract_examples.jsonl (contract, при is_default=False)

≥30 builder / ≥20 evaluator / ≥30 contract:
  uv run python scripts/optimize_prompts.py --target builder/evaluator/contract

→ data/*_program.json (auto-load на следующем run)
```

## Two-backend architecture

`agent/optimization/` — два взаимозаменяемых бэкенда за общим `OptimizerProtocol`:
- **`CoproBackend`** — `dspy.teleprompt.COPRO`, breadth×depth refinement. Метрика — `.score` от harness.
- **`GepaBackend`** — Genetic-Pareto Reflective Evolution, читает `dspy.Prediction.feedback`. Сохраняет Pareto-фронтир в `data/<target>_program_pareto/`.

Выбор per-target: `OPTIMIZER_<TARGET>` env var (`copro` default).

Feedback детерминированный (без LLM): `agent/optimization/feedback.py`.

## Per-task-type оптимизация

```
data/dspy_examples.jsonl → split by task_type:
  email ≥N → data/prompt_builder_email_program.json
  inbox ≥N → data/prompt_builder_inbox_program.json
  ...
  global  → data/prompt_builder_program.json

Fallback: per-type → global → bare signature
```

## Contract Phase DSPy

- `ExecutorPropose` + `EvaluatorReview` — отдельные сигнатуры для negotiation
- `data/contract_executor_program.json`, `data/contract_evaluator_program.json`
- Fail-open при отсутствии файлов

## Fail-open политика

Любой сбой загрузки скомпилированной программы → fallback to bare signature. Для evaluator — auto-approve. Для builder — return `''` (пустой аддендум). Ничто никогда не блокируется.

## Конфигурация

```bash
OPTIMIZER_DEFAULT=copro
OPTIMIZER_BUILDER=gepa
OPTIMIZER_EVALUATOR=copro
COPRO_BREADTH=4
COPRO_DEPTH=2
GEPA_AUTO=light   # light|medium|heavy
```

## Ключевые файлы

| Файл | Назначение |
|---|---|
| `scripts/optimize_prompts.py` | CLI: `--target builder\|evaluator\|classifier\|contract` |
| `agent/dspy_lm.py` | `DispatchLM` — `dspy.BaseLM` adapter |
| `agent/dspy_examples.py` | `record_example`, загрузчики |
| `agent/optimization/` | `CoproBackend`, `GepaBackend`, `metrics.py`, `feedback.py` |
