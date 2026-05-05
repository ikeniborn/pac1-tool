---
wiki_title: "Agent Fixes & Knowledge Pipeline (2026-04-27)"
wiki_type: design-spec
wiki_status: developing
wiki_sources:
  - docs/superpowers/specs/2026-04-27-agent-fixes-knowledge-pipeline-design.md
wiki_updated: 2026-05-05
tags: [fix, architecture, design, wiki]
---

# Agent Fixes & Knowledge Pipeline

**Baseline run:** `logs/20260427_164400_claude-code-sonnet-4.6` — 67.44% (29/43)

## Фиксы

### A1 — CC contract executor: парсинг пустого result

CC возвращает `stop_reason=end_turn` с пустым `result` (вывод в `tool_use`). Fix в `cc_client.py`: проверять `tool_use` блоки, извлекать последний assistant-message как result.

### A2 — Gate deadlocks

**Проблема A** ([force-read-contact]): search по `/contacts/` возвращает README.MD, gate не расслабляется. Fix: счётчик `_contact_search_misses` — инкрементировать только при нулевых совпадениях с contact-файлами.

**Проблема Б** ([force-read-before-write]): блокирует создание новых файлов. Fix: отличать create vs update через `set read_paths`. Смягчённое сообщение: "If updating existing file — read it first. If creating new file — proceed."

### A3 — JSON parse errors из CC

`_strip_fences` не справляется с trailing text после `}`. Fix: fallback-извлечение через stack-based балансировку скобок.

### A4 — Timeout recovery

При `[FILE UNREADABLE]` — инжектировать hint: "Use search tool as fallback. Do NOT guess content."

### B5 — Promote pattern/refusal в normal mode

`promote_successful_pattern()` и `promote_verified_refusal()` вызываются только в `RESEARCHER_MODE=1`. Fix: убрать guard, промоут становится стандартным поведением.

### B6 — Vault date

Агент использует системную дату вместо vault date. Fix в `prephase.py`: искать `VAULT_DATE:` в AGENTS.MD или файлы `context.json`, `vault-meta.json`.

## Ожидаемый эффект

| Изменение | Gain |
|---|---|
| A2 Gate deadlocks | +2 задачи (t11, t13) |
| A4 Timeout recovery | +1 задача (t30) |
| B6 Vault date | +1 задача (t41) |
| A1, A3 | -токены, +надёжность |
| B5 | накопительный эффект на будущих прогонах |
