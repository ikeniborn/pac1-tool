---
wiki_sources:
  - "agent/classifier.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - classifier
  - dspy
aliases:
  - "ModelRouter"
  - "classify_task_llm"
  - "task type classifier"
---

# Classifier (agent/classifier.py)

Классификатор типов задач и маршрутизатор моделей. Source of truth для типов задач — `data/task_types.json` (через `agent/task_types.py`). Экспортирует backwards-compatible константы `TASK_*` через `__getattr__`.

## Основные характеристики

### Классификация задач

Трёхступенчатый pipeline:

1. **Regex fast-path** (`classify_regex`, FIX-325): высокоуверенные паттерны из реестра; если confidence="high" — пропускает LLM
2. **DSPy ChainOfThought** (`ClassifyTask` Signature): загружается из `data/classifier_program.json`; docstring и enum enum-поле `task_type` генерируются из реестра при загрузке модуля
3. **Plain LLM fallback**: `call_llm_raw` с системным промптом из реестра; извлекает тип regex-ом из частичного JSON; plaintext keyword-fallback как последний резерв

**Majority vote для CC тира** (FIX-N+2): при `provider='claude-code'` запускает классификацию `CLASSIFIER_VOTES` раз (default 3) и берёт Mode. Env: `CLASSIFIER_VOTES`.

**Soft-label workflow**: если LLM предлагает тип вне `VALID_TYPES` — аппендит в `data/task_type_candidates.jsonl` (ноль LLM-вызовов).

### ModelRouter

Dataclass, маршрутизирует задачу на конкретную модель. Поля: `default`, `classifier`, legacy per-type поля, `extra_models` dict для новых типов из реестра, `configs` dict.

- `resolve(task_text)` — regex-only (без LLM)
- `resolve_after_prephase(task_text, pre)` — с LLM + vault_hint (AGENTS.MD + wiki hints для inbox/queue)
- `_adapt_config(cfg, task_type)` — применяет `ollama_options_<type>` overlay

## Env-переменные

- `CLASSIFIER_VOTES` — кол-во голосов на CC тире (default: 3 для CC, 1 для остальных)
- `CLASSIFIER_MAX_TOKENS` — max tokens для CoT (default: 256)

## Связанные концепции

- [[dispatch]] — `call_llm_raw` используется для LLM-fallback
- [[task-types]] — реестр типов задач из `data/task_types.json`
- [[orchestrator]] — создаёт `ModelRouter` и передаёт в `ClassifierAgent`
