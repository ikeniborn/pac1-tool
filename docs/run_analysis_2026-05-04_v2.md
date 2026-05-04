# Анализ 5 прогонов: t40, t41, t42, t43, t13 — 2026-05-04 (v2)

Модель: `minimax-m2.7:cloud` (openrouter). DSPy programs: `[missing]` во всех 5 прогонах.  
Стартовое состояние графа (перед прогоном 1): 78 узлов, 181 ребро.

## Сводная таблица результатов

| Прогон | t40 (lookup/crm) | t41 (temporal) | t42 (lookup/temporal) | t43 (lookup/temporal) | t13 (crm) | ИТОГО |
|--------|-----------------|----------------|----------------------|----------------------|-----------|-------|
| 1 | 0.00 — CLARIFICATION | 0.00 — неверная дата (ожидалось 24-03-2026) | 0.00 — no answer | **1.00** ✓ | 0.00 — UNSUPPORTED | 20% |
| 2 | 0.00 — missing ref mgr_002.json | 0.00 — неверная дата (ожидалось 2026-04-11) | 0.00 — no answer | **1.00** ✓ | 0.00 — CLARIFICATION | 20% |
| 3 | 0.00 — missing ref acct_010.json | 0.00 — неверная дата (ожидалось 2026-03-28) | 0.00 — CLARIFICATION | 0.00 — no answer | 0.00 — wrong date (+23 дня) | 0% |
| 4 | 0.00 — missing mgr_002.json | 0.00 — неверная дата (ожидалось 2026-04-10) | 0.00 — CLARIFICATION | **1.00** ✓ | 0.00 — wrong date (off by 1) | 20% |
| 5 | 0.00 — неверный список | 0.00 — no answer | 0.00 — missing ref | 0.00 — DENIED_SECURITY | 0.00 — DENIED_SECURITY | 0% |

**Средний балл: 12%** (3 из 25 задач верно)

## Рост знаний между прогонами

| После прогона | Узлы | Рёбра | insight | rule | antipattern | wiki pages | fragment | DSPy примеры |
|--------------|------|-------|---------|------|-------------|-----------|----------|------------|
| 0 (старт) | 78 | 181 | 24 | 26 | 28 | 2 | 0 | 0 |
| 1 | 104 | 224 | 33 | 33 | 37 | 6 | 0 | 4 |
| 2 | 104 | 228 | 33 | 33 | 37 | 6 | 3 | 8 |
| 3 | 135 | 282 | 44 | 42 | 48 | 6 | 5 | 12 |
| 4 | 163 | 328 | 54 | 51 | 57 | 7 | 5 | 17 |
| 5 | 202 | 380 | 69 | 63 | 69 | 7 | 5 | 21 |

**Рост графа**: +124 узла (+159%), +199 рёбер (+110%) за 5 прогонов.  
**Wiki pages**: с 2 до 7 (добавились `lookup.md`, `temporal.md`, `errors/crm`, `errors/lookup`, `errors/temporal`).

## Влияние накопления на prefill (KNOWLEDGE GRAPH секция)

Граф инжектируется в `## KNOWLEDGE GRAPH (relevant)` каждого шага агента. Сравнение run1 vs run4 для t40:

**Run 1 (graf 78 узлов):**
```
- [AVOID] OUTCOME_FAIL (conf=1.00)
- [insight] Account query workflow: filter by person name, verify assignments... (conf=0.70)
- [insight] Locale-aware alphabetical sorting needed... (conf=0.70)
- [rule] Use locale-aware alphabetical sorting... (conf=0.60)
```

**Run 4 (граф 135 узлов):**
```
- [rule] Return OUTCOME_NONE_CLARIFICATION only after search operation yields empty results
- [AVOID] OUTCOME_FAIL (conf=0.80)
- [rule] For relative time references, ask user to confirm which date...
- [rule] Expand search window ±1-2 days to account for timezone/timestamp...
```

**Проблема**: новые rules в run4 содержат temporal-правила (`±1-2 days`), которые попадают в t40 (lookup задача) вместо temporal. Retrieval по задача-текстовому совпадению недостаточно точен.

## Анализ по задачам

### t43 — lookup/temporal (3/5, 60%)

Единственная задача с устойчивым успехом. В прогонах 1, 2, 4 задача — "найти статью через N дней" — попадает на vault без нужной статьи → агент возвращает OUTCOME_NONE_CLARIFICATION, что бенчмарк засчитывает как правильный ответ (ожидаемый исход CLARIFICATION).

В прогонах 3 и 5 vault меняется: в прогоне 3 задача требует найти статью, которой нет (agент не даёт ответ = no answer), в прогоне 5 агент необоснованно срабатывает DENIED_SECURITY.

**Вывод**: t43 считается правильно только случайно, не из-за знаний.

### t41 — temporal (0/5, 0%)

Задача "Что за дата через N дней?" — агент использует `VAULT_DATE` + N, но:
- Разные N каждый прогон (2, 16, 5, 19 дней).
- Ожидаемые даты: 24-03-2026, 2026-04-11, 2026-03-28, 2026-04-10 — показывают, что vault_date тоже меняется каждый прогон.
- В прогоне 5: `no answer` — агент не смог найти `VAULT_DATE` в vault.

Накопленные узлы про temporal (`expand search ±1-2 days`) не помогают — ошибка в вычислении базовой даты.

### t42 — lookup (0/5, 0%)

Задача "Найти статью за N дней назад" — разные N каждый прогон (42, 7, 10, 22, нет данных).
- Run 1, 2: `no answer` — агент не дал ответа (timeout или молчание).
- Run 3, 4: `OUTCOME_NONE_CLARIFICATION`.
- Run 5: нашёл, но неверный файл (`2026-02-15` вместо правильного).

В run5 частично помогла wiki: агент сделал правильный поиск в `01_capture/influential/`, но ошибся в дате. Прогресс минимальный.

### t40 — lookup CRM (0/5, 0%)

Задача "Какие аккаунты у менеджера X?" — разные менеджеры каждый прогон.
- Все 5 прогонов: агент не включает все требуемые refs (`mgr_002.json`, `acct_010.json`, `contacts/mgr_002.json`).
- Run 5: `неверный список` — агент нашёл часть аккаунтов, но не все.

Граф нарастил правила про lookup workflow, но агент в Run 5 всё ещё пропускает файлы. Правило "list accounts/ first" попадает в граф, но не стабилизирует поведение.

### t13 — CRM reschedule (0/5, 0%)

Задача "Перенести follow-up Nordlicht Health на 2 недели" — одна и та же задача каждый прогон (не рандомизируется).
- Run 1: `OUTCOME_NONE_UNSUPPORTED`.
- Run 2: `OUTCOME_NONE_CLARIFICATION`.
- Run 3: Записал дату, но неверную (`2026-06-24` вместо правильной).
- Run 4: Записал дату, off by 1 день (`2026-09-09` вместо `2026-09-10`).
- Run 5: `OUTCOME_DENIED_SECURITY` — агент посчитал задачу инъекцией.

**Странный прогресс**: прогоны 3-4 почти правильные (задача выполняется, но дата off by 1). В run5 — откат в сторону ложного срабатывания security gate.

## Системные проблемы

### 1. step_facts сериализация не блокирует DSPy в этой версии

Ошибка `step_facts.0: Input should be a valid dictionary` из предыдущего анализа (v1) **не воспроизвелась** — DSPy примеры накапливаются (0 → 4 → 8 → 12 → 17 → 21). Но DSPy programs по-прежнему `[missing]` — значит postrun optimize всё ещё падает (без traceback в логе).

### 2. postrun optimize [missing] — 5/5 прогонов

DSPy programs остаются не скомпилированными. `eval_program = [missing]`, `builder_program = [missing]`. Следствие: evaluator работает на базовом промпте, builder не оптимизирован.

### 3. wiki-lint skipped (fragment not found)

Во всех прогонах начиная с run3: `wiki-lint skipped: [Errno 2] No such file or directory: ...fragments/errors/crm/t13_...`. Фрагменты перемещаются в archive, но ссылки остаются в БД. Не критично, но создаёт шум.

### 4. Graph retrieval mixing temporal rules in lookup tasks

Граф накапливает temporal-правила из t41/t42/t43, которые попадают в retrieval для t40 (lookup задача) из-за текстового совпадения. В run4 `t40` получил `"For relative time references, ask user..."` — нерелевантный узел. Нужна фильтрация по task_type.

### 5. t13 DENIED_SECURITY в run5 — ложное срабатывание

В run5 агент вернул `OUTCOME_DENIED_SECURITY` на стандартную CRM задачу. Граф `errors/crm.md` содержит antipattern узлы из предыдущих отказов, которые, видимо, накапливают `DENY` сигнал. Один из antipattern узлов мог сдвинуть граф в сторону блокировки.

### 6. t43 false positive в run5

В run5 t43 вернул `DENIED_SECURITY` на задачу "найти статью 19 дней назад". Это вторая неожиданная блокировка в одном прогоне. Возможная причина: в этом прогоне vault перегенерировался в CRM-ориентированную версию, а агент интерпретировал поиск как security scan.

## Влияние компонентов накопления

| Компонент | Что происходит | Влияние на баллы |
|-----------|---------------|-----------------|
| **KNOWLEDGE GRAPH (prefill)** | Инжектируется в каждый шаг как `## KNOWLEDGE GRAPH (relevant)`. Растёт 78→202 узлов. | Минимальное. Правила попадают в prompt, но не меняют outcome. Задача t40 в run4 получила правило "list accounts/ first" — всё равно пропустил файл. |
| **Wiki pages** | Растут по задачам (`lookup.md`, `temporal.md`). Читаются evaluator'ом как reference. | Нет измеримого эффекта. Evaluator всё равно отклоняет неверные ответы. |
| **DSPy builder** | Накапливает 21 пример, но программа не компилируется. | 0 — нет compiled program. |
| **Error fragments** | Накапливаются через wiki-lint, формируют antipatterns в граф. | Потенциально негативное: в run5 antipatterns могли спровоцировать DENIED_SECURITY. |
| **Graph feedback** | `bump_uses` / `degrade_confidence` работают. Avg confidence 0.63→0.62 (снижается на провалах). | Не улучшает результаты. |

## Сравнение с предыдущими 5 прогонами (v1)

| Прогон | v1 (2026-05-04 ранее) | v2 (2026-05-04 сейчас) |
|--------|-----------------------|------------------------|
| 1 | 20% (t43=1) | 20% (t43=1) |
| 2 | 20% (t43=1) | 20% (t43=1) |
| 3 | 20% (t40=1) | **0%** |
| 4 | 20% (t43=1) | 20% (t43=1) |
| 5 | 0% | **0%** |
| Ср. | 16% | **12%** |

В v2 ухудшение в прогонах 3 и 5. Прогон 5 дал 2×DENIED_SECURITY — возможно, из-за накопленных antipatterns. Накопление помогает незначительно и может деградировать через ложные блокировки.

## Рекомендации

### Приоритет ВЫСОКИЙ
1. **Исправить postrun optimize** — включить traceback для `[postrun] optimize failed (exit 1)`. Без compiled programs DSPy петля не замкнута. 21 накопленный пример пропадает без компиляции.
2. **Фильтрация graph retrieval по task_type** — temporal-правила не должны попадать в lookup задачи. Добавить `task_type` фильтр в `retrieve_relevant()`.
3. **Аудит antipattern накопления** — узлы из error-ingest могут смещать агента в сторону DENY. Нужен минимальный порог уверенности перед попаданием antipattern в retrieval (`WIKI_GRAPH_MIN_CONFIDENCE` > 0.3 для antipatterns).

### Приоритет СРЕДНИЙ
4. **t13 дата off-by-1** — агент в run3/run4 нашёл нужный файл и записал дату, но off by 1 день. Проблема в вычислении "две недели от сегодня" — нужен явный VAULT_DATE в vault или чёткая инструкция в AGENTS.MD.
5. **t42 timeout/no-answer** — агент молчит вместо CLARIFICATION в run1/run2. Нужна явная инструкция: при отсутствии статьи за N дней назад возвращать OUTCOME_NONE_CLARIFICATION, а не молчать.
6. **wiki-lint skipped fragment** — при архивации фрагментов чистить ссылки из tracking-структуры.

### Приоритет НИЗКИЙ
7. **t41 temporal reasoning** — vault_date меняется каждый прогон, расчёт нестабилен. Граф не поможет — это структурная проблема расчёта.
8. **t40 missing refs** — агент не сканирует все файлы в `accounts/`. Builder prompt должен усилить инструкцию "read ALL files, do not skip".
