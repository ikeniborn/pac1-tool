---
wiki_sources:
  - "agent/evaluator.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - evaluator
  - dspy
aliases:
  - "evaluate_completion"
  - "VerifierAgent"
---

# Evaluator (agent/evaluator.py)

Критик-агент (FIX-218): перехватывает `ReportTaskCompletion` перед отправкой в harness и проверяет качество ответа через `dspy.ChainOfThought(EvaluateCompletion)`. Fail-open: любая ошибка LLM или парсинга → автоматическое одобрение.

## Основные характеристики

### Жёсткий гейт: verbatim-значения (FIX-218b)

`check_quoted_values_verbatim(task_text, writes)` — если в тексте задачи есть quoted-значение, заканчивающееся на терминальную пунктуацию (`.`, `,`, `!`, `?`, `;`, `:`), то хотя бы один write должен содержать это значение с пунктуацией. Защищает от паттерна "агент пишет без последней точки".

### Wiki-контекст в evaluator (FIX-367)

Два дополнительных InputField в `EvaluateCompletion`:
- `reference_patterns` — содержимое `data/wiki/pages/<task_type>.md` (разделы "Successful patterns" + "Verified refusals"), лимиты по wiki-качеству: nascent/developing/mature = 500/2000/4000 chars
- `graph_insights` — top-K узлов из `wiki_graph.retrieve_relevant`

Wiki/graph — ADVISORY: на конфликте с жёсткими правилами INBOX/ENTITY побеждают жёсткие правила.

### Env-переменные

- `EVALUATOR_WIKI_ENABLED` (default "1") — подключить wiki-контекст
- `WIKI_GRAPH_ENABLED` (default "1") — подключить graph-контекст
- `EVALUATOR_GRAPH_TOP_K` (default 5) — кол-во graph-узлов
- `EVALUATOR_WIKI_MAX_CHARS_NASCENT/DEVELOPING/MATURE` — лимиты символов по качеству

### Compiled program

Загружается из `data/evaluator_program.json` (оптимизируется через `scripts/optimize_prompts.py --target evaluator`). Fail-open если файл отсутствует.

## Связанные концепции

- [[wiki-graph]] — `retrieve_relevant` для graph_insights
- [[prompt-builder]] — аналогичная DSPy-архитектура для addendum
- [[loop]] — evaluator вызывается в `VerifierAgent` перед `report_completion`
