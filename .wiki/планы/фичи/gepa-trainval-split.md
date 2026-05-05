---
wiki_title: "GEPA Train/Val Split Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-26-gepa-trainval-split.md"
wiki_updated: "2026-05-06"
tags: [gepa, dspy, optimizer, trainval]
---

# GEPA Train/Val Split

**Источник:** `docs/superpowers/plans/2026-04-26-gepa-trainval-split.md`

## Цель

Добавить детерминированный train/val split внутри `GepaBackend.compile()`, чтобы GEPA получал отдельный valset и не выдавал WARNING "No valset provided".

## Связь

Зависит от [[gepa-integration]] (Task 7 — базовый GepaBackend должен быть готов).

## Суть изменения

В `GepaBackend.compile()` перед передачей trainset в GEPA — выделить 20% (детерминированно, shuffle с fixed seed) в valset. Передать GEPA параметром `valset=` если API поддерживает, или обработать внутри.

**Ключевые файлы:**
- `agent/optimization/gepa_backend.py` — добавить `_split_trainval(trainset, val_ratio=0.2, seed=42)`
- `tests/test_optimization_gepa_split.py` — TDD тест на split

## Паттерн split

```python
def _split_trainval(trainset, val_ratio=0.2, seed=42):
    rng = random.Random(seed)
    shuffled = list(trainset)
    rng.shuffle(shuffled)
    split = max(1, int(len(shuffled) * (1 - val_ratio)))
    return shuffled[:split], shuffled[split:]
```
