---
wiki_sources:
  - docs/superpowers/specs/2026-04-28-remove-researcher-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, fix, researcher, refactor]
---

# Remove RESEARCHER Mode

**Дата:** 2026-04-28 | **Approach:** A — Full surgical deletion

Полное удаление RESEARCHER multi-cycle режима из кодовой базы.

## Что удаляется

**Файлы (полностью)**:
- `agent/researcher.py` — outer-cycle orchestrator
- `agent/reflector.py` — per-cycle reflection (только для researcher)

**Код в `agent/__init__.py`**:
- `_RESEARCHER_MODE = ...`
- Весь `if _RESEARCHER_MODE: ... return run_researcher(...)` блок

**Код в `agent/loop.py`**:
- Параметры `researcher_mode`, `researcher_breakout_check`
- Unwrap timeout/stall/evaluator conditions от `if not st.researcher_mode`
- Удалить mid-cycle breakout block

**Код в `main.py`**:
- Два score-gated researcher promotion блока после `end_trial()`

**`.env.example`**: весь блок `RESEARCHER_*` (~40 переменных)

## Что остаётся без изменений

`wiki.py`, `wiki_graph.py`, `evaluator.py`, `stall.py`, `classifier.py`, `prompt_builder.py`, `data/wiki/pages/`, `data/dspy_examples.jsonl` — все нормальные компоненты.

`promote_successful_pattern()` и `promote_verified_refusal()` — остаются, становятся стандартным поведением вместо researcher-exclusive.

## Чистка данных

```bash
rm -rf data/wiki/fragments/research/
rm -rf data/wiki/archive/research_negatives/
rm -rf logs/researcher/
echo '{"nodes": {}, "edges": []}' > data/wiki/graph.json
```

`data/wiki/pages/` — оставить (промотированные паттерны остаются как wiki knowledge).
