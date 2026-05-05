---
wiki_title: "T43 Followup Fixes Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-30-t43-followup-fixes.md"
wiki_updated: "2026-05-06"
tags: [fix, contract, evaluator, graph, wiki, t43]
---

# T43 Followup Fixes

**Источник:** `docs/superpowers/plans/2026-04-30-t43-followup-fixes.md`

## Цель

Устранить три проблемы из аудита t43: контракт игнорирует wiki-refusals, evaluator bypassed для всех lookup, error-ingest создаёт дубликаты в графе.

## Связь

Вытекает из [[t43-architecture-audit]] — три проблемы выявлены в ходе аудита t43.

## Три проблемы

### 1. Контракт игнорирует wiki-refusals
Negotiation не учитывает "Verified refusals" из wiki pages.  
**Фикс:** В `negotiate_contract()` — инжектировать wiki refusal patterns в context (аналогично reference_patterns в evaluator).  
**Файл:** `agent/contract_phase.py`

### 2. Evaluator bypass для всех lookup (не только pure read)
Lookup задачи с write операциями bypasses evaluator → неверные outcomes.  
**Фикс:** Bypass только если нет write/delete в `done_ops`.  
**Файл:** `agent/evaluator.py`

### 3. Error-ingest дублирует граф
При `WIKI_GRAPH_FEEDBACK=1` и score=0 — `add_pattern_node(type='antipattern')` создаёт дубликаты при повторных прогонах одной задачи.  
**Фикс:** `_find_near_duplicate()` проверяет перед добавлением. Если дубль — `bump_uses(existing)` вместо создания нового.  
**Файл:** `agent/wiki_graph.py`
