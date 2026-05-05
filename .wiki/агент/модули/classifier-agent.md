---
wiki_sources:
  - "agent/agents/classifier_agent.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - classifier
  - dispatch
aliases:
  - "ClassifierAgent"
---

# ClassifierAgent (agent/agents/classifier_agent.py)

Агент классификации задачи и выбора модели в мультиагентной архитектуре. Оборачивает `classify_task` и `ModelRouter` из `agent.classifier` в контрактный интерфейс.

## Основные характеристики

- **Конструктор:** принимает `ModelRouter`; router содержит дефолтную модель и per-type overrides.
- **Метод `run(task, prephase=None) → ClassificationResult`:**
  - Если `prephase` передан → `router.resolve_after_prephase()` использует vault-контекст (AGENTS.MD, дерево файлов, wiki-подсказки) для более точной классификации; `confidence=0.95`.
  - Если `prephase=None` → regex fast-path через `classify_task()`; `confidence=0.8`.
- **Возвращает** `ClassificationResult` с полями: `task_type`, `model`, `model_cfg`, `confidence`.
- **Изоляция**: импортирует только из `agent.classifier` и `agent.contracts`.

## Связанные концепции

- [[classifier]] — базовая логика `classify_task` и `ModelRouter`
- [[orchestrator]] — оркестрирует вызов ClassifierAgent в пайплайне
