---
wiki_type: design-decision
wiki_status: developing
wiki_sources:
  - scripts/CLAUDE.md
wiki_created: 2026-05-14
wiki_updated: 2026-05-14
tags:
  - ecom1-agent
  - eval
  - deduplication
  - design-decision
---

# Eval Optimization Deduplication

Стратегия предотвращения дублирующих рекомендаций в цикле `eval_log → propose_optimizations → data/`.

## Проблема

Один и тот же паттерн ошибки может встречаться в нескольких задачах или в нескольких прогонах — без дедупликации LLM-синтезатор генерирует структурно идентичные правила/gates/патчи, засоряя `data/`.

## Решение: двухуровневая дедупликация

### Уровень 1: Content-hash dedup (exact duplicates)

Каждая обработанная запись получает SHA-256 хэш от `(channel|task_text|raw_rec)`. Хэши хранятся в `data/.eval_optimizations_processed`.

- Повторные запуски автоматически пропускают уже обработанные записи.
- В `--dry-run` режиме обработанный set не изменяется.

### Уровень 2: LLM cluster (semantic duplicates)

`_cluster_recs` выполняет один LLM-вызов, который объединяет семантически эквивалентные рекомендации из разных задач в единую представительную запись.

### Уровень 3: Existing-content injection (cross-run duplicates)

Каждый синтезатор получает в системный промпт содержимое уже существующих файлов (`_existing_rules_text`, `_existing_security_text`, `_existing_prompts_text`). LLM отвечает `null` если рекомендация уже покрыта — запись помечается обработанной, файл не создаётся.

**Инвариант: `_existing_*` хелперы не удалять** — без них синтезаторы игнорируют уже существующие правила.

## Validation Gate

Перед записью кандидата — harness re-run с инжектированной рекомендацией (`validate_recommendation`):

- `validation_score >= original_score` → записать
- Нет baseline → записать с предупреждением
- Задача не в trial set → пропустить

Baseline читается через `read_original_score` из последней не-`validate-*` директории под `logs/`.

## Связанные модули

- [[propose-optimizations]] — реализует всю цепочку
- `evaluator.py` — источник рекомендаций в `eval_log.jsonl`
- `agent.knowledge_loader` — загрузка `_existing_*` контента
