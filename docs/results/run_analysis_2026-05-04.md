# Анализ 5 прогонов: t40, t41, t42, t43, t13 — 2026-05-04

Модель: `minimax-m2.7:cloud` (openrouter). Все DSPy programs: `[missing]`.

## Сводная таблица результатов

| Прогон | t40 (lookup) | t41 (temporal) | t42 (temporal) | t43 (distill) | t13 (crm) | ИТОГО |
|--------|-------------|----------------|----------------|---------------|-----------|-------|
| 1 | 0.00 — неверный порядок | 0.00 — неверная дата | 0.00 — CLARIFICATION | **1.00** ✓ | 0.00 — UNSUPPORTED | 20% |
| 2 | 0.00 — неверный порядок | 0.00 — неверная дата | 0.00 — CLARIFICATION | **1.00** ✓ | 0.00 — UNSUPPORTED | 20% |
| 3 | **1.00** ✓ | 0.00 — неверная дата | 0.00 — CLARIFICATION | 0.00 — vault swap | 0.00 — no answer | 20% |
| 4 | 0.00 — missing ref | 0.00 — неверная дата | 0.00 — CLARIFICATION | **1.00** ✓ | 0.00 — CLARIFICATION | 20% |
| 5 | 0.00 — неверный список | 0.00 — неверная дата | 0.00 — CLARIFICATION | 0.00 — vault swap | 0.00 — CLARIFICATION | 0% |

**Средний балл: 16%** (4 из 25 задач верно)

## Рост графа знаний

| После прогона | Узлы | Рёбра |
|--------------|------|-------|
| 0 (до) | 0 | 0 |
| 1 | 17 | 24 |
| 2 | 30 | 48 |
| 3 | 47 | 77 |
| 4+5 | 78 | — |

Итог: 24 insights, 26 rules, 28 antipatterns. Wiki-lint за каждый прогон обрабатывала 2 категории (`default`, `errors/default`) вместо 19 — только типы, которые появлялись в данном прогоне.

## Проблемы по задачам

### t41 — temporal (0/5, 0%)
**Корень**: FIX-357 gap formula возвращает неправильный ESTIMATED_TODAY для данного vault.  
- VAULT_DATE даётся, агент добавляет +5 дней → получает неверную базу.
- Ожидаемые даты рандомизируются (19-03, 08-03, 04-01, 25-03, 26-03) — vault перегенерируется каждый раз.
- Накопленные знания не исправляют формулу (это код, не промпт).

### t42 — distill lookup (0/5, 0%)
**Корень**: агент стабильно возвращает `OUTCOME_NONE_CLARIFICATION` вместо выполнения.  
- Задача "Find the article I captured 49 days ago" требует правильного расчёта даты + поиска по `/01_capture/`.
- Из-за той же ошибки temporal reasoning агент не находит файл и сдаётся.

### t40 — CRM lookup (1/5, 20%)
**Корень 1**: evaluator rejection loop для `grounding_refs` — evaluator требует "required_evidence" в специфическом формате, агент не понимает и застревает.  
**Корень 2**: в прогоне 5 агент не включил `acct_007.json` (CanalPort Shipping) в ответ — пропустил один аккаунт при сканировании всех 10 файлов подряд.  
- В прогоне 3 повезло: другой порядок аккаунтов у менеджера — агент справился.

### t43 — distill/lookup (3/5, 60%)
**Ситуация**: benchmark рандомизирует vault между CRM и distill:
- CRM vault → t43 = lookup → агент находит (1.00).
- Distill vault → t43 = temporal distill → ожидается CLARIFICATION (vault too sparse) → агент возвращает OK (0.00).
- Агент не умеет детектировать, когда vault слишком разрежен для ответа.

### t13 — CRM reschedule (0/5, 0%)
**Корень**: задача "Nordlicht Health asked to reconnect in two weeks. Reschedule the follow-up accordingly." требует записи в vault (update reminder + account).  
- Прогоны 1–2: `OUTCOME_NONE_UNSUPPORTED` — агент ошибочно классифицирует как "calendar/external system".
- Прогоны 4–5: `OUTCOME_NONE_CLARIFICATION` — реагирует иначе, но всё ещё не выполняет.
- В прогоне 3: `no answer provided` — таймаут или молчание.

## Системные проблемы

### 1. Pydantic ошибка step_facts (блокирует DSPy)
```
step_facts.0: Input should be a valid dictionary
  input_value=_StepFact(kind='read', ...), input_type=_StepFact
```
`_StepFact` объекты не сериализуются в `dict` при создании `ExecutionResult`. Возникает каждый прогон для каждой задачи. Следствие: DSPy примеры не накапливаются корректно.

### 2. postrun optimize failed (exit 1)
`[postrun] optimize failed (exit 1)` — каждый прогон. DSPy optimzer не может запуститься после прогона. Причина неизвестна (нет traceback в логе). Следствие: eval/builder programs остаются `[missing]` → агент работает без оптимизированных промптов.

### 3. Метрики токенов все нули
Колонки Шаги/Запр/Вход(tok)/Выход(tok) = 0 для всех задач. Minimax-m2.7 не возвращает метрики в ожидаемом формате. Анализ эффективности по токенам невозможен.

### 4. OUTCOME_FAIL антипаттерн засоряет граф
Узел `a_b30500141e` — `"text": "OUTCOME_FAIL"`, conf=1.0, uses=42. Это агрегированный счётчик неудач, а не содержательный паттерн. Занимает топ по uses, не даёт полезного сигнала.

### 5. Evaluator rejection loop
Evaluator отвергает `report_completion` 2 раза из-за `required_evidence` в `grounding_refs`. Агент не понимает формат и застревает (stall hints → принудительное завершение). Контракт создаётся с расплывчатыми `required_evidence` вместо точных путей.

## Влияние накопления на результаты

| Компонент | Статус | Влияние на прогонах 1-5 |
|-----------|--------|------------------------|
| Wiki pages | Растут (errors/default.md: nascent → developing → mature) | Инжектируются в evaluator, но оцениваемые задачи не выигрывают от этого |
| Graph nodes | 0 → 78 узлов | Инжектируются в system prompt (KNOWLEDGE GRAPH секция видна в логах прогона 4), но не устраняют системные баги |
| DSPy programs | [missing] все 5 прогонов | Нет вклада — оптимизация падает каждый раз |
| Error fragments | Накапливаются в `wiki/fragments/errors/` | Способствуют росту графа антипаттернов, но не меняют поведение |

**Вывод**: накопление вики и графа не улучшило результаты за 5 прогонов.  
Причина: системные блокеры (сломанная сериализация step_facts, падение postrun optimize) мешают DSPy-петле обратной связи. Граф растёт, но без скомпилированных программ оптимизированные знания не попадают в финальный промпт агента в нужном виде.

## Рекомендации

1. **Исправить step_facts сериализацию** — заменить `_StepFact` на `dict` или добавить `.model_dump()` при создании `ExecutionResult`. Приоритет: высокий (блокирует DSPy).
2. **Исправить postrun optimize** — включить полный traceback для `[postrun] optimize failed`, найти причину exit 1.
3. **Исправить t13** — задача reschedule неверно классифицируется как external/unsupported. Проверить `security.py` write-scope gates и классификатор.
4. **Исправить evaluator grounding_refs contract** — required_evidence должны быть конкретными путями, а не текстовыми описаниями. Или evaluator должен принимать текстовые аннотации в grounding_refs.
5. **Очистить граф от "OUTCOME_FAIL"** — этот узел не несёт знаний и не должен доминировать в retrieval.
6. **Temporal gap**: для `t41`/`t42` — gap +5 не универсален. Нужен более надёжный механизм определения базовой даты или проверка нескольких источников в vault.
