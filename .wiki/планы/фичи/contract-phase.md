---
wiki_title: "Contract Phase Implementation Plan"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-04-27-contract-phase.md"
wiki_updated: "2026-05-06"
tags: [contract, evaluator, negotiation, feature]
---

# Contract Phase

**Источник:** `docs/superpowers/plans/2026-04-27-contract-phase.md`

## Цель

Добавить pre-execution фазу contract negotiation: executor и evaluator агенты интерактивно договариваются о плане и критериях успеха до начала выполнения инструментов.

## Архитектура

Новый модуль `agent/contract_phase.py`. Отдельные system prompts для executor/evaluator в `data/contracts/`. Переговоры — несколько раундов LLM-вызовов до consensus. Default contracts (JSON) на каждый task_type как fallback.

## Ключевые компоненты

- `negotiate_contract(task_text, task_type, ...)` — основная функция, возвращает `(Contract, in_tok, out_tok)`
- `Contract` dataclass: `plan_steps`, `success_criteria`, `failure_conditions`, `mutation_scope`, `evaluator_only`
- `_load_default_contract(task_type)` — fallback при отсутствии промптов или CC tier
- `Contract.is_default` — флаг дефолтного контракта

## Важные паттерны

### CC tier early return (FIX-394)
CC tier не может вернуть structured JSON (tool_use stripped). Ранний return до любых LLM-вызовов:
```python
if model.startswith("claude-code/"):
    return _load_default_contract(task_type), 0, 0
```

### Evaluator-only flag
Контракт может указать `evaluator_only=True` → агент только оценивает vault, не мутирует. Gate в `loop.py`.

### Mutation scope
`mutation_scope` — список разрешённых путей. Gate в `loop.py` блокирует запись вне scope.

## Данные (30 файлов)

- `data/contracts/system_prompt_executor_{task_type}.md` — 10 файлов
- `data/contracts/system_prompt_evaluator_{task_type}.md` — 10 файлов
- `data/contracts/default_{task_type}.json` — 10 файлов
