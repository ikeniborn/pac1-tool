---
wiki_sources:
  - docs/superpowers/specs/2026-05-04-knowledge-accumulation-redesign.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, wiki, wiki-graph, knowledge-accumulation, contract, system-prompt]
---

# Knowledge Accumulation Redesign

**Дата:** 2026-05-04 | **Контекст:** 5 прогонов minimax 12%. Граф вырос 78→202 узлов, но score не улучшился.

## Диагноз: корневые причины нулевого эффекта

| Проблема | Root cause |
|---|---|
| Граф накапливает правила, противоречащие системному промпту | `"use system clock"` vs промпт `"use vault dates"` |
| Temporal-узлы попадают в lookup-задачи | tag_score — бонус, не фильтр |
| Contract с пустым mutation_scope | evaluator-only consensus берёт `planned_mutations=[]` |
| Builder/evaluator deadlock | Builder `[SKIP]`, evaluator требует grounding_refs |
| DENIED_SECURITY на contract block | Нет принудительного завершения |

**Фундаментальный конфликт:** системный промпт → конкурирующий авторитет по тем же вопросам что граф. Накопление знаний бессмысленно.

## Блок A — Очистка системного промпта

**Принцип:** системный промпт = форма поведения (инструменты, форматы, security gates). Граф/wiki = содержание знаний (стратегии, паттерны).

**Удаляется:** `## Temporal and date tasks`, `_TASK_BLOCKS` для temporal/crm/lookup/capture (конкретные стратегии).

**Остаётся:** JSON-синтаксис, outcome-коды, security gates, discovery-first принцип.

## Блок B — Граф: строгая изоляция по task_type (FIX-433)

```python
# До: tag_score = 2.0 if (task_type in tags or "all_types" in tags) else 0.0
# После: hard filter — continue если нет совпадения тега
if task_type not in tags and "all_types" not in tags and "general" not in tags:
    continue
```

## Блок C — Contract gate: только full consensus

**C1:** Единственные выходы из negotiation: (1) Full consensus, (2) max rounds → default contract. Убрать ветку `evaluator_accepts` без `full_consensus`.

**C2:** `planned_mutations` обязателен для `MUTATION_REQUIRED_TYPES = {"crm", "capture", "inbox"}`.

**C3:** Поле `evidence_standard: "vault_required" | "calculation_only"` в `ExecutorProposal` и `Contract`.

## Блок D — Принудительное завершение при contract block

```python
st.consecutive_contract_blocks += 1
if st.consecutive_contract_blocks >= 2:
    return _force_none_clarification(st, "contract-gate consecutive blocks")
```

## Блок E — DSPy postrun optimize

1. Установить `POSTRUN_OPTIMIZE=1` в `.env`
2. Добавить `_count_dspy_examples()` + порог `POSTRUN_OPTIMIZE_MIN_EXAMPLES=10`
3. Если примеров мало → `log.info()` + `return` (не abort)
