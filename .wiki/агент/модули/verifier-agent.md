---
wiki_sources:
  - "agent/agents/verifier_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - evaluator
  - dspy
  - dispatch
aliases:
  - "VerifierAgent"
---

# VerifierAgent (agent/agents/verifier_agent.py)

Агент верификации завершения задачи в мультиагентной архитектуре. Оборачивает `evaluate_completion` из `agent.evaluator` в контрактный интерфейс с fail-open семантикой.

## Основные характеристики

- **Конструктор:** принимает `enabled` (default из `EVALUATOR_ENABLED`), `model`, `cfg`.
- **Метод `verify(request: CompletionRequest) → VerificationResult`:**
  1. Если `enabled=False` → авто-одобрение (`approved=True`).
  2. Если модель не настроена → авто-одобрение.
  3. Вызывает `evaluate_completion(task_text, task_type, report, done_ops, digest_str, model, cfg, skepticism, efficiency, contract)`.
  4. При отказе — `rejection_count += 1` и передаёт `correction_hint` как `feedback`.
  5. При исключении в evaluate_completion — fail-open: авто-одобрение с логом.
- **Ленивый импорт** `agent.evaluator` внутри `verify()` — DSPy стек не загружается, пока verifier не вызван.
- Env: `EVALUATOR_ENABLED` (default `1`), `EVAL_SKEPTICISM` (default `mid`), `EVAL_EFFICIENCY` (default `mid`).
- **Возвращает** `VerificationResult`: `approved`, `feedback` (при отказе), `rejection_count`.

## Связанные концепции

- [[evaluator]] — содержит `evaluate_completion` с DSPy-логикой
- [[executor-agent]] — инжектирует VerifierAgent в run_loop
