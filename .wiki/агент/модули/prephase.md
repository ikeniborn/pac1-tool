---
wiki_sources:
  - "agent/prephase.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - prephase
aliases:
  - "run_prephase"
  - "PrephaseResult"
---

# Prephase (agent/prephase.py)

Фаза до начала основного цикла: загрузка vault tree, AGENTS.MD, inbox-файлов. Результат — `PrephaseResult` с начальным логом сообщений и preserve_prefix для compaction.

## Основные характеристики

### `PrephaseResult`

Dataclass:
- `log` — начальный лог сообщений (system prompt + few-shot + vault context)
- `preserve_prefix` — сообщения, никогда не вытесняемые compaction
- `agents_md_content` — содержимое AGENTS.MD (vault rulebook)
- `agents_md_path` — путь к найденному AGENTS.MD
- `inbox_files` — list of (path, content) inbox-файлов, отсортированный alphabetically
- `vault_tree_text` — raw tree-вывод шага 1 (передаётся в prompt_builder для task-specific guidance)
- `vault_date_est` — inferred дата vault YYYY-MM-DD для contract negotiation (FIX-406)

### Few-shot пара

Помещается сразу после system prompt в `preserve_prefix` — наиболее сильный сигнал для JSON-only вывода. Generic пути (не vault-специфичные, discovery-first принцип).

## Связанные концепции

- [[orchestrator]] — вызывает `run_prephase` как первый шаг
- [[log-compaction]] — `preserve_prefix` защищен от compaction
- [[classifier]] — `pre.agents_md_content` используется как vault_hint в `resolve_after_prephase`
