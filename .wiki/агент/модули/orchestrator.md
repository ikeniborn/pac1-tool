---
wiki_sources:
  - "agent/orchestrator.py"
  - "agent/__init__.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - orchestrator
  - dispatch
aliases:
  - "run_agent"
  - "Hub-and-Spoke pipeline"
---

# Orchestrator (agent/orchestrator.py)

Точка входа в пайплайн выполнения задачи PAC1. Реализует Hub-and-Spoke архитектуру: координирует специализированных агентов через типизированные контракты, не дублируя логику в самом файле. `agent/__init__.py` — тонкий псевдоним для обратной совместимости.

## Основные характеристики

- **Экспортирует:** `run_agent(router, harness_url, task_text) -> dict` и `write_wiki_fragment(...)`
- **Зависит от:** `ClassifierAgent`, `PlannerAgent`, `ExecutorAgent`, `SecurityAgent`, `StallAgent`, `CompactionAgent`, `StepGuardAgent`, `VerifierAgent`, `WikiGraphAgent`
- **Особый случай:** задачи типа `TASK_PREJECT` обходят PlannerAgent и WikiGraphAgent — сразу создаётся минимальный `ExecutionPlan` и запускается `ExecutorAgent`
- **Статистика:** возвращает dict с ключами `outcome`, `step_facts`, `graph_injected_node_ids`, `eval_rejection_count`, `model_used`, `task_type`, `builder_used`, `builder_in_tok`, `builder_out_tok`, `contract_rounds_taken`, `contract_is_default`

## Поток выполнения

1. `run_prephase(vm, task_text)` — загрузить дерево vault и AGENTS.MD
2. `ClassifierAgent.run(task_input)` — определить task_type и выбрать модель
3. `WikiGraphAgent.read(...)` — получить wiki-контекст (patterns_text + graph_section)
4. Если `patterns_text` присутствует — внедрить в последнее user-сообщение prephase
5. `PlannerAgent.run(...)` → `ExecutionPlan` (system prompt + addendum + contract)
6. `ExecutorAgent.run(ExecutorInput)` → `ExecutorResult` с outcome и step_facts
7. Вернуть stats dict (статистика токенов, результат, тип задачи)

## Связанные концепции

- [[dispatch]] — низкоуровневый LLM-вызов и PCM-dispatch
- [[classifier]] — классификация задачи и маршрутизация модели
- [[classifier-agent]] — оборачивает classifier в контрактный интерфейс
- [[loop]] — основной цикл шагов агента (внутри ExecutorAgent)
- [[prephase]] — загрузка vault-контекста до начала цикла
- [[wiki-graph]] — граф знаний, инжектируемый в промпт
- [[wiki-graph-agent]] — читает и обновляет wiki-граф через контрактный интерфейс
- [[contract-phase]] — переговоры по контракту внутри PlannerAgent
