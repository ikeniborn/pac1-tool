---
wiki_title: "errors/default.md bloat — страница превышает лимит"
wiki_status: stub
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-05_v5_partial.md
wiki_domain: результаты
wiki_type: system-problem
tags: [wiki, errors-default, bloat, sanitize, system-problem]
---

# errors/default.md bloat — страница превышает лимит

**Статус:** диагностирована в v5 smoke run. Block B не покрыл эту страницу.

## Симптом

`errors/default.md`: 985 строк до smoke run, 962 после. Целевой лимит — 200 строк.  
117 fragment-IDs в meta-header. 40 фрагментов с пустым `outcome:` — ранние ингесты без финального outcome.

## Причина

sanitize_wiki.py (Block B) использует три lookup-специфичных regex:
- `_POISON_BLOCK` — "captured X days ago"
- `_VERIFIED_REFUSAL_BLOCK` — "## Verified refusal"
- `_LOOKUP_TASK_BLOCK` — "## Lookup Task:"

`errors/default.md` содержит generic-default error fragments — ни один из этих regex не совпадает.

## Фикс

Добавить regex в sanitize_wiki.py для drop'а блоков с `outcome: ` пустым из errors/default.md. Также опционально: drop по возрасту (task_id старше N дней).

## Связи

- [[результаты/сессии/run-v5-partial]] — контекст диагностики
- [[результаты/фиксы/blocks-a-g-quality]] — Block B описание
