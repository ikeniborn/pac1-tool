---
wiki_sources:
  - "agent/agents/planner_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - orchestrator
  - dspy
  - dispatch
aliases:
  - "PlannerAgent"
---

# PlannerAgent (agent/agents/planner_agent.py)

Агент планирования в мультиагентной архитектуре. Принимает `PlannerInput` (классификацию, prephase-контекст, wiki-контекст) и производит `ExecutionPlan` с финальным system prompt, DSPy-аддендумом и опциональным контрактом.

## Основные характеристики

- **Конструктор:** принимает `model`, `cfg`; опциональные флаги `prompt_builder_enabled` и `contract_enabled` (если не переданы — читаются из `PROMPT_BUILDER_ENABLED` / `CONTRACT_ENABLED`).
- **Метод `run(inp: PlannerInput) → ExecutionPlan`** — четыре этапа:
  1. Базовый system prompt через `build_system_prompt(task_type)`.
  2. Инжекция секции графа знаний (`inp.wiki_context.graph_section`) в конец промпта.
  3. DSPy-аддендум через `build_dynamic_addendum(...)` (ленивый импорт, fail-open при ошибке). Добавляется как `## TASK-SPECIFIC GUIDANCE`.
  4. Контрактная фаза через `negotiate_contract(...)` (ленивый импорт, gated `CONTRACT_ENABLED`).
- Мутирует `inp.prephase.log[0]["content"]` и `inp.prephase.preserve_prefix[0]["content"]` на финальный промпт.
- **Возвращает** `ExecutionPlan`: `base_prompt`, `addendum`, `contract`, `route="EXECUTE"`, `in_tokens`, `out_tokens`.
- Env: `PROMPT_BUILDER_MAX_TOKENS` (default 500), `CONTRACT_MAX_ROUNDS` (default 3).

## Связанные концепции

- [[prompt-builder]] — `build_dynamic_addendum` для DSPy-аддендума
- [[contract-phase]] — `negotiate_contract` для контрактной фазы
- [[prompt]] — `build_system_prompt` базовый промпт
- [[wiki-graph]] — graph_section вставляется в промпт
