---
wiki_title: "Run5 All Tasks Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-05-04-run5-all-tasks.md"
wiki_updated: "2026-05-06"
tags: [audit, benchmark, run5, all-tasks, regression]
---

# Run5 All Tasks

**Источник:** `docs/superpowers/plans/2026-05-04-run5-all-tasks.md`

## Цель

Запустить 5 последовательных прогонов по всем задачам бенчмарка (`make run`), с захватом состояния после каждого и сводным отчётом.

## Алгоритм

```
For run in 1..5:
  1. Зафиксировать состояние: graph.json nodes count, dspy_examples.jsonl count
  2. make run
  3. Записать scores по задачам, win_rate, failures
  4. Проверить: росли ли pages/*.md? rosли ли graph nodes?
  5. Сравнить с предыдущим run
```

## Метрики для capture

- `win_rate` (по SCORE SUMMARY в stdout)
- Scores per task (t01..t43)
- Graph nodes count after run
- Wiki pages line count after run
- `dspy_examples.jsonl` count after run

## Цель эксперимента

Проверить: накапливается ли знание с каждым прогоном? Растёт ли win_rate? Стабилен ли pipeline?

## Связь

Результаты Run5 → источник для анализа деградации качества → [[quality-degradation-fixes]].
