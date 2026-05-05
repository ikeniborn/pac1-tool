---
wiki_title: "Contract Prompts & Default Contracts Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-28-contract-prompts.md"
wiki_updated: "2026-05-06"
tags: [contract, data-files, prompts]
---

# Contract Prompts & Default Contracts

**Источник:** `docs/superpowers/plans/2026-04-28-contract-prompts.md`

## Цель

Создать 30 недостающих файлов данных (20 system prompt MD + 10 default contract JSON), чтобы `contract_phase.py` мог запускать реальные переговоры вместо fallback на hardcoded stub.

## Структура данных

**System prompts (20 MD-файлов):**
- `data/contracts/system_prompt_executor_{task_type}.md` — для 10 task_types
- `data/contracts/system_prompt_evaluator_{task_type}.md` — для 10 task_types

**Default contracts (10 JSON-файлов):**
- `data/contracts/default_{task_type}.json` — schema: `{plan_steps, success_criteria, failure_conditions, mutation_scope, evaluator_only}`

## Task types

think, distill, email, lookup, inbox, queue, capture, crm, temporal, preject
