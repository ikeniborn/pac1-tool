---
wiki_title: "Contract B3: Grounding + Enforcement Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-29-contract-b3-grounding-enforcement.md"
wiki_updated: "2026-05-06"
tags: [fix, contract, grounding, enforcement, vault-tree, contract-monitor]
---

# Contract B3: Grounding + Enforcement

**Источник:** `docs/superpowers/plans/2026-04-29-contract-b3-grounding-enforcement.md`

## Цель

Исправить три паттерна сбоя контракта: vault_tree grounding в negotiation, parse-error retry с partial fallback, failure_conditions в evaluator prompt, и rule-based contract_monitor в loop.

## Четыре фикса

### 1. Vault_tree grounding
Negotiation промпты не содержат vault tree → executor/evaluator договариваются о несуществующих путях.  
**Фикс:** Инжектировать `vault_tree` в negotiation context (уже передаётся параметром, нужно добавить в промпт).

### 2. Parse-error retry с partial fallback
Если один раунд negotiation даёт невалидный JSON — весь контракт падает на default.  
**Фикс:** Retry текущего раунда с упрощённым промптом; partial fallback (использовать часть предыдущего валидного раунда).

### 3. failure_conditions в evaluator prompt
Evaluator prompt не содержит `failure_conditions` из предыдущих раундов → не учитывает накопленные ограничения.  
**Фикс:** Передавать `accumulated_conditions` в каждый следующий раунд evaluator.

### 4. Rule-based contract_monitor в loop.py
После начала выполнения — нет runtime проверки соответствия выполняемых операций контракту.  
**Фикс:** `_check_contract_compliance(job, contract)` перед каждым dispatch. Если нарушение — вернуть блокирующее сообщение.

**Ключевые файлы:** `agent/contract_phase.py`, `agent/loop.py`
