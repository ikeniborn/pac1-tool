---
wiki_title: "Agent Fixes & Knowledge Pipeline — FIX-394–400"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-04-27-agent-fixes-knowledge-pipeline.md"
wiki_updated: "2026-05-06"
tags: [fix, gate, contract, json-parse, wiki, temporal, FIX-394, FIX-395, FIX-396, FIX-397, FIX-398, FIX-399, FIX-400]
---

# Agent Fixes & Knowledge Pipeline (FIX-394–400)

**Источник:** `docs/superpowers/plans/2026-04-27-agent-fixes-knowledge-pipeline.md`

## Цель

Исправить 4 кодовых бага (gate deadlocks, CC contract overhead, JSON parse errors, timeout hallucination) и включить накопление знаний wiki/graph в нормальном режиме.

## Фиксы

### FIX-394: CC tier early-return в contract_phase.py

**Проблема:** Все 43 задачи тратят 1-2 пустых CC subprocess на contract negotiation.  
**Файл:** `agent/contract_phase.py`  
**Фикс:** `if model.startswith("claude-code/"): return _load_default_contract(task_type), 0, 0`

### FIX-395: contact gate — README.MD не считается contact file

**Проблема:** Search возвращает `contacts/README.MD:17`, счётчик `_empty_searches` не инкрементируется → t11 зациклился.  
**Файл:** `agent/loop.py:1786-1796`  
**Фикс:** `_has_contact_json = ".json" in _summary_lower` — если нет `.json` в результате → считать как empty search.

### FIX-396: force-read-before-write — create vs update

**Проблема:** Gate блокирует запись нового файла (ещё не существующего) → t13 timeout.  
**Файл:** `agent/loop.py:1670-1679`  
**Фикс:** Сообщение gate теперь разъясняет: "If creating new file — proceed with write directly. If updating existing — read first."

### FIX-397: Pre-strip CC output перед model_validate_json

**Проблема:** CC добавляет текст после `}` → "trailing characters" → fallback extraction на ~70% задач.  
**Файл:** `agent/loop.py:533-534`  
**Фикс:** Балансирующий скобки strip до первой `{` / последней `}` перед `model_validate_json`.

### FIX-398: Timeout recovery — hint при [FILE UNREADABLE]

**Проблема:** PCM возвращает `[FILE UNREADABLE]` → агент галлюцинирует содержимое → t30 придумал 5, потом 24 записи.  
**Файлы:** `agent/loop.py`, `agent/prompt.py`  
**Фикс:** Инжектировать user message "Retry with search on this path. Do NOT guess content." + правило в `_CORE`.

### FIX-399: Normal-mode wiki promotion

**Проблема:** `promote_successful_pattern()` вызывается только в researcher mode → `pages/*.md` пусты.  
**Файл:** `main.py:373-374`  
**Фикс:** После researcher-promotion блока — добавить normal-mode блок, который вызывает `promote_successful_pattern` / `promote_verified_refusal` при `score>=1.0`.

### FIX-400: Vault date — явный поиск в AGENTS.MD

**Проблема:** t41 "what day is today?" → агент использовал системную дату вместо vault date.  
**Файлы:** `agent/prephase.py`, `agent/prompt.py`  
**Фикс:** Regex-поиск `VAULT_DATE:` / `today:` в AGENTS.MD; добавить правило в `_TEMPORAL` о TASK CONTEXT date.

## Ожидаемый эффект

| Фикс | Задачи | Ожидаемый эффект |
|------|--------|-----------------|
| FIX-394 | Все 43 | -1-2 CC subprocess/задачу |
| FIX-395 | t11 | ≤5 шагов вместо 30 |
| FIX-396 | t13 | Нет timeout на создание файлов |
| FIX-397 | ~30 задач | Исчезновение JSON parse failed логов |
| FIX-398 | t30 | Нет галлюцинации при FILE UNREADABLE |
| FIX-399 | Все будущие | pages/*.md накапливают паттерны |
| FIX-400 | t41 | Vault date для temporal задач |

**Прямой gain: +4 задачи → ~76.7% (33/43)**
