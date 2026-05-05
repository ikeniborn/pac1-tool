---
wiki_sources:
  - "agent/agents/step_guard_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - contract
  - dispatch
aliases:
  - "StepGuardAgent"
---

# StepGuardAgent (agent/agents/step_guard_agent.py)

Агент валидации инструментальных вызовов против контрактного плана в мультиагентной архитектуре. Обнаруживает отклонения от плана, согласованного `PlannerAgent`.

## Основные характеристики

- **Метод `check(request: StepGuardRequest) → StepValidation`:**
  - Извлекает `path` из `tool_args` (ключ `path` или `from_name`).
  - Формирует `done_ops`: `["DELETED: {path}"]` для `Req_Delete`, `["WRITTEN: {path}"]` для `Req_Write`/`Req_MkDir`, пустой для остальных.
  - Делегирует в `check_step(contract, done_ops, step_num)`.
  - При наличии предупреждения возвращает `StepValidation(valid=False, deviation=warning, suggestion=...)`.

- **Метод `check_optional(step_index, tool_name, tool_args, done_operations, contract)`:**
  - Если `contract is None` → всегда `valid=True` (нет ограничений).
  - Иначе — полная проверка через `check_step`.

- **Возвращает** `StepValidation`: `valid`, `deviation` (опционально), `suggestion` (опционально).

## Обнаруживаемые отклонения

- Удаления (`Req_Delete`), не упомянутые в контрактном плане.
- Записи в неожиданные директории начиная со шага ≥ 3.

## Связанные концепции

- [[contract-phase]] — `Contract` и `check_step` из contract_monitor
- [[executor-agent]] — инжектирует StepGuardAgent в run_loop
- [[planner-agent]] — производит `Contract`, который StepGuardAgent проверяет
