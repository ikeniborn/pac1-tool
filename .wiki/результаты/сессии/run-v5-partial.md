---
wiki_title: "Прогоны v5 — smoke run (прерван)"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-05_v5_partial.md
wiki_domain: результаты
wiki_type: run-session
tags: [run-analysis, smoke-run, quality-fixes, contract-phase, block-a-g, v5]
---

# Прогоны v5 — smoke run (прерван)

**Date:** 2026-05-05. Запуск: 19:22:08, убит через 60 минут (20:22).  
**Branch:** `quality-fixes` (worktree). **Baseline SHA:** `ea3f26c`.  
**Финализировано задач:** 3 (t23 × 2, t34).

Smoke run запущен после реализации 13 коммитов (Blocks A–G) из плана `quality-degradation-fixes`.

## Реализованные блоки (Blocks A–G)

| Block | Назначение | Статус |
|---|---|---|
| A — anti-poisoning | Фильтрация OUTCOME_NONE_CLARIFICATION из graph_feedback | ✅ работает |
| B — wiki sanitation | Очистка lookup.md от poison-паттернов | ✅ частично (errors/default.md не покрыт) |
| C — soft budget | WIKI_PAGE_MAX_LINES warning-only | ✅ работает |
| D — confidence decay | epsilon 0.05→0.15, min_confidence 0.2→0.4 | ✅ graph file shrunk -3.7% |
| E — mutation_scope gate | Гейт переключён с мёртвого evaluator_only | ✅ активен |
| F — negotiate contract | CONTRACT_MODEL → включает negotiate на всех тирах | ❌ ломает throughput |
| G — stemmed dedup | `_stem()` в wiki_graph normalize/token_overlap | ✅ unit tests OK |

## Ключевые метрики smoke run

| Метрика | Значение |
|---|---|
| Финализированных задач | 3 |
| contract rounds всего | 113 |
| Уникальных задач, прошедших negotiate | 40 |
| max_rounds=3 exceeded | 19 (47% не сошлись) |
| Граф nodes до/после | 1122 / 1122 (без роста — Block A работает) |
| Граф файл-размер | 578 894 → 557 569 байт (-3.7%, Block D работает) |
| errors/default.md | 985 → 962 строки (цель: ≤ 200) |
| Pace vs v4 | ~3 задачи / 60 мин vs v4 ~50 задач / 30–60 мин → деградация ×5–10 |

## Диагностированные проблемы

### Concern 1 — Block F overhead (CRITICAL)

Задан `MODEL_CONTRACT=minimax-m2.7:cloud` в `.env`. После Block F каждая задача запускает negotiate: 3 раунда × 2 LLM-вызова = до 6 calls перед основным циклом. minimax-m2.7 не сходится в 47% случаев (max_rounds exceeded → fallback в default contract).

**Импакт:** +25–75 мин к суммарному времени на 50 задач.  
**Фикс:** закомментировать `MODEL_CONTRACT` в `.env` — Block F остаётся в коде как opt-in.

### Concern 2 — Block B не покрывает errors/default.md (HIGH)

Все три regex'а sanitize_wiki.py были lookup-специфичны. `errors/default.md` содержит 117 fragment-ID с разнородной структурой. 40 фрагментов с пустым outcome — ранние ингесты без финального outcome. Цель ≤ 200 строк не достигнута (реальность: 962).

**Фикс:** добавить regex для drop'а блоков с `outcome: ` пустым в sanitize_wiki.py.

## Рекомендации перед re-run

1. Закомментировать `MODEL_CONTRACT` в `.env`
2. Расширить sanitize_wiki.py: drop fragments с `outcome: ` пустым из errors/default.md
3. Запустить полный 5-run после фиксов

## P2-блоки (отложены)

step-budget split, tracking-based feedback, contract block visibility — не реализованы в v5.

## Статус проверки плановых целей

| Цель v5 | Статус |
|---------|--------|
| avg score ≥ 55% (vs v4 51%) | не проверено — run прерван |
| no answer provided ≤ 20% (vs v4 33%) | не проверено |
| graph growth/run ≤ +80 (vs v4 +160) | ✅ 0 роста за 60 мин (Block A работает) |
| t42 ≥ 2/5 (vs v4 0/5) | не проверено |

## Связи

- [[результаты/фиксы/blocks-a-g-quality]] — детали реализации блоков
- [[результаты/проблемы/contract-negotiate-overhead]] — Concern 1
- [[результаты/проблемы/errors-default-bloat]] — Concern 2
- [[результаты/сессии/run-v4-all-tasks]] — baseline для сравнения
