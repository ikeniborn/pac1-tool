---
wiki_title: "Multi-Agent Hub-and-Spoke Architecture Implementation Plan"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-04-30-multi-agent-architecture.md"
wiki_updated: "2026-05-06"
tags: [architecture, multi-agent, hub-spoke, refactor, pydantic]
---

# Multi-Agent Hub-and-Spoke Architecture

**Источник:** `docs/superpowers/plans/2026-04-30-multi-agent-architecture.md`

## Цель

Рефакторинг монолитного агента в 10 изолированных агентов с типизированными Pydantic-контрактами (in-process, никакой переписки с нуля).

## Архитектура

```
Orchestrator (hub)
├── Prephase Agent
├── Classifier Agent
├── PromptBuilder Agent
├── Evaluator Agent
├── LoopAgent (executor)
│   ├── Dispatcher
│   ├── StallDetector
│   └── SecurityGate
├── WikiAgent
├── GraphAgent
└── PostrunAgent
```

**Принцип:** Все агенты общаются через typed Pydantic messages. Оркестратор — единственная точка координации.

## Структура файлов

**Новые файлы:**
- `agent/orchestrator.py` — hub, маршрутизирует сообщения
- `agent/agents/base.py` — `BaseAgent(Protocol)` с `process(msg) -> AgentResult`
- `agent/agents/classifier.py`, `prephase.py`, `prompt_builder.py`, etc.
- `agent/messages.py` — Pydantic message types

**Модифицируемые:**
- `main.py` — заменить прямые вызовы на `orchestrator.run(task)`
- `agent/__init__.py` — экспортировать `Orchestrator`

## Ключевые паттерны

### Typed messages
Каждый агент принимает специфичный `InputMsg` и возвращает `OutputMsg`. Нет прямого доступа к `LoopState` между агентами.

### In-process, не subprocess
Агенты — Python классы, не отдельные процессы. Никакого gRPC между агентами.

### Совместимость
Монолитные функции переносятся as-is внутрь агентов. Поведение не меняется — только интерфейс обёртки.
