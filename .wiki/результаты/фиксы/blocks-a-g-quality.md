---
wiki_title: "Blocks A–G: Quality Degradation Fixes (P0+P1)"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-05_v5_partial.md
wiki_domain: результаты
wiki_type: fix-block
tags: [quality-fixes, block-a, block-b, block-c, block-d, block-e, block-f, block-g, smoke-run]
---

# Blocks A–G: Quality Degradation Fixes (P0+P1)

**Branch:** `quality-fixes` (worktree). **Baseline:** `ea3f26c`.  
**Plan:** `docs/superpowers/plans/2026-05-05-quality-degradation-fixes.md`  
**Тесты:** 567 passed, 2 skipped (13 коммитов)

## Обзор блоков

### Block A — Anti-poisoning ingest filter (P0) ✅

| Коммит | Что |
|---|---|
| `849b4f2` | main.py: пробрасывает outcome через graph_feedback_queue payload |
| `c061e8e` | agent/postrun.py: pattern-node ingest гейчен outcome=OUTCOME_OK |
| `8742549` | agent/wiki.py:format_fragment: refusal-фрагменты роутятся в refusals/<type> |

**Эффект:** OUTCOME_NONE_CLARIFICATION больше не попадает в success-pages и не создаёт поддельных pattern-узлов.  
**Верификация smoke run:** граф nodes стабильны (1122 → 1122 за 60 мин работы).

### Block B — Wiki sanitation (P0) ✅ (с gap)

| Коммит | Что |
|---|---|
| `8a5089e` | Создан scripts/sanitize_wiki.py (one-shot инструмент) |
| `8bd9406` | Применение: lookup.md −2767 байт, 4 узла в архив |

**Применённые regex:** `_POISON_BLOCK`, `_VERIFIED_REFUSAL_BLOCK`, `_LOOKUP_TASK_BLOCK`.  
**Gap:** errors/default.md (985 строк) не покрыта — regex были lookup-специфичны. Цель ≤ 200 строк не достигнута.

### Block C — WIKI_PAGE_MAX_LINES soft budget (P0) ✅

| Коммит | Что |
|---|---|
| `992edae` | agent/wiki.py:_llm_synthesize_aspects: бюджет передан в синтез-промпт; warning-only _check_page_budget |

**Верификация:** warnings корректно фиксируются (errors/default.md 962 строки > 200).

### Block D — Confidence decay tightening (P0) ✅

| Коммит | Что |
|---|---|
| `07dd16e` | .env.example: epsilon 0.05→0.15, min_confidence 0.2→0.4 |

**Верификация:** graph file shrunk 578 894 → 557 569 байт (-3.7%).

### Block E — Reanimate mutation_scope gate (P1) ✅

| Коммит | Что |
|---|---|
| `3730c8a` | agent/loop.py: гейт переключён с мёртвого evaluator_only на not is_default and mutation_scope |

**Верификация:** гейт активен. Реальных triggers не наблюдалось в 3 финализированных задачах.

### Block F — Negotiate contract на CC tier (P1) ❌ ломает throughput

| Коммит | Что |
|---|---|
| `1ceb4be` | agent/contract_phase.py: early-return пропадает если задан MODEL_CONTRACT |
| `f699e3f` | .env.example: документация MODEL_CONTRACT |

**Problem:** при MODEL_CONTRACT=minimax-m2.7:cloud каждая задача делает 3 раунда negotiate. 47% задач не сходятся → max_rounds exceeded. Деградация throughput ×5-10.  
**Фикс:** закомментировать MODEL_CONTRACT в .env.

### Block G — Stemmed dedup (P1) ✅

| Коммит | Что |
|---|---|
| `144daec` | agent/wiki_graph.py: добавлен _stem; обновлены _normalize и _token_overlap |
| `d3913c6` | Усиление _stem для trailing-e и double-consonant |

**Верификация:** unit tests OK. On-vault эффект не виден из-за прерванного run.

## P2-блоки (не реализованы в v5)

- step-budget split
- tracking-based feedback
- contract block visibility

## Что нужно до re-run

1. Закомментировать MODEL_CONTRACT в .env (Block F фикс)
2. Расширить sanitize_wiki.py: drop fragments с `outcome: ` пустым из errors/default.md (Block B gap)
3. Запустить полный 5-run и сравнить с v4 baseline (target ≥ 55%)

## Связи

- [[результаты/сессии/run-v5-partial]] — smoke run с диагностикой
- [[результаты/проблемы/contract-negotiate-overhead]] — Concern 1 (Block F)
- [[результаты/проблемы/errors-default-bloat]] — Concern 2 (Block B gap)
- [[результаты/проблемы/antipattern-poisoning]] — Block A решает
