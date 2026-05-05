---
wiki_title: "Orchestrator Wiring + Three-Party Contract Negotiation"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-05-03-orchestrator-contract-negotiation.md"
wiki_updated: "2026-05-06"
tags: [orchestrator, contract, dspy, three-party, planner]
---

# Orchestrator Wiring + Three-Party Contract Negotiation

**Источник:** `docs/superpowers/plans/2026-05-03-orchestrator-contract-negotiation.md`

## Цель

Подключить все субагенты через оркестратор с typed messages и добавить Round 0 `PlannerStrategize` к contract negotiation с DSPy joint optimization.

## Суть изменений

### Orchestrator wiring
Все субагенты (Prephase, Classifier, PromptBuilder, LoopAgent, WikiAgent, GraphAgent, PostrunAgent) получают сообщения через `orchestrator.dispatch(msg)` вместо прямых вызовов функций.

### Three-party contract negotiation
В contract phase добавляется Round 0:
1. **PlannerStrategize** (новый агент) — разрабатывает черновой plan ПЕРЕД executor/evaluator
2. Executor и evaluator уточняют plan planner'а
3. Consensus через max_rounds раундов

**Новые DSPy Signatures:**
- `PlannerStrategize` — `task_text, vault_tree → initial_plan, mutation_scope`
- Совместная оптимизация через `dspy.multi_chain_comparison`

## Ключевые файлы

- `agent/contract_phase.py` — добавить `_planner_strategize()` Round 0
- `agent/orchestrator.py` — wire messages
- `scripts/optimize_prompts.py` — `--target contract`
