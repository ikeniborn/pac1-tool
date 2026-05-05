---
wiki_title: "Context Management Redesign Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-28-context-management.md"
wiki_updated: "2026-05-06"
tags: [context, compaction, log-compaction, failure-knowledge]
---

# Context Management Redesign

**Источник:** `docs/superpowers/plans/2026-04-28-context-management.md`

## Цель

Исправить два независимых дефекта деградации контекста: (1) compaction срабатывает безусловно каждый шаг вместо lazy по token fill, (2) knowledge о failure (error fragments) никогда не передаётся агенту при следующем прогоне.

## Проблема 1: Eager compaction

`log_compaction.py` компактирует на каждом шаге вне зависимости от заполненности контекста. Это теряет полезный контекст слишком рано.

**Фикс:** Compaction только когда `estimated_tokens > threshold` (например, 80% от `context_window`). Добавить `_should_compact(log, model_context_window) -> bool`.

## Проблема 2: Failure knowledge gap

При score=0 — error fragments (`step_facts` с `error != ""`) нигде не сохраняются. На следующем прогоне агент повторяет те же ошибки.

**Фикс:** После `end_trial(score=0)` — сохранять error_summary в `data/failure_cache/{task_type}.jsonl`. При prephase — читать и инжектировать в system prompt как "Known failure patterns".

## Ключевые файлы

- `agent/log_compaction.py` — lazy compaction gate
- `agent/prephase.py` — inject failure_cache
- `main.py` — save error_summary on score=0
