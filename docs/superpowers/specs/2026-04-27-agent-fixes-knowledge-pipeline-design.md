# Agent Fixes & Knowledge Pipeline — Design Spec

**Date:** 2026-04-27  
**Run analyzed:** `logs/20260427_164400_claude-code-sonnet-4.6`  
**Baseline score:** 67.44% (29/43)  
**Approach:** Подход 3 — архитектурные фиксы там где нужны, pipeline-улучшения там где достаточно

---

## Контекст

Анализ прогона выявил 14 провалов с двумя корневыми категориями:
1. **Баги в коде** — gate deadlocks, парсинг CC-ответов, отсутствие recovery — wiki/DSPy не могут их устранить
2. **Пробелы в знаниях** — security semantics, grounding refs, vault date — накапливаются через wiki/graph/DSPy, но для этого нужно включить промоут в normal mode

---

## Изменения

### A1 — CC contract executor: исправить парсинг пустого результата

**Файл:** `agent/cc_client.py`

**Проблема:** Каждая задача тратит 1–3 CC-вызова в contract-executor. CC возвращает `stop_reason=end_turn` с пустым полем `result` (потому что вывод идёт в `tool_use` блоки, а не в `result`). Агент правильно фолбэкит, но это системный перерасход — видно на 100% задач.

**Решение:**  
В `cc_client.py` — если `result` пустой при `stop_reason=end_turn`:
- Проверить наличие непустых `tool_use` блоков в conversation
- Если есть — извлечь последний assistant-message текст как альтернативный result
- Если нет — текущее поведение (fail, fallback)

Либо: убрать contract-executor pre-step для CC tier полностью, если он системно не работает (CC уже имеет свой внутренний loop).

**Метрика успеха:** Исчезновение строк `[CC] empty result with stop_reason=end_turn — not retrying` в логах.

---

### A2 — Gate deadlocks: авто-расслабление и create-vs-update

**Файл:** `agent/security.py`

**Проблема A — [force-read-contact] deadlock (t11, 30 шагов без ответа):**  
Задача: "Write email to maya@example.com" — контакта нет в vault.  
Gate требует прочитать `/contacts/<id>.json` перед записью в `/outbox/`. Авто-расслабление срабатывает "после ≥2 разных поисков", но поиски по "maya" и "example.com" оба возвращают `README.MD:17` — gate считает что контакт "найден" и не расслабляется. Агент зациклился на 30 шагах.

**Решение:**  
Ввести явный счётчик `_contact_search_misses`: инкрементировать только когда search по `/contacts/` вернул **нулевые совпадения с contact-файлами** (т.е. совпадения только с README.MD не считаются). После 2 таких промахов — gate расслабляется с логом:
```
[force-read-contact] auto-relax: 2 contact searches found no contact file
```

**Проблема Б — [force-read-before-write] блокирует создание новых файлов (t13, timeout):**  
Gate блокирует любую запись без предварительного чтения. Но агент пытался создать новый reminder — читать нечего. Gate не различает update vs create.

**Решение:**  
Использовать set уже прочитанных путей в текущей задаче (`task_state.read_paths`). Если целевой path write-операции **не** присутствует в `read_paths` — gate добавляет в user-message смягчённую версию:
```
[force-read-before-write] If updating existing file — read it first.
If creating new file — proceed with write.
```
Агент сам определяет контекст (create vs update) и действует соответственно. Если файл был прочитан (`path in read_paths`) и агент пишет без чтения в текущей задаче — блокируем как прежде.

**Метрика успеха:** t11 завершается за ≤5 шагов. t13 не уходит в timeout.

---

### A3 — JSON parse errors: улучшить извлечение из CC-ответа

**Файл:** `agent/cc_client.py`

**Проблема:** `_strip_fences` удаляет markdown-фенсы, но CC иногда добавляет текст после закрывающей `}` (объяснение, trailing chars). Результат: `Invalid JSON: trailing characters at line 3 column 1`. Происходит на ~70% задач при report_completion, добавляя 1 лишний шаг.

**Решение:**  
После `_strip_fences` — добавить fallback-извлечение: найти первый `{` и последний `}` сбалансированный по скобкам (stack-based), вырезать этот substring и попробовать parse снова. Это надёжно изолирует JSON-объект даже при trailing text.

**Метрика успеха:** Исчезновение `JSON parse failed, trying extraction` в логах.

---

### A4 — Timeout recovery: graceful fallback на [FILE UNREADABLE]

**Файл:** `agent/loop.py`, `agent/prompt.py`

**Проблема:** `Telegram.txt` read вернул timeout → `[FILE UNREADABLE]` → агент галлюцинировал количество (сначала 5, потом 24) → `discovery-gate` заблокировал финализацию → OUTCOME_ERR_INTERNAL (t30).

**Решение:**

В `loop.py`: если PCM tool вернул `[FILE UNREADABLE]` или read error — инжектировать в следующий user-message:
```
[READ ERROR: /path/to/file] — file unreadable. Use search tool with same path as fallback.
Do NOT guess or hallucinate content.
```

В `prompt.py` (system prompt): добавить правило:
```
If read returns [FILE UNREADABLE] → immediately retry with search tool.
Do NOT infer, guess, or count content from a failed read.
```

**Метрика успеха:** При read timeout агент переключается на search, не галлюцинирует данные.

---

### B5 — Promote pattern/refusal в normal mode (по умолчанию)

**Файл:** `agent/main.py`

**Проблема:** `promote_successful_pattern()` и `promote_verified_refusal()` вызываются только в `RESEARCHER_MODE=1`. В normal mode pages накапливают синтезированные wiki-паттерны от wiki-lint, но не получают "verified" паттернов из реальных прогонов. После 43 успешных normal-задач — `pages/<type>.md` пусты по verified patterns. Evaluator и builder работают вслепую.

**Решение:**  
Убрать `if RESEARCHER_MODE` проверку вокруг вызовов `promote_successful_pattern()` и `promote_verified_refusal()` в `main.py`. Промоут становится стандартным поведением:

- `score == 1.0` + `OUTCOME_OK` → `promote_successful_pattern(task_id, trajectory)`
- `score == 1.0` + terminal refusal (DENIED/CLARIFICATION/UNSUPPORTED) → `promote_verified_refusal(task_id, outcome)`

Дополнительно: добавить метку источника `source: normal` vs `source: researcher` в promoted pattern — чтобы evaluator мог учитывать "качество" паттерна (researcher-паттерны прошли через reflector, normal-паттерны — нет).

**Метрика успеха:** После прогона normal mode: `pages/<type>.md` содержат `## Successful pattern:` и `## Verified refusal:` записи. Следующий прогон — evaluator/builder видят накопленные паттерны.

---

### B6 — Vault date: prephase ищет date-контекст

**Файл:** `agent/prephase.py`, `agent/prompt.py`

**Проблема:** t41 "what day is today?" → ожидалось `17-03-2026` (дата vault), агент вернул `27-04-2026` (реальная системная дата из TASK CONTEXT). Vault живёт в своей временной рамке; агент читает системное время.

**Решение:**

В `prephase.py`: добавить поиск vault date context — проверить наличие:
1. Блока `VAULT_DATE:` или `today:` в `AGENTS.MD`
2. Файлов `context.json`, `vault-meta.json`, `meta.md` в корне vault
3. Если найдено — извлечь дату и передать в prompt как `VAULT_DATE`

В `prompt.py`: если `VAULT_DATE` доступен — инжектировать в system prompt:
```
VAULT DATE: {vault_date}  ← use this as "today" for all date operations
SYSTEM DATE: {system_date} ← do NOT use for vault operations
```

Добавить правило: `"what day is today" или любой запрос текущей даты → использовать VAULT DATE`.

**Если vault date не найден:** wiki накопит паттерн "проверь AGENTS.MD на date context" через successful promoted patterns из будущих прогонов.

**Метрика успеха:** t41-подобные задачи используют vault date.

---

## Ожидаемое влияние на score

| Изменение | Затронутые задачи | Потенциальный gain |
|-----------|------------------|-------------------|
| A1 CC empty result | Все 43 — эффективность | -токены, +скорость |
| A2 Gate deadlocks | t11, t13 | +2 задачи |
| A3 JSON parse | ~30 задач — лишний шаг | -шаги, +надёжность |
| A4 Timeout recovery | t30 | +1 задача |
| B5 Normal mode promote | Все будущие прогоны | Накопительный эффект |
| B6 Vault date | t41 + аналогичные | +1 задача |

**Прямой gain: +4 задачи** → ~76.7% (33/43)  
**Косвенный gain через накопление:** security semantics, grounding refs, lookup patterns → улучшение в следующих прогонах через promoted pages + DSPy перекомпиляцию

---

## Порядок реализации

1. **A2** (gate deadlocks) — наибольший impact, изолированный файл
2. **A3** (JSON parse) — затрагивает 70% задач, простой фикс
3. **A1** (CC contract) — требует понимания CC internals
4. **A4** (timeout recovery) — простой prompt + loop изменение
5. **B5** (normal mode promote) — убрать один if-guard в main.py
6. **B6** (vault date) — prephase exploration + prompt injection

---

## Что НЕ входит в этот план

- **Security outcome semantics (t28, t33, t37, t20)** — накапливается через `promote_verified_refusal` (B5). После нескольких прогонов pages будут содержать verified refusal patterns → evaluator/builder подхватят. Ручное добавление правила в prompt — риск over-fitting на конкретные кейсы.
- **Missing grounding_refs (t23, t40, t42)** — аналогично, накапливается через successful patterns. DSPy builder оптимизирует подсказку после накопления ≥30 примеров.
- **DSPy перекомпиляция** — после B5 начнут накапливаться примеры, перекомпиляция становится эффективной. Запустить отдельно после 2-3 прогонов.
