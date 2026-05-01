# T43 Architecture Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Запустить PAC1-задачу t43 и оценить эффективность мультиагентной архитектуры с контрактами, субагентами, вики и графом знаний.

**Architecture:** Операционный аудит без изменения кода: фиксация baseline → запуск с диагностикой → анализ логов по 4 измерениям → выводы.

**Tech Stack:** Python/uv, make, bash, data/wiki/graph.json, logs/<timestamp>/

---

## Task 0: Baseline — зафиксировать состояние до запуска

**Files:**
- Read: `data/wiki/graph.json`
- Read: `data/wiki/pages/*.md`

- [ ] **Step 1: Зафиксировать статистику графа**

```bash
python3 -c "
import json
g = json.load(open('data/wiki/graph.json'))
nodes = g['nodes']
types = {}
for n in nodes.values():
    t = n.get('type','?')
    types[t] = types.get(t,0) + 1
print('BASELINE GRAPH:')
print(f'  Всего узлов: {len(nodes)}')
print(f'  Всего рёбер: {len(g[\"edges\"])}')
print(f'  По типам: {types}')
avg_conf = sum(n.get(\"confidence\",0) for n in nodes.values()) / max(len(nodes),1)
print(f'  Средний confidence: {avg_conf:.3f}')
"
```

Ожидаемый вывод (текущий baseline): 675 узлов, 1063 рёбра.

- [ ] **Step 2: Зафиксировать состояние wiki-страниц**

```bash
for f in data/wiki/pages/*.md; do
  echo "--- $f ---"
  grep -m4 "^category:\|^quality:\|^fragment_count:\|^last_synthesized:" "$f" 2>/dev/null
done
```

Записать: какие страницы nascent/developing/mature. Это важно для оценки того, сколько wiki-контента агент получит в промпт.

- [ ] **Step 3: Зафиксировать тип задачи t43 (если известен из прошлых логов)**

```bash
ls logs/ | sort | tail -5
# Если есть логи — посмотреть последний для понимания типа t43:
# grep "task_type\|classify" logs/<последний>/*.log 2>/dev/null | head -5
```

Если тип неизвестен — ничего страшного, узнаем из вывода запуска.

---

## Task 1: Запуск t43 с полной диагностикой

**Files:**
- Read: `logs/<новый timestamp>/` (создаётся автоматически)

- [ ] **Step 1: Проверить здоровье графа перед запуском**

```bash
uv run python scripts/check_graph_health.py
```

Ожидаем: `OK` или список предупреждений. Если FAIL — запустить с `GRAPH_HEALTH=0`.

- [ ] **Step 2: Запустить задачу t43 с DEBUG-логированием**

```bash
LOG_LEVEL=DEBUG make task TASKS=t43 2>&1 | tee /tmp/t43_audit.log
```

Во время выполнения наблюдать за:
- `[contract]` строками → видна фаза переговоров
- `[classify]` → тип задачи и confidence
- `[wiki]` / `[graph]` → инжекция контекста
- `[stall]` → детекции зависания
- `[evaluator]` / `[verifier]` → оценка перед сабмитом
- `score:` в финале → итоговый результат

- [ ] **Step 3: Зафиксировать финальный score и номер шагов**

```bash
grep -E "score|steps|task_type|model_used|builder_used|stall" /tmp/t43_audit.log | tail -30
```

Записать: score (0.0/0.5/1.0), шагов, тип задачи, модель, был ли билдер, были ли stall-ы.

- [ ] **Step 4: Найти лог-директорию этого прогона**

```bash
ls -lt logs/ | head -3
# Записать путь: logs/<timestamp>/
```

---

## Task 2: Анализ измерения 1 — Эффективность контрактов

**Files:**
- Read: `/tmp/t43_audit.log`

- [ ] **Step 1: Извлечь все события контрактной фазы**

```bash
grep -n "\[contract\]\|CONTRACT\|negotiat\|proposal\|objection\|consensus\|agreed\|fallback" \
  /tmp/t43_audit.log | head -50
```

- [ ] **Step 2: Оценить контрактную фазу по критериям**

Проверить и записать ответы на:
1. Запустилась ли фаза контракта (`CONTRACT_ENABLED=1` в env)?
2. Сколько раундов переговоров (ищем `round 1`, `round 2`, `round 3`)?
3. Были ли `blocking_objections`? Какие именно?
4. Достигнут ли консенсус (`agreed=true`) или сработал fallback на `default_contracts/`?
5. Изменил ли контракт содержимое addendum (есть ли `plan_steps` в выводе)?

```bash
grep -A5 "blocking_objection\|agreed.*true\|fallback.*contract\|plan_steps" \
  /tmp/t43_audit.log | head -40
```

- [ ] **Step 3: Вывод по контрактам**

Сформулировать: контракт работает как надо / есть проблемы (и какие именно).

---

## Task 3: Анализ измерения 2 — Координация субагентов

**Files:**
- Read: `/tmp/t43_audit.log`

- [ ] **Step 1: Проследить pipeline субагентов**

```bash
grep -n "ClassifierAgent\|PlannerAgent\|WikiGraphAgent\|VerifierAgent\|SecurityAgent\|StallAgent\|ExecutorAgent\|CompactionAgent\|StepGuardAgent" \
  /tmp/t43_audit.log | head -30
```

- [ ] **Step 2: Проверить передачу контрактов между агентами**

```bash
# Классификация
grep -E "task_type|confidence|classify" /tmp/t43_audit.log | head -10

# Передача wiki-контекста в PlannerAgent
grep -E "wiki_context|injected_node|patterns_text|graph_section" /tmp/t43_audit.log | head -10

# Verifier перед сабмитом
grep -E "evaluator|verif|before.*report|evaluat.*complet" /tmp/t43_audit.log | head -10
```

- [ ] **Step 3: Проверить security и stall агентов**

```bash
grep -E "\[stall\]|\[security\]|write.*scope|injection|escalat" /tmp/t43_audit.log | head -20
```

- [ ] **Step 4: Вывод по субагентам**

Сформулировать: все ли субагенты отработали, не было ли провалов в передаче данных через контракты.

---

## Task 4: Анализ измерения 3 — Качество Wiki и Графа

**Files:**
- Read: `/tmp/t43_audit.log`
- Read: `data/wiki/graph.json` (после прогона)
- Read: `data/wiki/pages/<task_type>.md` (после прогона)

- [ ] **Step 1: Проверить инжекцию графа в промпт**

```bash
grep -E "graph|KNOWLEDGE GRAPH|injected.*node|top.k|graph_section|retrieve_relevant" \
  /tmp/t43_audit.log | head -20
```

Зафиксировать: сколько узлов инжектировано (WIKI_GRAPH_TOP_K=5 по умолчанию), релевантны ли они типу задачи.

- [ ] **Step 2: Проверить использование wiki-страницы**

```bash
grep -E "wiki.*page|patterns_text|EVALUATOR_WIKI|reference_pattern|wiki_enabled" \
  /tmp/t43_audit.log | head -20
```

Сравнить: какого качества была wiki-страница для типа t43 (из baseline Task 0) и сколько символов было передано (EVALUATOR_WIKI_MAX_CHARS_DEVELOPING=2000 для developing).

- [ ] **Step 3: Проверить пост-прогонное обновление графа**

```bash
python3 -c "
import json
g = json.load(open('data/wiki/graph.json'))
nodes = g['nodes']
types = {}
for n in nodes.values():
    t = n.get('type','?')
    types[t] = types.get(t,0) + 1
print('POST-RUN GRAPH:')
print(f'  Всего узлов: {len(nodes)}')
print(f'  Всего рёбер: {len(g[\"edges\"])}')
print(f'  По типам: {types}')
avg_conf = sum(n.get(\"confidence\",0) for n in nodes.values()) / max(len(nodes),1)
print(f'  Средний confidence: {avg_conf:.3f}')
"
```

Сравнить с baseline (Task 0, Step 1). Изменился ли граф?

- [ ] **Step 4: Проверить новый wiki-фрагмент**

```bash
# Определить тип задачи из лога (Task 1, Step 3), затем:
TASK_TYPE=<тип из лога>
grep "fragment_count\|last_synthesized" data/wiki/pages/${TASK_TYPE}.md
```

Сравнить fragment_count до (из baseline) и после.

- [ ] **Step 5: Вывод по wiki и графу**

Сформулировать: граф помогает агенту / wiki-страница достаточно насыщена / есть пробелы.

---

## Task 5: Анализ измерения 4 — Итоговое качество решения

**Files:**
- Read: `/tmp/t43_audit.log`

- [ ] **Step 1: Разобрать trajectory агента**

```bash
grep -E "STEP|tool.*call|write|read|delete|find|search|tree|list|move|report_completion" \
  /tmp/t43_audit.log | head -50
```

Считать: сколько шагов, какие инструменты использованы, был ли лишний exploration без writes.

- [ ] **Step 2: Проверить score и финальный статус**

```bash
grep -E "score|result|DONE|SUCCESS|FAIL|report_completion|trial" /tmp/t43_audit.log | tail -20
```

- [ ] **Step 3: Проверить токены и эффективность**

```bash
grep -E "in_tok|out_tok|total.*tok|builder.*tok|usage" /tmp/t43_audit.log | tail -10
```

- [ ] **Step 4: Вывод по итоговому качеству**

Оценить по шкале: score + количество шагов + наличие stall-ов.

| Метрика | Хорошо | Приемлемо | Плохо |
|---|---|---|---|
| Score | 1.0 | 0.5 | 0.0 |
| Шаги | <10 | 10-20 | >20 |
| Stall-детекции | 0 | 1 | 2+ |
| Write-scope нарушения | 0 | — | любое |

---

## Task 6: Итоговые выводы и рекомендации

- [ ] **Step 1: Свести все 4 измерения в одну оценку**

Написать краткое резюме по каждому:
- **Контракты:** [работает/есть проблема] — [деталь]
- **Субагенты:** [работает/есть проблема] — [деталь]
- **Wiki/Граф:** [работает/есть проблема] — [деталь]
- **Итог задачи:** score X.X, N шагов, [эффективно/нет]

- [ ] **Step 2: Сформулировать минимум 3 конкретные рекомендации**

Каждая рекомендация должна содержать:
- Что именно не так (с конкретной ссылкой на лог или компонент)
- Что сделать для улучшения (конкретное действие: дообучить, добавить фрагмент, изменить параметр)

- [ ] **Step 3: Проверить, что graph health всё ещё OK**

```bash
uv run python scripts/check_graph_health.py
```

- [ ] **Step 4: Сохранить выводы**

Записать итоговый анализ в `docs/superpowers/plans/2026-04-30-t43-architecture-audit.md` в раздел `## Результаты аудита` ниже этой линии.

---

## Результаты аудита

**Прогон:** 2026-04-30, `logs/20260430_230118_minimax-m2.7-cloud/`  
**Модель:** minimax-m2.7:cloud  
**Задача:** `lookup` — "which captured article is from 37 days ago?"  
**Итог:** Score 0.00 — expected OUTCOME_NONE_CLARIFICATION, got OUTCOME_OK

---

### Измерение 1: Эффективность контрактов

**Статус: ПРОБЛЕМА — контракт переопределяет правильные сигналы из графа и addendum**

- Фаза контракта запустилась: 1 раунд, нет blocking_objections
- Тип консенсуса — **"evaluator-only"**: executor.agreed=False, evaluator.agreed=True
- Контракт сгенерировал план "идти искать статью" (list → search → read)
- Одновременно в системном промпте уже было:
  - Граф: `[AVOID] Relative date queries fail (conf=0.57)` + `[AVOID] (conf=0.96)` (ссылка на Verified refusal)
  - Builder addendum: `[SKIP] Task triggers immediate rejection. No vault exploration needed.`
  - Wiki-страница: `## Verified refusal: t43` — явно OUTCOME_NONE_CLARIFICATION
- **Контракт имеет приоритет над всеми тремя сигналами** — агент последовал плану контракта, проигнорировав граф, addendum и wiki

### Измерение 2: Координация субагентов

**Статус: ПРОБЛЕМА — Evaluator bypassed для всех lookup-задач**

- ClassifierAgent: корректно определил тип `lookup`
- WikiGraphAgent: корректно инжектировал 5 релевантных узлов (включая AVOID-сигналы)
- PlannerAgent (builder): корректно определил `[SKIP] Task triggers immediate rejection`
- ContractPhase: неверно сгенерировал план-действие вместо плана-отказа
- VerifierAgent (evaluator): **полностью bypassed** — `agent/loop.py:2185`:
  ```python
  if task_type == TASK_LOOKUP:
      _eval_bypass = True  # "evaluator doesn't understand vault data model"
  ```
  Evaluator, который мог бы поймать неправильный OUTCOME, был отключён хардкодом
- SecurityAgent, StallAgent: не активировались (задача прошла без нарушений безопасности и без stall)

### Измерение 3: Качество Wiki и Графа

**Статус: Wiki и Граф РАБОТАЮТ правильно — их сигналы игнорируются архитектурой**

- Граф (baseline): 675 узлов, 1063 рёбра, средний confidence 0.648
- Граф корректно имел два AVOID-узла для t43 с высоким confidence (0.96 и 0.57)
- Граф (post-run): 806 узлов (+131), 1322 рёбра (+259) — wiki-lint + error-ingest добавили контент
- Wiki lookup-страница: quality=developing, 10 фрагментов — уже содержала `Verified refusal: t43`
- **Проблема**: граф здоровье ухудшилось с OK → WARN: 3 contaminated (+1), 2 duplicates (+2) — error-ingest добавил дублирующие/заражённые узлы
- Degrade: 5 узлов понизили confidence (score=0), 0 архивировано — механизм работает

### Измерение 4: Итоговое качество решения

**Статус: ПЛОХО по score, но ХОРОШО по эффективности шагов**

| Метрика | Значение | Оценка |
|---|---|---|
| Score | 0.00 | Плохо |
| Шаги | 2 (list + report) | Хорошо |
| Stall-детекции | 0 | Хорошо |
| Write-scope нарушения | 0 | Хорошо |
| Время | 109.4s | Приемлемо |
| Токены агента | 25,180 in / 1,167 out | Приемлемо |

Агент выполнил ровно то, что предписал контракт (list `/01_capture/influential` → report) — минимально и без лишних шагов. Ошибка не в эффективности, а в **неправильном типе outcome**: агент дал approximate match вместо отказа.

---

### Рекомендации

**1. Контракт должен читать wiki Verified Refusals перед генерацией плана**

Контрактная фаза (`agent/contract_phase.py`) не получает wiki-контент как входной сигнал. Она видит только task_text и graph_context. Нужно передавать в CONTRACT_PROMPT секцию `## Verified refusal:` из wiki-страницы соответствующего типа. Это позволит контракту генерировать "план-отказ" (`outcome: OUTCOME_NONE_CLARIFICATION, no exploration needed`) вместо "план-действия".

**2. Убрать паушальный bypass evaluator для lookup — заменить точечным**

`agent/loop.py:2185` отключает evaluator для ВСЕХ lookup-задач. Это мешает поймать неправильные OUTCOME. Нужно заменить на точечную логику: bypass только если `outcome == OUTCOME_OK AND grounding_refs содержит прочитанные файлы` (т.е. агент реально что-то нашёл и прочитал). Если outcome == OUTCOME_NONE_CLARIFICATION — evaluator не нужен. Если outcome == OUTCOME_OK без reads — подозрительно, evaluator должен проверить.

**3. Error-ingest порождает дубликаты — нужна деdup-проверка перед вставкой в граф**

После прогона граф здоровье ухудшилось: 2 duplicate-text node groups. `wiki_graph.py` при `error-ingest` добавляет antipattern-узлы без проверки на семантическое дублирование. Нужно добавить в `add_pattern_node` / `_error_ingest` проверку схожести текста нового узла с существующими (например, простой overlap > 0.8 → skip). Запустить `scripts/check_graph_health.py --purge` для очистки текущих дублей.

**Дополнительно (низкий приоритет):**  
Builder addendum правильно говорит `[SKIP]` — но этот сигнал не пробрасывается в контрактную фазу как constraint. Можно добавить: если addendum содержит `[SKIP]`, contract_phase сразу возвращает default contract с `agreed=True, plan_steps=["report: OUTCOME_NONE_CLARIFICATION"]`.

