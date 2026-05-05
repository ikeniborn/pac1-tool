---
wiki_title: "Contract DSPy Optimization Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-28-contract-dspy-optimization.md"
wiki_updated: "2026-05-06"
tags: [contract, dspy, optimization, copro]
---

# Contract DSPy Optimization

**Источник:** `docs/superpowers/plans/2026-04-28-contract-dspy-optimization.md`

## Цель

Собирать примеры negotiated contracts и использовать их для (A) оптимизации executor/evaluator negotiation prompts через DSPy, и (B) дистиллировать per-type default contracts из успешных прогонов.

## Суть

После накопления N примеров контрактных переговоров:
1. COPRO/GEPA оптимизирует промпты executor/evaluator для лучшего консенсуса
2. Успешные контракты дистиллируются в новые `data/contracts/default_{task_type}.json`

**Ключевые файлы:**
- `agent/dspy_contract_examples.py` — сбор примеров (аналог `dspy_examples.py`)
- `scripts/optimize_prompts.py` — расширить под `--target contract`
- `data/contracts/` — обновляемые default contracts
