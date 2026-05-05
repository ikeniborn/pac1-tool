---
wiki_title: "Wiki / Graph / Contract Improvements"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-29-wiki-graph-contract-improvements.md"
wiki_updated: "2026-05-06"
tags: [fix, wiki, contract, security, mutation-scope, evaluator-only]
---

# Wiki / Graph / Contract Improvements

**Источник:** `docs/superpowers/plans/2026-04-29-wiki-graph-contract-improvements.md`

## Цель

Предотвратить четыре failure pattern: vault-doc injection writes, evaluator-only wrong outcomes, scope-overreach deletes, security false-positives — добавив wiki contract constraints, расширив Contract models с mutation_scope/evaluator_only flags, гейтируя out-of-scope mutations в loop.py, добавив trusted-path exemption в security.py.

## Четыре исправления

### 1. Vault-doc injection writes
Агент записывает в `docs/`, `automation.md`, инструкции vault — запрещённые пути.  
**Фикс:** Wiki pages (successful patterns) добавляют контрактное ограничение: система путей `docs/` ≠ task output. Правило в `_CORE` prompt.

### 2. Evaluator-only wrong outcomes
Контракт `evaluator_only=True` → агент сообщает неверный outcome (OUTCOME_NONE вместо OUTCOME_OK).  
**Фикс:** При `evaluator_only=True` — явный hint в loop: "You are in evaluation-only mode. Report outcome based on vault state, not your mutations."

### 3. Scope-overreach deletes
Агент удаляет файлы за пределами `mutation_scope`.  
**Фикс:** `_check_contract_compliance()` в loop.py для операций `delete` — verifica против `contract.mutation_scope`.

### 4. Security false-positives
`security.py` блокирует легитимные пути через homoglyph detection.  
**Фикс:** Trusted-path whitelist (`/outbox/`, `/contacts/`, `/capture/`, `/reminders/`) — не применять homoglyph detection.

**Ключевые файлы:** `agent/loop.py`, `agent/security.py`, `agent/prompt.py`
