---
wiki_title: "Quality Degradation Fixes — P0+P1"
wiki_status: developing
wiki_sources:
  - "docs/superpowers/plans/2026-05-05-quality-degradation-fixes.md"
wiki_updated: "2026-05-06"
tags: [fix, wiki, graph, context, mutation-scope, contract, quality, P0, P1]
---

# Quality Degradation Fixes — P0+P1

**Источник:** `docs/superpowers/plans/2026-05-05-quality-degradation-fixes.md`

## Цель

Закрыть P0+P1 fix'ы из анализа деградации качества §9: остановить отравление wiki/графа, обуздать рост контекста, реанимировать mutation_scope-гейт и поднять контракт-negotiate на CC tier.

## Связь

Источник: [[run5-all-tasks]] — анализ деградации качества по результатам пяти прогонов.

## Метрики

| Метрика | v4 baseline | Target |
|---|---|---|
| Score (avg 5 runs) | 51% | ≥55% |
| Failures "no answer" | 33% (run 5) | ≤20% |
| t42 "expected OK got CLARIFICATION" | 0/5 | ≥2/5 |
| Graph nodes growth per run | +150-180 | ≤+80 |
| Wiki page lines (errors/default.md) | 985 | ≤200 |

## Блоки фиксов

### Block A: Gate wiki/graph по outcome
`format_fragment` и `add_pattern_node` вызываются для провальных задач → отравление wiki/графа.  
**Фикс:** Гейт `if outcome == "OUTCOME_OK":` в `wiki.py:format_fragment` и `postrun.py:_do_graph_feedback`.

### Block C: Soft-limit роста страниц
Wiki страницы растут без ограничений — `default.md` 985 строк.  
**Фикс:** `_check_page_budget()` в `_llm_synthesize_aspects` — если страница > MAX_LINES → compress/truncate oldest fragments.

### Block G: Стеммер-dedup в wiki_graph
Дублирующиеся узлы с похожими тегами (tag overlap > 0.7) не мержатся.  
**Фикс:** `_find_near_duplicate()` — добавить стеммер-нормализацию тегов перед сравнением.

## Файловая структура

| Файл | Блок |
|---|---|
| `agent/wiki.py` | A: gate by outcome, C: soft-limit |
| `agent/wiki_graph.py` | G: стеммер-dedup |
| `agent/postrun.py` | A: gate add_pattern_node |
| `agent/loop.py` | mutation_scope gate |
| `agent/contract_phase.py` | CC-tier negotiate |
| `main.py` | wiring |
| `data/wiki/pages/lookup.md` | data sanitation |
