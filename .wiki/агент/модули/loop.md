---
wiki_sources:
  - "agent/loop.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - loop
aliases:
  - "run_loop"
  - "основной цикл"
---

# Loop (agent/loop.py)

Основной цикл выполнения задачи. Самый крупный файл агента (>41k токенов). Управляет шагами агента: LLM-вызов → парсинг JSON → dispatch инструмента → stall-detection → compaction → evaluator-review.

## Основные характеристики

### Ограничения

- `TASK_TIMEOUT_S` (default 180s) — hard timeout на всю задачу
- `≤30 шагов` максимум
- `EVAL_MAX_REJECTIONS` (default 2) — evaluator отклоняет не более N раз перед force-submit

### LLM-вызов в цикле

Поддерживает все четыре тира из dispatch.py. При CC тире — `_cc_complete`. Retry на transient errors (`TRANSIENT_KWS`) и hard connection errors (`HARD_CONNECTION_KWS`, cap 1 retry). FIX-417: `MODEL_FALLBACK` при полном отказе primary модели.

### Безопасность в цикле

Каждый шаг: инъекционная нормализация (`_normalize_for_injection`), проверка `_INJECTION_RE`, контаминация outbox (`_CONTAM_PATTERNS`), формат-гейт inbox (`_FORMAT_GATE_RE`), inbox инъекции (`_INBOX_INJECTION_PATTERNS`), write scope (`_check_write_scope`), write payload injection (`_check_write_payload_injection`).

### Stall-detection

Вызывает `_check_stall` с fingerprints, steps_since_write, error_counts, step_facts, contract_plan_steps. При stall — `_handle_stall_retry`.

### Evaluator в цикле

`evaluate_completion` вызывается при каждом `report_completion`. При rejection — инжектирует feedback в следующее user-сообщение. После `EVAL_MAX_REJECTIONS` — принудительный submit.

### Log compaction

`_compact_log` с `preserve_prefix` при превышении token budget. `_compact_tool_result` для экономии контекста.

## Env-переменные

- `TASK_TIMEOUT_S` (default 180)
- `EVALUATOR_ENABLED` (default "1")
- `EVAL_SKEPTICISM` (default "mid") — low/mid/high
- `EVAL_EFFICIENCY` (default "mid")
- `EVAL_MAX_REJECTIONS` (default 2)
- `ROUTER_FALLBACK` (default "CLARIFY") — CLARIFY|EXECUTE
- `ROUTER_MAX_RETRIES` (default 2)
- `LOG_LEVEL=DEBUG` — полный лог LLM-ответов

## Связанные концепции

- [[dispatch]] — LLM тиры и PCM dispatch
- [[security]] — все security-функции импортируются из security.py
- [[stall]] — `_check_stall` и `_handle_stall_retry`
- [[log-compaction]] — `_compact_log`, `_StepFact`, `build_digest`
- [[evaluator]] — `evaluate_completion` вызывается при report_completion
