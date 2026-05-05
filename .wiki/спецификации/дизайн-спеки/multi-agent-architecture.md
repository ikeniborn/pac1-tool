---
wiki_sources:
  - docs/superpowers/specs/2026-04-30-multi-agent-architecture-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, architecture, orchestrator, hub-and-spoke, agents, contracts]
---

# Multi-Agent Architecture: Hub-and-Spoke

**Дата:** 2026-04-30 | **Scope:** Рефакторинг монолитного `loop.py` в 10 изолированных агентов

## Принципы

- In-process изоляция (не subprocess, не сеть)
- Существующие модули не переписываются — агенты являются обёртками
- `agent/contracts/` — единственный shared import между агентами
- Оркестратор — единственный, кто импортирует агентов

## 10 агентов

```
Orchestrator (agent/orchestrator.py)
  ClassifierAgent      → agent/agents/classifier_agent.py
  WikiGraphAgent       → agent/agents/wiki_graph_agent.py
  PlannerAgent         → agent/agents/planner_agent.py
  ExecutorAgent        → agent/agents/executor_agent.py
    SecurityAgent      → agent/agents/security_agent.py
    StallAgent         → agent/agents/stall_agent.py
    CompactionAgent    → agent/agents/compaction_agent.py
    StepGuardAgent     → agent/agents/step_guard_agent.py
    VerifierAgent      → agent/agents/verifier_agent.py
```

## Типизированные контракты (agent/contracts/__init__.py)

Ключевые типы: `TaskInput`, `ClassificationResult`, `WikiContext`, `ExecutionPlan`, `SecurityCheck`, `StallResult`, `CompactedLog`, `VerificationResult`, `ExecutionResult`

## Orchestrator flow

```python
def run_agent(router, harness_url, task_text, trial_id):
    classification = ClassifierAgent().run(task_input)
    # preject short-circuit
    # parallel (ThreadPoolExecutor): prephase + WikiGraphAgent.read
    plan = PlannerAgent().run(PlannerInput(...))
    result = ExecutorAgent(...).run(ExecutorInput(...))
    WikiGraphAgent().write_feedback(WikiFeedbackRequest(...))
    return result.token_stats
```

Prephase + WikiGraphAgent.read выполняются параллельно (независимы).

## VerifierAgent

Часть петли ExecutorAgent, не финальный шаг оркестратора. При `approved=False` фидбек возвращается в цикл как user-сообщение.

## StepGuardAgent

Проверяет соответствие каждого шага `Contract` из `ExecutionPlan` до dispatch.

## Стратегия миграции (5 фаз)

1. `agent/contracts/__init__.py` — все контракты
2. Leaf-агенты: Security, Stall, Compaction, StepGuard, Classifier
3. WikiGraphAgent (read + write_feedback)
4. VerifierAgent + PlannerAgent
5. ExecutorAgent → orchestrator.py
