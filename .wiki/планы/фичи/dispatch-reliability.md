---
wiki_title: "Dispatch Reliability + Contract Objection Types"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-30-dispatch-reliability-and-prephase-lazy.md"
wiki_updated: "2026-05-06"
tags: [dispatch, reliability, contract, objection, broken-pipe]
---

# Dispatch Reliability + Contract Objection Types

**Источник:** `docs/superpowers/plans/2026-04-30-dispatch-reliability-and-prephase-lazy.md`

## Цель

Исправить два reliability gap из t43 post-mortem: (1) `[Errno 32] Broken Pipe` не обрабатывается retry и нет fallback модели; (2) contract evaluator расценивает informational notes как blocking objections → лишние раунды и преждевременное исчерпание max_rounds.

## Проблема 1: Broken Pipe в dispatch

`dispatch.py` не обрабатывает `BrokenPipeError` в retry logic. Если OpenRouter закрывает соединение — падение без fallback.

**Фикс:** Добавить `BrokenPipeError` в список ретраиваемых исключений в `openrouter_complete`. Ретрай с exponential backoff, max 3.

## Проблема 2: Informational notes как блокирующие objections

Contract evaluator возвращает objections типа "I note that..." — не блокирующие, но парсер считает их objections и добавляет раунды.

**Фикс:** Разделить `objections` (blocking) и `notes` (non-blocking) в `ContractEvalResponse`. Notes не инкрементируют round counter.

```python
class ContractEvalResponse(BaseModel):
    approved: bool
    objections: list[str] = []   # blocking — требуют ответа
    notes: list[str] = []        # informational — не блокируют
```

**Ключевые файлы:** `agent/dispatch.py`, `agent/contract_phase.py`
