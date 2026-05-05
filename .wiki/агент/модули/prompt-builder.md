---
wiki_sources:
  - "agent/prompt_builder.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - prompt
  - dspy
aliases:
  - "build_dynamic_addendum"
  - "DSPy prompt addendum"
---

# Prompt Builder (agent/prompt_builder.py)

DSPy Predict-модуль для генерации task-specific guidance (3-6 bullet-пунктов) перед запуском цикла агента. Fail-open: любая ошибка → пустой addendum.

## Основные характеристики

- Активируется только для типов в `_NEEDS_BUILDER` (из `data/task_types.json`, поле `needs_builder`). `TASK_PREJECT` имеет `needs_builder=False`
- Compiled program из `data/prompt_builder_program.json` (COPRO или GEPA). Fail-open если отсутствует
- Signature `PromptAddendum` включает `graph_context` InputField (FIX-389) — после расширения старые compiled programs могут не иметь этого поля; загрузка через try/except (fail-open)
- **FIX-327**: фильтрация temporal-addenda — `_sanitize_temporal_addendum` удаляет bullets с PAC1/+8/offset когда `task_type='temporal'`

## Связанные концепции

- [[evaluator]] — аналогичная DSPy-архитектура
- [[wiki-graph]] — graph_context инжектируется как InputField
- [[orchestrator]] — вызывает prompt_builder внутри PlannerAgent
