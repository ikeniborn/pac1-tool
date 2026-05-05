---
wiki_sources:
  - "agent/agents/stall_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - stall
  - dispatch
aliases:
  - "StallAgent"
---

# StallAgent (agent/agents/stall_agent.py)

Агент обнаружения зависаний (stall) в мультиагентной архитектуре. Оборачивает `_check_stall` из `agent.stall` в контрактный интерфейс.

## Основные характеристики

- **Метод `check(request: StallRequest) → StallResult`:**
  - Конвертирует `request.fingerprints` в `deque(maxlen=10)`, `request.error_counts` в `Counter`.
  - Конвертирует `request.step_facts_dicts` в `_StepFact` объекты.
  - Делегирует в `_check_stall(fp, steps_without_write, ec, facts, contract_plan_steps)`.
  - Если hint=None → `StallResult(detected=False)`.
  - Если hint содержит `[STALL ESCALATION]` → escalation level 2 (< 18 шагов) или 3 (≥ 18 шагов). Иначе — level 1.
- **Возвращает** `StallResult`: `detected`, `hint`, `escalation_level`.

## Типы обнаруживаемых зависаний

| Тип | Триггер | Escalation |
|-----|---------|-----------|
| Повтор fingerprint | 3× одинаковый вызов | 1 |
| Повтор path error | 2× одинаковая ошибка | 1 |
| Exploration stall | 6+ шагов без write | 1 |
| Escalation 12+ | 12+ шагов без write | 2 |
| Escalation 18+ | 18+ шагов без write | 3 |

## Связанные концепции

- [[stall]] — содержит базовую функцию `_check_stall`
- [[executor-agent]] — инжектирует StallAgent в run_loop
