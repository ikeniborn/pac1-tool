---
wiki_title: "Contract negotiate overhead (Block F) — деградация throughput"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-05_v5_partial.md
wiki_domain: результаты
wiki_type: system-problem
tags: [contract, negotiate, throughput, block-f, minimax, system-problem]
---

# Contract negotiate overhead (Block F) — деградация throughput

**Статус:** диагностирована в v5 smoke run. Требует fix перед re-run.

## Симптом

После Block F (`1ceb4be`) при заданном `MODEL_CONTRACT=minimax-m2.7:cloud` каждая задача запускает contract negotiate: 3 раунда × 2 LLM-вызова = до 6 calls перед основным циклом агента.

**Статистика smoke run (60 мин, 40 задач прошли negotiate):**
- 113 contract rounds всего → 2.8 раунда/задача в среднем
- 19/40 (47%) задач упёрлись в `max_rounds=3 exceeded` без consensus
- Pace: ~3 задачи за 60 мин vs v4 ~50 задач за 30-60 мин → деградация ×5-10

## Пример из лога (t41)

```
[t41] [contract] round 1: executor.agreed=False evaluator.agreed=False
[t41] [contract] round 2: executor.agreed=False evaluator.agreed=True
[t41] [contract] round 3: executor.agreed=False evaluator.agreed=False
[t41] [contract] max_rounds=3 exceeded — using partial from last round
```

При exceeded fallback в default contract — то же что без negotiate, но дороже.

## Корневая причина

minimax-m2.7 как negotiation LM плохо коррелирует: executor.agreed остаётся False в 47% случаев. Модель не предназначена для negotiate-роли.

## Фикс (немедленный)

Закомментировать `MODEL_CONTRACT` в `.env`. Block F остаётся в коде как opt-in feature — при пустом MODEL_CONTRACT CC-tier возвращается к hard-skip.

## Долгосрочные варианты

1. Использовать другую модель для negotiate (e.g., claude-haiku-4-5) — она быстрее сходится.
2. Повысить `max_rounds` с 3 до 5 — но увеличит overhead при несхождении.
3. Переработать формат objections для лучшей сходимости.

## Связи

- [[результаты/сессии/run-v5-partial]] — контекст диагностики
- [[результаты/фиксы/blocks-a-g-quality]] — Block F описание
