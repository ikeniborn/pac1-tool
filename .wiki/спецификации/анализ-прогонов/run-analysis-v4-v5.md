---
wiki_sources:
  - docs/run_analysis_2026-05-04_v3.md
  - docs/run_analysis_2026-05-04_v4.md
  - docs/run_analysis_2026-05-05_v5_partial.md
  - docs/superpowers/specs/2026-05-05-quality-degradation-analysis.md
wiki_updated: 2026-05-05
wiki_status: developing
tags: [run-analysis, quality-degradation, wiki-poisoning, minimax, benchmark]
---

# Анализ прогонов v3, v4, v5 (2026-05-04..05)

## Executive Summary

5 последовательных прогонов ALL-tasks (v4): **49% → 60% → 53% → 51% → 51%** с пиком во 2-м прогоне и монотонной деградацией. Знание накапливалось:

| Метрика | После run 1 | После run 5 | Прирост |
|---|---|---|---|
| Граф узлов | 489 | 1126 | +130% |
| Граф рёбер | 744 | 2065 | +177% |
| Wiki фрагментов | 128 | 338 | +163% |
| DSPy примеров | 80 | 213 | +166% |

**Знание накапливается, качество — нет.**

## «No answer provided» — доминирующий failure-mode

| Прогон v4 | Доля «no answer» |
|---|---|
| 1 | 21% |
| 2 | 16% |
| 3 | 19% |
| 4 | 30% |
| 5 | 33% |

Причина: раздутый prefill (wiki/graph/errors) → agent тратит все 30 шагов на discovery и не успевает сформировать ответ.

## Стабильно проваленные задачи (0/5)

| Task | Failure pattern |
|---|---|
| t03, t04 | no answer provided |
| t13 | JSON mismatch `next_follow_up_on` (CRM-формула без +8) |
| t14 | JSON mismatch `to:` в outbox (wrong recipient) |
| t37 | no answer / NONE_CLARIFICATION ↔ OK |
| t41 | wrong date (temporal arithmetic) |
| t42 | OK ожидался, агент даёт NONE_CLARIFICATION |

## Корневые причины (ранжированы)

| Ранг | Причина | P |
|---|---|---|
| 1 | **Wiki-poisoning lookup.md**: NONE_CLARIFICATION как успех → t42 стабильно 0/5 | P0 |
| 2 | **Контекстное распухание**: errors/default.md=985 строк → no_answer растёт | P0 |
| 3 | **Confidence decay слишком мягкий** (ε=0.05, min=0.2): ~8 негативных trials чтобы убить узел | P0 |
| 4 | **FIX-437 dead-code**: `evaluator_only=True` нигде не присваивается → consecutive_contract_blocks никогда не инкрементируется | P1 |
| 5 | **Default contract на CC tier**: skip negotiate → нет task-specific guidance | P1 |
| 6 | **Pattern-extractor на любой score=1.0**: паттерны отказа промотируются как успех | P1 |

## v5 Smoke Run — что исправлено

13 коммитов в worktree `quality-fixes`:

| Block | Фикс |
|---|---|
| A | Anti-poisoning: OUTCOME_NONE_CLARIFICATION не попадает в success-pages |
| B | Wiki sanitation: `scripts/sanitize_wiki.py` удалил poison из lookup.md |
| C | `WIKI_PAGE_MAX_LINES` soft budget — warning-only |
| D | Confidence decay: epsilon 0.05→0.15, min_confidence 0.2→0.4 |
| E | Mutation_scope gate: переключён с dead `evaluator_only` на `not is_default and mutation_scope` |
| F | Negotiate на CC tier: при заданном `MODEL_CONTRACT` |
| G | Stemmed dedup в wiki_graph |

## v5 Проблемы (смоук-ран)

**Concern 1 (CRITICAL):** Block F с `MODEL_CONTRACT=minimax-m2.7:cloud` даёт ~6 LLM calls before execution на каждую задачу. 47% задач (19/40) не сошлись за 3 раунда → fallback в default contract. Throughput деградировал ×5–10.

**Concern 2 (HIGH):** `errors/default.md` = 962 строки после ран (target 200). Block B покрывал только lookup-специфичные паттерны. 40 фрагментов с пустым outcome не удалены.

**Рекомендации перед следующим прогоном:**
1. Закомментировать `MODEL_CONTRACT` в `.env`
2. Расширить `sanitize_wiki.py` для drop fragments с пустым outcome из errors/default.md
3. Запустить чистый 5-run

## Эффективность графа

**Работает:** Hard cross-type filter (FIX-433), confidence feedback по injected_node_ids, near-duplicate dedup (FIX-421)

**Не работает:**
- Confidence decay слишком мягкий → отравленные узлы переживают trials
- Pattern-extractor бьёт по любому score=1.0 (нужен фильтр на outcome=OUTCOME_OK)
- Инфляция узлов ~150–180/прогон без ассимптоты
- Edges создаются, но при retrieval не используются (граф работает как лексический индекс)

## v3 Mini-run (t42, t43, t40, t41, t13 × 5 прогонов)

Старт: граф 41 узлов, wiki 7 страниц. Итог: 0/5 → 1/5 → 0/5 → ... — t42 и t41 стабильно 0/5 во всех прогонах. t40 win rate 1/5.
