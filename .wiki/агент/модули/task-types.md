---
wiki_sources:
  - "agent/task_types.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - classifier
aliases:
  - "task_types.py"
  - "REGISTRY"
  - "VALID_TYPES"
---

# Task Types Registry (agent/task_types.py)

Source of truth для типов задач — `data/task_types.json`. Загрузчик и API для остальных модулей. FIX-325.

## Что управляется реестром

- Enum классификатора (VALID_TYPES, `_TASK_CONSTS` в classifier.py)
- Docstring `ClassifyTask` и desc поле `task_type`
- `cc_json_schema.task_type.enum` (runtime inject в cc_client.py)
- Regex fast-path `classify_regex()`
- `ModelRouter` resolve через `resolve_model()`
- `wiki.py` folder map
- `prompt_builder._NEEDS_BUILDER`

## Ключевые функции

- `REGISTRY` — объект с загруженными типами из JSON
- `VALID_TYPES` — frozenset валидных type-id
- `classify_regex(task_text)` → `(type, confidence) | None`
- `resolve_model(task_type, env, default_model, explicit)` → model_id
- `build_classifier_docstring()`, `build_classifier_system_prompt()` — для DSPy Signature
- `builder_types()` → frozenset типов с `needs_builder=True`
- `plaintext_fallback_pairs()` → list[(keywords, type)] для plain-text fallback

## Добавление нового типа

1. Добавить entry в `data/task_types.json` (fields: description, model_env, fallback_chain, wiki_folder, fast_path, needs_builder, status)
2. Опционально: `MODEL_<UPPER>` в `.env`
3. Если `status: "soft"` → recompile: `uv run python scripts/optimize_prompts.py --target classifier`
4. Если нужен bespoke system-prompt → добавить в `_TASK_BLOCKS` в `agent/prompt.py`

## Связанные концепции

- [[classifier]] — re-exports TASK_* constants и использует API реестра
- [[prompt-builder]] — `_NEEDS_BUILDER` из реестра
- [[wiki-memory]] — folder map из реестра
