---
wiki_title: "Contract Phase Design"
wiki_type: design-spec
wiki_status: mature
wiki_sources:
  - docs/superpowers/specs/2026-04-27-contract-phase-design.md
  - docs/superpowers/specs/2026-04-28-contract-dspy-optimization-design.md
  - docs/superpowers/specs/2026-04-28-contract-prompts-design.md
  - docs/superpowers/specs/2026-04-29-contract-b3-grounding-enforcement-design.md
  - docs/superpowers/specs/2026-04-29-wiki-graph-contract-improvements-design.md
  - docs/superpowers/specs/2026-05-03-orchestrator-contract-negotiation-design.md
wiki_updated: 2026-05-05
tags: [contract, design, dspy, architecture]
---

# Contract Phase Design

## Проблема

Evaluator видит результаты только после выполнения задачи. Нет upfront-соглашения о критериях успеха.

## Целевая архитектура

```
AGENT.md + task + wiki_context + graph_context
  → CONTRACT PHASE
      ExecutorAgent ←→ EvaluatorAgent
      max N раундов (CONTRACT_MAX_ROUNDS=3)
      → Contract (plan_steps, success_criteria, required_evidence, failure_conditions)
  → EXECUTION LOOP (Contract injected в system prompt)
  → VERIFICATION (validates vs Contract)
```

## Структуры данных

```python
class ExecutorProposal(BaseModel):
    plan_steps, expected_outcome, required_tools
    planned_mutations: list[str]   # явные пути write/delete
    open_questions, agreed: bool

class EvaluatorResponse(BaseModel):
    success_criteria, failure_conditions, required_evidence
    objections, agreed: bool

class Contract(BaseModel):
    plan_steps, success_criteria, required_evidence, failure_conditions
    mutation_scope, forbidden_mutations  # из wiki contract constraints
    evaluator_only: bool   # True = только evaluator согласился
    planner_strategy: str  # из Round 0 PlannerStrategize
    is_default: bool, rounds_taken: int
```

## Round 0: PlannerStrategize

Перед executor-evaluator-петлёй — сигнатура `PlannerStrategize(task_text, task_type, vault_tree, agents_md)` → `search_scope, interpretation, critical_paths, ambiguities`. Устраняет узкий search scope (t42: агент искал только `/01_capture/influential/`).

## Grounding (vault_tree в negotiation)

`vault_tree` передаётся в обоих агентах negotiation. Устраняет false consensus когда executor предлагает абстрактные пути не зная реальной структуры vault.

## Fallback hierarchy

1. Parse error → retry up to 3 раз
2. max_rounds exceeded + непустой `rounds_transcript` → partial contract из последнего раунда (не generic default)
3. Пустой `rounds_transcript` → `_load_default_contract(task_type)`

## Per-type default contracts

`data/default_contracts/{email,inbox,queue,lookup,capture,crm,temporal,distill,preject}.json` — статические fallback-контракты с task-specific guidance.

## Промпты

`data/prompts/{task_type}/executor_contract.md` + `evaluator_contract.md` + `planner_contract.md`. Fallback → `data/prompts/default/`.

## DSPy оптимизация

Сбор: `data/dspy_contract_examples.jsonl` — только для `not is_default` трajectoрий. Expand_rounds=True: каждый раунд → отдельный пример. Optimize: `--target contract`.

## contract_monitor (runtime)

`agent/contract_monitor.py` — правила без LLM, max 3 warnings/task:
- Unexpected delete не из `plan_steps`
- Write за пределами согласованного scope (at `step_num >= 3`)

## Mutation-scope gate

`loop.py`: при `evaluator_only=True` и write вне `mutation_scope` → stall-hint + счётчик `consecutive_contract_blocks`. При ≥2 блоках → force `OUTCOME_NONE_CLARIFICATION`.

**Текущий статус (FIX-437 dead-code):** gate переключён с dead `evaluator_only` на `not is_default and mutation_scope` в рамках fix из v5.

## Env-переменные

```
CONTRACT_ENABLED=1
CONTRACT_MAX_ROUNDS=3
MODEL_CONTRACT=openrouter/...  # если задан — CC tier тоже negotiates
CONTRACT_COLLECT_DSPY=1
OPTIMIZER_CONTRACT=copro
```
