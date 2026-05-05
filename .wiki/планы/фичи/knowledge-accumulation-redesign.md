---
wiki_title: "Knowledge Accumulation Redesign Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-05-04-knowledge-accumulation-redesign.md"
wiki_updated: "2026-05-06"
tags: [wiki, graph, knowledge, feedback-loop, dspy, evaluator, builder]
---

# Knowledge Accumulation Redesign

**Источник:** `docs/superpowers/plans/2026-05-04-knowledge-accumulation-redesign.md`

## Цель

Устранить внутренние конфликты системы (граф vs промпт, evaluator-only contract, builder/evaluator deadlock, POSTRUN_OPTIMIZE отключён), чтобы петля накопления знаний реально влияла на качество.

## Четыре конфликта

### 1. Граф vs промпт
Wiki graph вносит noise в system prompt — узлы antipattern с низким confidence заглушают полезные pattern узлы. Фикс: min_confidence threshold для инъекции.

### 2. Evaluator-only contract deadlock
Контракт `evaluator_only=True` + задача требует write → агент зависает. Фикс: contract monitor должен предупреждать агента о конфликте, не блокировать.

### 3. Builder/evaluator deadlock
DSPy builder генерирует слишком строгие hints → evaluator отклоняет все → score=0 на всём. Фикс: разделить builder и evaluator trainsets.

### 4. POSTRUN_OPTIMIZE отключён
`agent/postrun.py` → `POSTRUN_OPTIMIZE=1` никогда не устанавливается. Фикс: auto-enable после N примеров в `dspy_examples.jsonl`.

## Ключевые файлы

- `agent/wiki_graph.py` — min_confidence threshold
- `agent/contract_phase.py` — evaluator-only conflict warning
- `agent/dspy_examples.py` — разделить builder/evaluator trainsets
- `agent/postrun.py` — auto-enable `POSTRUN_OPTIMIZE`
