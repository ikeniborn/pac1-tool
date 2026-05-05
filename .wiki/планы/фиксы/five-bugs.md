---
wiki_title: "Five Bug Fixes Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-05-04-five-bugs.md"
wiki_updated: "2026-05-06"
tags: [fix, dspy, temporal, crm, evaluator, feedback-loop]
---

# Five Bug Fixes

**Источник:** `docs/superpowers/plans/2026-05-04-five-bugs.md`

## Цель

Исправить 5 блокирующих проблем, ломающих DSPy feedback loop, temporal reasoning, CRM classification и evaluator rejection cycle.

## Пять багов

### Bug 1: DSPy feedback loop не работает
`record_example()` записывает данные, но `POSTRUN_OPTIMIZE` никогда не включается автоматически.  
**Фикс:** В `agent/postrun.py` — auto-trigger optimize если `len(examples) >= MIN_EXAMPLES` и `POSTRUN_OPTIMIZE=1` в env.

### Bug 2: Temporal reasoning — нет дельты от vault date
Агент знает `VAULT_DATE` но не вычисляет `ESTIMATED_TODAY`.  
**Фикс:** В prephase — вычислять `ESTIMATED_TODAY = VAULT_DATE + max_gap_days` где `max_gap_days` из `data/wiki/pages/temporal.md`.

### Bug 3: CRM classification неустойчива
`crm` задачи иногда классифицируются как `lookup`.  
**Фикс:** Улучшить fast-path regex в `classify_task()` для CRM: `r"update.*contact|set.*last_contacted|crm"`.

### Bug 4: Evaluator rejection cycle
Evaluator отклоняет → агент пробует снова → снова отклоняет → OUTCOME_ERR_INTERNAL.  
**Фикс:** Счётчик `evaluator_rejects`. После 2 rejects → accept best attempt + log warning.

### Bug 5: POSTRUN_OPTIMIZE порог слишком высок
`MIN_EXAMPLES=50` — нереально для тестов. После каждого full run (~43 задачи) будет только ~43 примера.  
**Фикс:** `MIN_EXAMPLES=20`.

**Ключевые файлы:** `agent/postrun.py`, `agent/prephase.py`, `agent/classifier.py`, `agent/evaluator.py`
