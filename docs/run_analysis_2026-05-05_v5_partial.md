# v5 Partial Run Analysis (Smoke Test Aborted)

**Date:** 2026-05-05
**Run mode:** Single smoke run, aborted at 60 min after diagnosing two blockers
**Branch:** `quality-fixes` (worktree)
**Baseline branch SHA:** `ea3f26c`
**Aborted at:** task t40 still active, only 3 fully-finalized tasks
**Source log:** `logs/v5/run_1.log` (21 MB, 132K+ lines)

---

## 1. Что сделано в этой итерации

13 коммитов в worktree `quality-fixes` реализуют 7 блоков из плана `docs/superpowers/plans/2026-05-05-quality-degradation-fixes.md`.

### Block A — Anti-poisoning ingest filter (P0)
| Commit | Что |
|---|---|
| `849b4f2` | `main.py`: пробрасывает `outcome` через graph_feedback_queue payload |
| `c061e8e` | `agent/postrun.py`: pattern-node ingest гейчен `outcome=OUTCOME_OK` |
| `8742549` | `agent/wiki.py:format_fragment`: refusal-фрагменты роутятся в `refusals/<type>`, не в `<type>` |

**Эффект:** OUTCOME_NONE_CLARIFICATION больше не попадает в success-pages и не создаёт поддельных pattern-узлов.

### Block B — Wiki sanitation (P0)
| Commit | Что |
|---|---|
| `8a5089e` | Создан `scripts/sanitize_wiki.py` (один-shot инструмент) |
| `041ff9d` | Style-fix: убраны unused subn-counters |
| `8bd9406` | Применение sanitize: lookup.md −2767 байт, 4 узла из графа в архив |

**Применённые regex:**
- `_POISON_BLOCK` — "captured … N days ago" поисковая отрава
- `_VERIFIED_REFUSAL_BLOCK` — секции "## Verified refusal"
- `_LOOKUP_TASK_BLOCK` — "## Lookup Task:" процедуры

### Block C — WIKI_PAGE_MAX_LINES soft budget (P0)
| Commit | Что |
|---|---|
| `992edae` | `agent/wiki.py:_llm_synthesize_aspects`: бюджет передан в синтез-промпт; warning-only функция `_check_page_budget` |

### Block D — Confidence decay tightening (P0)
| Commit | Что |
|---|---|
| `07dd16e` | `.env.example`: epsilon 0.05→**0.15**, min_confidence 0.2→**0.4** |

### Block E — Reanimate mutation_scope gate (P1)
| Commit | Что |
|---|---|
| `3730c8a` | `agent/loop.py`: гейт переключён с dead `evaluator_only` на `not is_default and mutation_scope` |

### Block F — Negotiate contract на CC tier (P1)
| Commit | Что |
|---|---|
| `1ceb4be` | `agent/contract_phase.py`: early-return пропадает если задан `MODEL_CONTRACT` |
| `f699e3f` | `.env.example`: документация MODEL_CONTRACT |

### Block G — Stemmed dedup (P1)
| Commit | Что |
|---|---|
| `144daec` | `agent/wiki_graph.py`: добавлен `_stem`; обновлены `_normalize` и `_token_overlap` |
| `d3913c6` | Усиление `_stem` для trailing-e и double-consonant |

**Тесты:** 567 passed, 2 skipped (исключены 2 предсуществующих failure не относящихся к плану).

---

## 2. Результаты smoke run

| Метрика | Значение |
|---|---|
| Запущен | 19:22:08 |
| Убит | 20:22 (60 мин) |
| Финализированных задач | 3 (t23 ×2, t34) |
| Уникальных task ID видно в логе | 43 (t01..t43) |
| `[contract] round` строк | 113 |
| Уникальных задач, прошедших negotiate | 40 |
| `max_rounds=3 exceeded` | 19 (47% не сошлись) |
| Postrun отработал (wiki-lint cycles) | минимум 1 |
| Граф nodes до/после | 1122 / 1122 (без роста) |
| Граф файл-размер | 578 894 → 557 569 байт (-3.7%, decay сработал) |
| `errors/default.md` лимит-warning | 962 строки > 200 (target) |

**Ключевая статистика:** при v4-baseline 50 задач за 30-60 мин текущий pace составил ~3 задачи за 60 мин — деградация × 5-10.

---

## 3. Диагностированные проблемы

### Concern 1 — Block F overhead на CC-tier (CRITICAL)

**Симптом:** 113 contract-rounds на ~40 задач = в среднем 2.8 раунда/задача. Из них 19 (47%) упёрлись в `max_rounds=3 exceeded` без consensus.

**Причина:** в локальном `.env` задан `MODEL_CONTRACT=minimax-m2.7:cloud`. После Block F (`1ceb4be`) условие пропуска negotiate стало:
```python
if model.startswith("claude-code/") and not os.environ.get("MODEL_CONTRACT"):
```
То есть: при заданном `MODEL_CONTRACT` каждая задача делает **3 раунда × 2 LLM-вызова = до 6 calls** перед основным циклом, вместо 0 в v4. И у minimax-m2.7 negotiate часто не сходится за 3 раунда.

**Импакт:** ~30-90с overhead на задачу × 50 задач = +25-75 мин к общему времени. Плюс token-budget burn без прогресса (когда max_rounds exceeded → fallback в default contract, как и без negotiate, только дороже).

**Sample evidence из логов:**
```
[t41] [contract] round 1: executor.agreed=False evaluator.agreed=False
[t41] [contract] round 2: executor.agreed=False evaluator.agreed=True
[t41] [contract] round 3: executor.agreed=False evaluator.agreed=False
[t41] [contract] max_rounds=3 exceeded — using partial from last round
```

**Hypothesis о root cause:** minimax-m2.7 как negotiation LM плохо коррелирует со суждениями evaluator-роли (executor.agreed остаётся False). Возможно нужна другая модель (e.g., Haiku 4.5) для negotiate, или повышение max_rounds, или другой формат objections.

### Concern 2 — Block B sanitization не покрывает errors/default.md (HIGH)

**Симптом:** `errors/default.md` имеет 985 строк до и 962 после smoke run (компакция wiki-lint'ом снизила на 23). Целевой лимит плана — 200. Block B (sanitize_wiki.py) **не уменьшил** этот файл.

**Причина:** все три regex'а sanitize_wiki.py были lookup-специфичны:
- `_POISON_BLOCK`: "captured X days ago" — встречается только в lookup-page
- `_VERIFIED_REFUSAL_BLOCK`: блок "## Verified refusal" с outcome NONE_CLARIFICATION
- `_LOOKUP_TASK_BLOCK`: блок "## Lookup Task:" с пошаговой процедурой

`errors/default.md` содержит **117 fragment-IDs** (см. meta-header) — это generic-default error-fragments со структурой `task_id/task_type/outcome/STEP FACTS/`. Большинство из них с outcome пустым:
```
$ grep "outcome:" errors/default.md | sort | uniq -c
  40 outcome: 
   2 outcome: OUTCOME_OK
   1 outcome: OUTCOME_NONE_UNSUPPORTED
```
40 фрагментов с пустым outcome означают, что postrun не получил финальный outcome — это либо crashed-задачи, либо ранние ингесты до Block A. Они должны быть удалены.

**Это плановый дефект** — план опирался на assumption что Block B покрывает все error-страницы, но не уточнил какие именно патерны нужно искать вне lookup. P0 цель ("errors/default.md ≤ 200 lines") не достигнута.

---

## 4. Что осталось не проверено

5-run verification из V1 не выполнен. Без полного прогона не известно:
- Меняется ли avg score (target ≥ 55% vs v4 51%)
- Снизилось ли «no answer provided» (target ≤ 20% vs v4 33%)
- Замедлился ли graph growth/run (target ≤ +80 vs v4 +160)
- Решён ли t42 (target ≥ 2/5 vs v4 0/5)

Эти проверки откладываются до устранения двух concerns выше.

---

## 5. Рекомендации к следующей итерации

### Шаг 1 (обязательно перед re-run) — отключить MODEL_CONTRACT
```bash
# В .env закомментировать строку MODEL_CONTRACT=minimax-m2.7:cloud
```
Block F остаётся в коде как opt-in feature: при пустом MODEL_CONTRACT CC-tier возвращается к hard-skip (FIX-394 поведение). Это даст чистый baseline для v5 без negotiate-overhead.

### Шаг 2 (обязательно) — расширить sanitize_wiki.py
Добавить regex / handler для drop'а fragments из `errors/default.md`:
- Удалить блоки с `outcome: ` пустым (40 шт.) — это ингесты без финального outcome из ранних версий
- Опционально: drop по возрасту (`task_id` метка времени старее N дней)

### Шаг 3 (опционально) — пересмотреть Block F
Если MODEL_CONTRACT остаётся critical для CC-tier (есть таски где он принципиально нужен) — найти модель которая лучше сходится в negotiate. Текущий minimax-m2.7 не сходится в 47% случаев, что хуже чем skip.

### Шаг 4 — чистый 5-run
После шагов 1-2 запустить полный 5-run и сравнить с v4 baseline по таблице из плана §V1.5.

---

## 6. Status сводка плана

| Block | Code | Tested | V1 verified | Notes |
|---|---|---|---|---|
| A — anti-poisoning | ✅ | ✅ | partial (run прерван) | работает: 0 graph growth в 60 мин |
| B — sanitation | ✅ | ✅ | ❌ | **gap: errors/default.md untouched** |
| C — soft budget | ✅ | ✅ | ✅ | warnings корректно фиксируются |
| D — confidence decay | ✅ | n/a (env-only) | ✅ | graph file shrunk -3.7% |
| E — mutation_scope gate | ✅ | ✅ | ❓ | гейт активен, но за 3 finalized задач реальных triggers не видно |
| F — negotiate on CC | ✅ | ✅ | ❌ | **ломает throughput с текущей MODEL_CONTRACT** |
| G — stemmed dedup | ✅ | ✅ | n/a | unit-tests OK; on-vault эффект не виден из-за прерванного run |

P2-блоки (step-budget split, tracking-based feedback, contract block visibility) не реализованы и не запланированы для v5 — отложены.

---

## 7. Артефакты

- `logs/v5/run_1.log` — partial smoke run (21 MB)
- `data/wiki/graph.json.pre-v5` — snapshot перед smoke run (578 KB, 1122 nodes)
- `data/wiki/pages.pre-v5/` — snapshot страниц перед smoke run
- `data/wiki/graph.json` — состояние после aborted run (557 KB, 1122 nodes)
- 13 коммитов в `quality-fixes` от `ea3f26c` до `d3913c6`

---

## 8. Решение по продолжению

Per user response (2026-05-05): **отчёт сохранён для проработки позже**. Re-run не запускается до исправления двух concerns. Worktree остаётся как есть; .env пока не правится.
