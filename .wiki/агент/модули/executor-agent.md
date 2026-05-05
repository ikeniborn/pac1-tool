---
wiki_sources:
  - "agent/agents/executor_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - orchestrator
  - loop
  - dispatch
aliases:
  - "ExecutorAgent"
---

# ExecutorAgent (agent/agents/executor_agent.py)

Агент выполнения задачи в мультиагентной архитектуре. Принимает `ExecutorInput` (результат prephase, план, маршрутизацию модели), создаёт PCM VM-соединение и делегирует всю логику цикла в `run_loop` с инжектированными агентами.

## Основные характеристики

- **Конструктор:** принимает экземпляры `SecurityAgent`, `StallAgent`, `CompactionAgent`, `StepGuardAgent`, `VerifierAgent` — все без состояния, могут переиспользоваться между вызовами.
- **Метод `run(inp: ExecutorInput) → ExecutionResult`:**
  - Создаёт `PcmRuntimeClientSync(inp.harness_url)`.
  - Вызывает `run_loop` с DI-параметрами: `_security_agent`, `_stall_agent`, `_compaction_agent`, `_step_guard_agent`, `_verifier_agent`.
  - Конвертирует `step_facts` из dataclass-объектов в dicts (FIX-428).
  - Маппит outcome строку (`OUTCOME_OK` / `OUTCOME_DENIED_SECURITY` / `OUTCOME_ERR_INTERNAL`) в `status`.
- **Возвращает** `ExecutionResult`: `status`, `outcome`, `token_stats`, `step_facts`, `injected_node_ids`, `rejection_count`.
- Импорт `run_loop` и `PcmRuntimeClientSync` — ленивый (внутри `run()`), чтобы не тянуть gRPC при инициализации.

## Связанные концепции

- [[loop]] — содержит `run_loop`, которому делегирует ExecutorAgent
- [[security-agent]] — инжектируемый агент безопасности
- [[stall-agent]] — инжектируемый агент обнаружения stall
- [[step-guard-agent]] — инжектируемый агент валидации шагов
- [[verifier-agent]] — инжектируемый агент верификации завершения
- [[compaction-agent]] — инжектируемый агент компакции лога
