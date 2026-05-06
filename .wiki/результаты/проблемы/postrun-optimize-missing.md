---
wiki_title: "postrun optimize [missing] — DSPy не компилируется"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04.md
  - docs/results/run_analysis_2026-05-04_v2.md
  - docs/results/run_analysis_2026-05-04_v3.md
wiki_domain: результаты
wiki_type: system-problem
tags: [dspy, postrun, optimize, system-problem, missing-program]
---

# postrun optimize [missing] — DSPy не компилируется

**Статус:** частично решена (v3: step_facts фикс). postrun optimize всё ещё падает.  
**Влияние:** evaluator и builder работают на базовых промптах без оптимизации.

## Симптом

`[postrun] optimize failed (exit 1)` — каждый прогон в v1/v2. Нет traceback в логе.  
Следствие: `eval_program = [missing]`, `builder_program = [missing]`.

## Две отдельные проблемы

### 1. step_facts сериализация (v1, решена в v2/v3)

**Ошибка v1:**
```
step_facts.0: Input should be a valid dictionary
  input_value=_StepFact(kind='read', ...), input_type=_StepFact
```
`_StepFact` объекты не сериализуются в `dict` при создании `ExecutionResult`.  
Следствие: DSPy примеры не накапливались (0 в v1).

**Статус:** в v2/v3 ошибка не воспроизвелась — DSPy примеры накапливаются нормально (21 → 50 в v3).

### 2. postrun optimize exit 1 (продолжается)

DSPy optimizer падает с exit 1 без traceback. Точная причина неизвестна.  
Следствие: даже при 50 накопленных примерах (v3) программы остаются `[missing]`.

**Рекомендация:** включить полный traceback — `uv run python scripts/optimize_prompts.py --target all 2>&1`.

## Влияние на результаты

| Версия | DSPy примеры | Compiled programs | Влияние |
|--------|-------------|-------------------|---------|
| v1 | 0 | missing | Нет вклада |
| v2 | 21 | missing | Нет вклада |
| v3 | 50 | `['prompt_builder_program.json']` | Частичный |
| v4 | 75 → 213 | `['prompt_builder_program.json']` | builder оптимизирован |

В v4 появился скомпилированный `prompt_builder_program.json` — это одна из причин роста с 16% до 53%.

## Рекомендации

1. Включить traceback: обернуть `optimize_prompts.py` вызов в try/except с полным выводом.
2. После v3 с 50 примерами запустить `uv run python scripts/optimize_prompts.py --target all` вручную.
3. Проверить почему evaluator program не компилируется даже при 50 примерах.

## Связи

- [[результаты/сессии/run-v1-v2-v3]] — контекст проблемы
- [[результаты/сессии/run-v4-all-tasks]] — v4 с частично решённой проблемой
