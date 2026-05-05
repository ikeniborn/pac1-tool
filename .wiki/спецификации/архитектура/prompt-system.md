---
wiki_sources:
  - docs/architecture/03-prompt-system.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, prompt, dspy, prephase, addendum]
---

# Prompt-система

Три слоя финального system prompt: статический базовый + discovery-контекст + DSPy-аддендум.

## Три слоя

1. **Слой 1 — `prompt.py` (статический)**: `_CORE` + task-type-specific блоки (`_EMAIL`, `_INBOX`, `_LOOKUP` и т.д.)
2. **Слой 2 — `prephase.py` (discovery)**: vault tree (level=2), AGENTS.MD, preloaded folders, vm.context, few-shot pair
3. **Слой 3 — `prompt_builder.py` (DSPy-динамический)**: 3–6 bullets задача-специфичного guidance

## Task-type → промпт-блоки

| Task type | Блоки (композиция) |
|---|---|
| `email` | `_CORE` + `_EMAIL` + `_LOOKUP` |
| `inbox` | `_CORE` + `_INBOX` |
| `queue` | `_CORE` + `_QUEUE` + `_INBOX` |
| `lookup` | `_CORE` + `_LOOKUP` |
| `capture` | `_CORE` + `_CAPTURE` |
| `crm` | `_CORE` + `_CRM` |
| `temporal` | `_CORE` + `_TEMPORAL` |
| `distill` | `_CORE` + `_DISTILL` |
| `preject` | `_CORE` + `_PREJECT` |

## Prephase: discovery

```
run_prephase():
  vm.tree(root=/, level=2) → vault layout
  vm.read(/AGENTS.MD) → folder semantics
  loop referenced folders: vm.list, vm.read non-template files
  vm.context() → {date, user, ...}
  log.append(system=base_prompt)
  log.append(user=tree+AGENTS.MD+context)
  log.append(assistant=few-shot response)
  log.append(user=real_task_text)
  → preserve_prefix = system + few-shot pair
```

## PromptAddendum signature (DSPy)

```
Input: task_text, vault_tree_text, vault_context_summary
Output: addendum (3-6 bullets)
  - Bullet 1: какую папку исследовать первой
  - Bullet 2: ключевой риск / правило валидации
  - Bullet 3+: task-specific поля или ограничения
  - НИКОГДА не копировать буквальные значения из task
```

## Ключевые принципы

- **Discovery-first** — никаких хардкод-путей
- **Fail-open gates** — нечёткая задача → OUTCOME_NONE_CLARIFICATION
- **Сохранение контекста** — system prompt + few-shot pair никогда не компактизуются

## Конфигурация

```bash
PROMPT_BUILDER_ENABLED=1          # включить DSPy-аддендум
PROMPT_BUILDER_MAX_TOKENS=500     # бюджет токенов
MODEL_PROMPT_BUILDER=...          # отдельная модель
```
