---
wiki_title: "Remove RESEARCHER Mode Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-28-remove-researcher.md"
wiki_updated: "2026-05-06"
tags: [refactor, researcher, cleanup, normal-mode]
---

# Remove RESEARCHER Mode

**Источник:** `docs/superpowers/plans/2026-04-28-remove-researcher.md`

## Цель

Удалить весь RESEARCHER-режим из кодовой базы, оставив normal mode нетронутым.

## Мотивация

RESEARCHER mode — экспериментальный режим с промпт-логикой для "исследовательских" задач. После внедрения wiki/graph pipeline он стал рудиментом. Его код запутывает main.py и loop.py, а FIX-399 (normal-mode wiki promotion) делает его ненужным.

## Что удалить

- `agent/researcher.py` — весь файл
- `main.py` — блок `if researcher_mode: ... researcher.run(...)` (~30 строк)
- `agent/loop.py` — condition branches на `RESEARCHER_MODE`
- `agent/prompt.py` — `_RESEARCHER_BLOCK` (если есть)
- `.env.example` — `RESEARCHER_MODE` переменная
- `tests/test_researcher*.py` — тесты

## Условие безопасного удаления

`make run` на все 43 задачи должен дать те же scores ±0 — researcher mode никогда не включался в production (всегда `RESEARCHER_MODE=0`).
