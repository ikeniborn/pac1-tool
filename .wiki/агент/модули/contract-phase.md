---
wiki_sources:
  - "agent/contract_phase.py"
  - "agent/contract_models.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - contract
aliases:
  - "Contract"
  - "contract negotiation"
  - "ContractPhase"
---

# Contract Phase (agent/contract_phase.py)

Двухролевые переговоры перед выполнением: executor и evaluator агенты обмениваются Pydantic-валидированными JSON-сообщениями до `max_rounds`. Когда оба установят `agreed=True` — финализируется `Contract`. Fail-open: любая ошибка → default contract из `data/default_contracts/<task_type>.json`.

## Основные характеристики

- **Три compiled programs**: `contract_executor_program.json`, `contract_evaluator_program.json`, `contract_planner_program.json` (FIX-426: planner опционален)
- **`MUTATION_REQUIRED_TYPES`**: для типов `crm`, `capture`, `inbox` контракт должен включать mutation (write/delete/move)
- **`_effective_model`**: использует `MODEL_CONTRACT` env если задан, иначе caller_model
- **Wiki-контекст**: `load_contract_constraints` и `load_refusal_hints` из `agent/wiki.py` инжектируются в evaluator prompt

### Pydantic-модели (agent/contract_models.py)

- `Contract` — финальный договор: plan_steps, mutation_required, agreed
- `ContractRound` — один раунд переговоров
- `ExecutorProposal` — предложение executor
- `EvaluatorResponse` — ответ evaluator с agreed/feedback

## Связанные концепции

- [[orchestrator]] — contract phase запускается внутри PlannerAgent
- [[evaluator]] — evaluator agent участвует в переговорах
- [[wiki-memory]] — wiki-контекст для контракта загружается из wiki.py
