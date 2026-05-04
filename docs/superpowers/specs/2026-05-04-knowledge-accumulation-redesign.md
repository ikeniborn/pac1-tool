# Knowledge Accumulation Redesign

**Date:** 2026-05-04  
**Context:** 5 прогонов minimax-m2.7 дали средний балл 12%. Граф вырос с 78 до 202 узлов, wiki с 2 до 7 страниц, DSPy примеры накопились до 21 — но счёт не улучшился. Анализ логов выявил системные конфликты, блокирующие применение знаний.

---

## Диагноз

### Корневые причины нулевого эффекта от накопления

| Проблема | Задача | Root cause |
|---|---|---|
| Граф накапливает правила, противоречащие системному промпту | t41 | `"use system clock"` vs промпт `"use vault dates"` |
| Temporal-узлы попадают в lookup-задачи | t40 | tag_score — бонус, не фильтр |
| Contract выполняется с пустым mutation_scope | t13 | Evaluator-only consensus берёт `planned_mutations=[]` из незавершённого proposal |
| Builder/evaluator deadlock | t41 | Builder: `[SKIP]`, evaluator: требует grounding_refs |
| Агент возвращает DENIED_SECURITY на contract block | t13 run5 | Нет принудительного завершения в коде |

### Фундаментальный конфликт

Системный промпт содержит конкретные доменные правила (temporal triangulation, CRM lookup strategies). Граф накапливает правила из реального опыта. Когда они расходятся — промпт побеждает, граф игнорируется. Накопление знаний бессмысленно пока промпт является конкурирующим авторитетом по тем же вопросам.

---

## Дизайн

### Блок A — Очистка системного промпта

**Принцип:** системный промпт описывает форму поведения (инструменты, форматы, security gates), граф и wiki описывают содержание знаний (стратегии, паттерны, антипаттерны).

**Удаляется из `agent/prompt.py` и `_TASK_BLOCKS`:**
- `## Temporal and date tasks` — формулы triangulation, VAULT_DATE bounds, implied_today
- `_TASK_BLOCKS` для `temporal`, `crm`, `lookup`, `capture` — конкретные стратегии выполнения
- Правила про конкретные папки и поля (где лежат CRM-файлы, форматы date-файлов)

**Остаётся:**
- Синтаксис и формат JSON-команд (NextStep, tool names)
- Outcome-коды и условия их применения
- Security gates (injection detection, write-scope enforcement)
- Общие принципы: discovery-first, hallucination gate, read before write

**Граф:** одноразовый сброс до `{"nodes": {}, "edges": []}` при деплое этих изменений. Далее накапливается нормально через прогоны.

---

### Блок B — Граф: строгая изоляция по task_type

**Файл:** `agent/wiki_graph.py`, функция `_score_candidates`

**Текущее поведение:** `tag_score = 2.0 if task_type in tags else 0.0` — узел без нужного тега всё равно попадает в top-K через text-token overlap.

**Новое поведение:** если `task_type not in node.tags` и тег не `"general"` — score обнуляется принудительно. Temporal-узлы не попадают в lookup-задачи физически.

```python
# До:
tag_score = 2.0 if (task_type in tags or "all_types" in tags) else 0.0

# После:
if task_type not in tags and "all_types" not in tags and "general" not in tags:
    continue  # hard filter, не бонус
tag_score = 2.0
```

---

### Блок C — Contract gate: только full consensus

**Файл:** `agent/contract_phase.py`, `agent/contract_models.py`

#### C1 — Убрать evaluator-only режим

Единственные выходы из negotiation:
1. **Full consensus** (`executor.agreed=True` + `evaluator.agreed=True`) → выполнение
2. **Max rounds exceeded** → default contract (fail-open)

Строки 330–360 `contract_phase.py`: убрать ветку `evaluator_accepts` без `full_consensus`. Если evaluator согласен, executor нет — продолжать раунды.

#### C2 — Обязательный `planned_mutations`

В `ExecutorProposal` поле `planned_mutations` становится обязательным для task_type с мутациями (`crm`, `capture`, `inbox`). Если executor не задекларировал мутации для такого типа — evaluator выдаёт blocking_objection. Раунд продолжается.

Определение типов с обязательными мутациями: `MUTATION_REQUIRED_TYPES = {"crm", "capture", "inbox"}` — константа в `contract_phase.py`.

#### C3 — Поле `evidence_standard`

Добавляется в `ExecutorProposal` и `Contract`:

```python
evidence_standard: str = "vault_required"  # "vault_required" | "calculation_only"
```

Evaluator при финальной оценке (`evaluate_completion`): если `contract.evidence_standard == "calculation_only"` — не требует grounding_refs из vault, принимает расчётный ответ без file evidence.

---

### Блок D — Принудительное завершение при contract block

**Файл:** `agent/loop.py`

Когда contract gate блокирует write-операцию, система уже отправляет сообщение агенту. Агент его игнорирует и продолжает пытаться писать или выбирает DENIED_SECURITY.

**Изменение:** счётчик consecutive contract blocks. После 2 блоков подряд loop принудительно форсирует завершение с `OUTCOME_NONE_CLARIFICATION`, не передавая управление агенту.

```python
# В loop.py при срабатывании contract gate:
st.consecutive_contract_blocks += 1
if st.consecutive_contract_blocks >= 2:
    # force complete, не ждём агента
    return _force_none_clarification(st, "contract-gate consecutive blocks")
```

---

## Что проверяем после изменений

1. **Чистый граф + очищенный промпт:** первые прогоны дадут базовый балл без доменных знаний. Ожидаемо низкий.
2. **После 3–5 прогонов:** граф должен накопить правильные стратегии из успешных trials. Балл должен расти.
3. **t13:** contract gate больше не блокирует write при правильном плане → ожидается score=1.0.
4. **t41:** без [SKIP] в промпте агент пойдёт в vault → правильная triangulation → правильная дата.
5. **t40:** temporal-узлы не попадают в lookup → чище retrieval.

---

## Ограничения и риски

- Первые прогоны после очистки промпта дадут регрессию — агент не знает доменных стратегий. Это ожидаемо и является частью теста.
- Граф накапливает через wiki-lint (LLM-синтез) и pattern-extractor (score=1.0). Если minimax не генерирует корректный JSON для graph_deltas — накопление будет медленным. Нужно мониторить `fence: missing` в логах.
- DSPy postrun optimize по-прежнему не работает (нет traceback). Это отдельная проблема, не входит в этот спек.
