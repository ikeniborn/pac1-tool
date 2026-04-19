# Wiki-Memory: Постоянная память агента между сессиями

> Inspired by [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## Проблема

Между сессиями агент теряет всё накопленное знание. Каждая задача решается с нуля:

- Не помнит, что `john@acme.com` — это Senior VP, с которым нужно быть формальным
- Не помнит, что поиск по CRM у этого клиента лучше работает через `search("company:Acme")`
- Не помнит паттерн расписания (board meetings — последняя пятница месяца)
- Повторно допускает ошибки, исправленные в прошлых задачах

Единственная текущая персистентность — это содержимое vault (данные задачи) и `AGENTS.MD` (роль агента). Нет структурированного накопления знаний о том, **как** решать задачи.

---

## Точки входа и выхода в цикле задачи

### Где wiki читается (до выполнения)

Текущий flow в `agent/__init__.py:run_agent()`:

```
1. run_prephase(vm, task_text)          ← task_type ЕЩЁ НЕИЗВЕСТЕН
2. router.resolve_after_prephase()      ← task_type становится известен
3. build_system_prompt(task_type)
4. build_dynamic_addendum(task_type, …) ← DSPy builder
5. run_loop(…)                          ← основной цикл
```

Проблема: prephase запускается до классификации. Поэтому wiki загружается **в два этапа**:

**Этап A — в prephase (без task_type):**
```python
# prephase.py:run_prephase()
# Читаем с локального диска — vault здесь не нужен
from .wiki import load_wiki_base
wiki_base = load_wiki_base(task_text)
# загружает с диска: pages/errors.md + entities.md + entity-страницы по email/именам из task_text
pre.preserve_prefix.append({"role": "user", "content": wiki_base})
```

**Этап B — после classify (с task_type):**
```python
# __init__.py:run_agent() — между шагами 2 и 3
from agent.wiki import load_wiki_patterns
wiki_patterns = load_wiki_patterns(task_type)
# читает с диска: pages/{task_type}.md
pre.preserve_prefix[-1]["content"] += "\n\n" + wiki_patterns
# → тот же preserve_prefix, не компактируется
```

**Этап C — в build_dynamic_addendum (использует wiki):**
```python
# prompt_builder.py
addendum, _, _ = build_dynamic_addendum(
    task_text=task_text,
    task_type=task_type,
    wiki_context=wiki_patterns,   # ← новый аргумент
    …
)
# DSPy builder генерирует addendum зная vault-специфичные паттерны
```

Итоговая схема:

```
task_text → prephase → INDEX.md + errors.md + entities  ┐
                                                          ├─ preserve_prefix (не компактируется)
classifier → task_type → patterns/{type}.md             ┘
                    ↓
            build_dynamic_addendum(wiki_context=…)
                    ↓
            run_loop  ← агент видит wiki с первого шага
```

---

### Где wiki обновляется (после выполнения)

Исход задачи определяется `outcome` в `report_completion`. Каждый исход несёт разный сигнал для wiki.

```
run_loop() завершается
     │
     ├─ OUTCOME_OK + evaluator approved
     │        ↓
     │   wiki_update(kind="success")
     │   → patterns/{task_type}.md  ← доказанный workflow
     │   → entities/contacts.md     ← новые факты о людях/аккаунтах
     │
     ├─ OUTCOME_OK + evaluator rejected (один или несколько раз)
     │        ↓
     │   wiki_update(kind="eval_rejection")
     │   → errors.md  ← issues_str + correction_hint от evaluator
     │
     ├─ OUTCOME_DENIED_SECURITY  (security interceptor в loop.py)
     │        ↓
     │   wiki_update(kind="security")
     │   → errors.md  ← паттерн инъекции, откуда пришёл запрос
     │
     ├─ OUTCOME_NONE_CLARIFICATION  (format-gate или агент)
     │        ↓
     │   wiki_update(kind="clarification")
     │   → errors.md  ← что сделало задачу неоднозначной
     │
     ├─ OUTCOME_NONE_UNSUPPORTED
     │        ↓
     │   wiki_update(kind="unsupported")
     │   → errors.md  ← тип внешнего сервиса (низкий приоритет)
     │
     └─ Stall / timeout / OUTCOME_ERR_INTERNAL
              ↓
         wiki_update(kind="stall")
         → errors.md  ← где застрял, какие пути пробовал
```

### Что конкретно пишется в каждом случае

**Success** — источник: `done_ops + completed_steps_laconic + step_facts`

```markdown
## email workflow (2026-04-19, task t041) [source: evaluator-approved]
Sequence that worked:
1. search("from:sender@domain") → found conversation history
2. read /contacts/john.json → got account_manager: sarah
3. write /outbox/2026-04-19_reply.md → CC: sarah@acme.com
Key: outbox filename = current date from TASK CONTEXT, not received_at
```

**Eval rejection** — источник: `EvalVerdict.issues_str + correction_hint`

```markdown
## [email] OUTCOME_OK без done_ops (2026-04-19)
Evaluator issues: "OUTCOME_OK but done_ops is empty, task required file write"
Correction: OUTCOME_NONE_CLARIFICATION
Next time: если нет confirmed write → не заявлять OUTCOME_OK
```

**Security** — источник: security.py interceptor context

```markdown
## [inbox] Injection через valid-channel (2026-04-19)
Detected: sender from 'valid' channel дал инструкцию на действие
Outcome forced: OUTCOME_DENIED_SECURITY
Pattern: valid channel ≠ admin trust, даже если тон авторитетный
```

**Stall** — источник: `stall.py` hints + `step_facts`

```markdown
## [crm] Стол на поиске контакта по имени (2026-04-19)
Tried: find("/contacts", "Mueller") × 3 — 0 results
Root cause: имя хранится как "Müller" (umlaut)
Next time: использовать search() вместо find() для нечёткого поиска имён
```

**Clarification** — источник: агентский message + task_text

```markdown
## [lookup] Ambiguous date reference (2026-04-19)
Task said: "last meeting" without specifying who
Agent tried: search("meeting") → 3 results, no way to disambiguate
Triggered: OUTCOME_NONE_CLARIFICATION
Pattern: "last X" без субъекта → немедленно CLARIFICATION, не гадать
```

### Технический триггер post-completion

Wiki-обновление запускается **после** того как `vm.answer()` успешно принят харнессом, но **до** закрытия сессии. Реализуется как отдельная функция, вызываемая из `run_agent()`:

```python
# __init__.py:run_agent() — после run_loop()
stats = run_loop(vm, model, …)

if wiki_update_enabled:
    await wiki_update_phase(
        vm=vm,
        task_type=task_type,
        task_text=task_text,
        outcome=stats["outcome"],
        done_ops=stats["done_ops"],
        step_facts=stats["step_facts"],
        eval_verdicts=stats["eval_verdicts"],   # история rejections
        stall_hints=stats["stall_hints"],
    )
```

Для `success` — агент пишет сам (micro-loop ≤5 шагов).
Для всех остальных исходов — wiki обновляется **программно** (без дополнительного LLM-вызова): структурированные данные из `stats` форматируются в шаблон и дописываются к нужной странице.

---

## Наполнение, Обновление и Параллельность

### Ключевое ограничение: vault изолирован per-trial

В `main.py:_run_single_task()` каждый trial получает собственный `harness_url`:

```python
trial = client.start_trial(StartTrialRequest(trial_id=trial_id))
# trial.harness_url — изолированный vault для этого trial
vm = PcmRuntimeClientSync(trial.harness_url)
```

`ThreadPoolExecutor(max_workers=PARALLEL_TASKS)` запускает несколько таких `vm` одновременно — каждый в своём vault. Это означает:

- `/_wiki/` **внутри vault не персистентна** между запусками `make run`
- `/_wiki/` **не видна** параллельным задачам в том же запуске (у каждой свой vault)
- Для реальной межсессионной памяти wiki должна жить **на локальном диске**, рядом с `data/`

### Физическое расположение: data/wiki/

```
pac1-tool/
├── data/
│   ├── prompt_builder_program.json   ← DSPy compiled (аналог)
│   ├── evaluator_program.json        ← DSPy compiled (аналог)
│   └── wiki/                         ← Wiki (NEW, рядом с DSPy данными)
│       ├── pages/                    ← скомпилированные страницы (lint пишет)
│       │   ├── errors.md
│       │   ├── email.md
│       │   ├── crm.md
│       │   └── entities.md
│       └── fragments/                ← append-only, задачи пишут сюда
│           ├── errors/
│           │   └── t042_20260419T100030Z.md
│           ├── email/
│           │   └── t041_20260419T100000Z.md
│           └── entities/
│               └── t041_20260419T100000Z.md
```

Wiki читается с локального диска до prephase и пишется на локальный диск после завершения задачи — **без vault-инструментов**.

### Паттерн Fragment: параллельные записи без конфликтов

Проблема параллельных write в один файл:

```
Thread A: read pages/email.md → modify → write  ← перезаписывает Thread B
Thread B: read pages/email.md → modify → write  ← Thread A потерян
```

Решение — **append-only fragments**: каждая задача создаёт новый файл с уникальным именем.

```python
# agent/wiki.py — после завершения run_loop()
def write_fragment(task_id: str, category: str, content: str) -> None:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = WIKI_DIR / "fragments" / category / f"{task_id}_{ts}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    # Нет read-modify-write → нет гонок между потоками
```

`t041_20260419T100000Z.md` и `t042_20260419T100030Z.md` — разные файлы, не конкурируют.

### Lint: когда pages компилируются из fragments

Lint — единственный процесс, пишущий в `pages/`. Запускается **один раз в начале каждого `make run`**, до `ThreadPoolExecutor`:

```python
# main.py:main() — до ThreadPoolExecutor
from agent.wiki import run_wiki_lint
if WIKI_LINT_ENABLED:
    run_wiki_lint()   # читает fragments/ → мержит → пишет pages/ → чистит старые fragments

with ThreadPoolExecutor(max_workers=PARALLEL_TASKS) as pool:
    futures = {pool.submit(_run_single_task, tid, …) for tid in run.trial_ids}
```

Во время параллельного выполнения **lint не запускается** — только fragment-записи. Это гарантирует:
- `pages/` стабильны на весь run (читаются параллельными задачами без блокировок)
- `fragments/` растут атомарно (новые файлы, не модификация существующих)

### Жизненный цикл за два прогона

```
─── make run #1 ───────────────────────────────────────────────────────────
  Lint: fragments/ пусто → pages/ пусто (первый запуск)

  Parallel tasks:
    t001: prephase читает pages/errors.md  → пусто
          run_loop … OUTCOME_OK
          write_fragment("t001", "email", "workflow that worked…")

    t002: prephase читает pages/errors.md  → пусто
          run_loop … evaluator rejected
          write_fragment("t002", "errors", "OUTCOME_OK without done_ops…")

  Run ends:
    data/wiki/fragments/email/t001_…md    ✓
    data/wiki/fragments/errors/t002_…md   ✓

─── make run #2 ───────────────────────────────────────────────────────────
  Lint: читает fragments/ → мержит в pages/:
    pages/email.md   ← содержит workflow от t001
    pages/errors.md  ← содержит ошибку от t002
    fragments/ очищается (или архивируется)

  Parallel tasks:
    t003: prephase читает pages/email.md  → видит workflow от t001 ✓
    t004: prephase читает pages/errors.md → знает ловушку от t002 ✓

─── make run #3 ────────────────────────────────────────────────────────── 
  Lint: мержит новые fragments/ в pages/ (накопление продолжается)
```

### Что lint делает при мерже

```python
def run_wiki_lint():
    for category in ["email", "crm", "errors", "entities", ...]:
        fragments = sorted((WIKI_DIR / "fragments" / category).glob("*.md"))
        if not fragments:
            continue

        existing = (WIKI_DIR / "pages" / f"{category}.md").read_text()
        new_entries = [f.read_text() for f in fragments]

        # LLM-вызов: дедупликация + противоречия + актуализация
        merged = llm_merge(existing, new_entries)

        (WIKI_DIR / "pages" / f"{category}.md").write_text(merged)

        # Архивировать, а не удалять — для отладки
        for f in fragments:
            f.rename(WIKI_DIR / "archive" / category / f.name)
```

`llm_merge` — лёгкий LLM-вызов (не DSPy, не evaluator): убирает дубликаты, разрешает противоречия, обновляет `last_seen` даты. Fail-open: если LLM недоступен, просто конкатенирует fragments в pages.

### Гарантии актуальности

| Момент | Что видит задача |
|--------|-----------------|
| Первый `make run` | Пустые pages (wiki не накоплена) |
| Второй `make run` | pages содержат знания из первого run |
| Параллельные задачи в одном run | Одинаковые стабильные pages (lint прошёл до них) |
| Задача в текущем run | НЕ видит fragments других задач этого же run |

Последний пункт — осознанный трейдофф: актуальность в пределах одного run не нужна (задачи независимы), зато чтения без блокировок.

---

## Источники сырых данных

Wiki — это **дистилляция**, а не отдельное хранилище. Сырые данные уже существуют в двух местах:

### 1. Vault (статичные файлы)

```
/contacts/*.json     →  факты о людях (роль, email, аккаунт)
/accounts/*.json     →  факты об организациях
/inbox/*.txt         →  паттерны входящих запросов
/outbox/*.txt        →  примеры удачных ответов
```

Vault существует независимо от wiki. Агент читает его при каждой задаче — wiki избавляет от необходимости перечитывать одно и то же.

### 2. step_facts текущей сессии (эфемерные)

В `loop.py` уже накапливаются факты о каждом шаге:

```
READ   /contacts/john.json  → узнал: john — VP, formal tone
SEARCH "from:john"          → узнал: работает через email-поиск
ERROR  write(/outbox/5.txt) → узнал: неверный формат пути
DONE   WRITTEN /outbox/...  → узнал: правильный формат
```

Эти факты живут только в рамках сессии. После `report_completion` они **исчезают**. Wiki — это межсессионный кэш `step_facts`.

### Пайплайн накопления

```
make run N:
  vault-файлы (per-trial) + task_text
       ↓  (агент читает/работает)
  step_facts  ← loop.py собирает автоматически
       ↓  (post-completion: write_fragment на локальный диск)
  data/wiki/fragments/  ← один новый файл на задачу

make run N+1:
  wiki_lint()  ← мержит fragments/ → pages/  (до параллельных задач)
  prephase загружает data/wiki/pages/  →  агент стартует с накопленным знанием
```

Таким образом, **vault — слой сырых данных текущей задачи**, **wiki — локальный диск с дистиллированным опытом между запусками**, а `step_facts` — временный буфер внутри одной задачи.

---

## Концепция: Karpathy Wiki Pattern

Карпати предлагает вместо RAG (каждый раз искать в сырых источниках) поддерживать **живую wiki** — набор Markdown-страниц, которые LLM сам инкрементально дополняет и актуализирует.

```
Сырые данные  →  [LLM Ingest]  →  Wiki (Markdown-страницы)
                                        ↓
Вопрос задачи →  [LLM Query]   →  Ответ (с wiki-контекстом)
                                        ↓
               [LLM Lint]      →  Актуализация, устранение противоречий
```

Ключевое свойство: **знания накапливаются**, а не дедуцируются заново при каждом запросе.

---

## Архитектура Wiki для PAC1 Агента

### Расположение

Wiki живёт на **локальном диске**, рядом с DSPy-данными — не внутри harness vault (vault изолирован per-trial и не персистентен между запусками):

```
pac1-tool/data/wiki/
├── pages/                     # Скомпилированные страницы (lint пишет, задачи читают)
│   ├── errors.md              # Известные ловушки и решения
│   ├── entities.md            # Люди, организации — накопленные факты
│   ├── email.md               # Паттерны для email-задач
│   ├── crm.md
│   ├── lookup.md
│   ├── temporal.md
│   └── inbox.md
├── fragments/                 # Append-only записи от каждой задачи
│   ├── errors/
│   ├── email/
│   ├── entities/
│   └── …/
└── archive/                   # Обработанные fragments (для отладки)
```

Чтение: `Path("data/wiki/pages/…").read_text()` — до prephase, без vault-инструментов.
Запись: `Path("data/wiki/fragments/…").write_text()` — после run_loop, новый файл на каждую задачу.

### Типы страниц

#### 1. Entity-страницы — что знаем о конкретных сущностях

```markdown
# contacts.md

## john.smith@acme.com
- Роль: Senior VP of Operations
- Предпочтительный тон: формальный
- Account Manager: Sarah Johnson (/contacts/sarah_johnson.json)
- Паттерн: отвечает медленно, предпочитает краткие письма
- Последнее взаимодействие: 2026-03-15

## alice@startupxyz.io
- Роль: Founder
- Тон: неформальный, прямой
- Связанный аккаунт: /accounts/startupxyz.json
```

#### 2. Pattern-страницы — как решать задачи данного типа

```markdown
# patterns/email.md

## Эффективный workflow
1. Сначала `search("from:<адрес>")` — находит историю переписки
2. Проверить `/outbox/` — нет ли похожих отправленных писем
3. Читать `AGENTS.MD` раздел outbox перед записью

## Ловушки
- Не использовать `tree` для поиска контакта — медленно, лучше `search`
- CC всегда включать account manager при письмах клиентам
- Формат даты в subject: YYYY-MM-DD

## Инсайты из задач
- "priority:high" письма требуют ответа в тот же день (паттерн из t023, t041)
- Клиенты с `tier:enterprise` — всегда formal tone
```

#### 3. Temporal-страница — паттерны расписания

```markdown
# patterns/temporal.md

## Регулярные события
- Weekly standup: каждый понедельник 9:00
- Board meeting: последняя пятница месяца
- Billing cycle: 1-е число каждого месяца

## Временные правила
- Задачи "ASAP" интерпретировать как: следующий рабочий день
- Квартальные отчёты: последняя неделя марта/июня/сентября/декабря
```

#### 4. Errors.md — известные ловушки

```markdown
# errors.md

## Ошибки и решения

### write permission denied на /outbox/
Причина: путь не соответствует конвенции. Правильный формат: `/outbox/YYYY-MM-DD_<topic>.txt`

### search возвращает 0 результатов
Причина: слишком специфичный запрос. Решение: начинать с broad-запроса, сужать итеративно.

### Контакт не найден через find
Причина: имя хранится в нескольких форматах. Решение: `search("email:<адрес>")` надёжнее.
```

---

## Интеграция с Существующей Архитектурой

### Слой 1: Prephase — загрузка Wiki

```
run_prephase()
  ├── tree -L 2 /              (существующий)
  ├── AGENTS.MD                (существующий)
  ├── preload referenced dirs  (существующий)
  └── [NEW] wiki_preload()
       ├── read /_wiki/INDEX.md
       ├── read /_wiki/patterns/<task_type>.md   (по типу задачи)
       ├── read /_wiki/errors.md
       └── read /_wiki/entities/<relevant>.md    (по упомянутым именам/email в задаче)
```

Wiki-контент попадает в `preserve_prefix` — **не компактируется** на протяжении всей сессии.

### Слой 2: Loop — обнаружение знаний

В существующей системе `step_facts` накапливают факты о прочитанных файлах.
Расширение: добавить `wiki_candidates` — факты, достойные записи в wiki.

```python
# В _extract_fact() — добавить эвристику:
# Если агент читает контакт и тот не в wiki/entities → кандидат
# Если агент делает N+1 попытку поиска → паттерн ошибки → кандидат errors.md
```

### Слой 3: Post-completion — обновление Wiki

После успешного `report_completion` (до закрытия сессии):

```
evaluator.py → approve → [NEW] wiki_update_phase()
  ├── Инструкция агенту: "Обнови wiki по итогам задачи"
  ├── Агент: читает INDEX.md, определяет что обновить
  ├── Агент: пишет/обновляет 1-3 wiki-страницы
  └── Агент: обновляет INDEX.md (дата изменения)
```

Это **дополнительный микро-цикл** (≤5 шагов) после основной задачи.

### Слой 4: Lint — периодическая актуализация

Отдельный тип задачи `wiki_lint` (запускается раз в N задач):

```python
# В classifier.py — добавить тип:
TASK_TYPE_WIKI_LINT = "wiki_lint"

# Задача: найти противоречия, устаревшие данные, обновить INDEX
```

---

## Формат INDEX.md

```markdown
# Wiki Index

last_updated: 2026-04-19
total_pages: 12

## Entities
- [contacts.md](entities/contacts.md) — 8 контактов — обновлён 2026-04-18
- [accounts.md](entities/accounts.md) — 3 аккаунта — обновлён 2026-04-15

## Patterns
- [email.md](patterns/email.md) — workflow, ловушки — обновлён 2026-04-19
- [crm.md](patterns/crm.md) — обновлён 2026-04-10
- [temporal.md](patterns/temporal.md) — обновлён 2026-04-12
- [lookup.md](patterns/lookup.md) — обновлён 2026-04-08

## Meta
- [errors.md](errors.md) — 7 известных ловушек — обновлён 2026-04-17
- [schema.md](schema.md) — конвенции wiki
```

---

## Промпт-интеграция

### Дополнение к system prompt (блок `_WIKI`)

```
## Knowledge Wiki

You have access to a persistent knowledge wiki at /_wiki/.
Before starting work, wiki context is pre-loaded for you (see above).

The wiki contains:
- Known entities (contacts, accounts) with behavioral notes
- Proven patterns for this task type
- Known pitfalls and their solutions

After completing your task (after report_completion), you MUST:
1. Read INDEX.md to see what pages exist
2. Update 1-3 relevant wiki pages with new knowledge gained
3. Use concise, factual entries (no speculation)
4. Update INDEX.md last_updated timestamp

Wiki update format:
- New fact about entity → append to entities/<type>.md
- Discovered pattern → append to patterns/<task_type>.md
- Hit a non-obvious error → append to errors.md
```

---

## Сравнение с Текущим Состоянием

| Аспект | Сейчас | С Wiki |
|--------|--------|--------|
| Знание о контактах | Каждый раз читает из vault | Предзагружено + кэшировано в wiki |
| Паттерны задач | В system prompt (статично) | В wiki (накапливается из реальных задач) |
| Ошибки | Повторяются | Документируются, избегаются |
| Накопление опыта | Нет | Линейный рост wiki после каждой задачи |
| Context window | Только текущая задача | Текущая + предзагруженная wiki |

---

## Реализация: Минимальный MVP

### Фаза 1 — Passive Wiki (читаем, не пишем)

1. Создать `/_wiki/` структуру вручную с базовыми страницами
2. Добавить `wiki_preload()` в `prephase.py`:
   ```python
   async def wiki_preload(vm, task_type: str, task_text: str) -> str:
       pages = ["/_wiki/INDEX.md", f"/_wiki/patterns/{task_type}.md", "/_wiki/errors.md"]
       content = []
       for path in pages:
           result = await vm.read(path)
           if result.ok:
               content.append(f"## Wiki: {path}\n{result.content}")
       return "\n\n".join(content)
   ```
3. Инжектировать в `preserve_prefix` (после AGENTS.MD)
4. **Измерить**: улучшается ли качество решений с wiki-контекстом?

### Фаза 2 — Active Wiki (агент пишет)

1. Добавить блок `_WIKI` в system prompt с инструкцией обновления
2. Добавить пост-completion микро-цикл в `loop.py`
3. Добавить `wiki_candidates` в `step_facts` для сигнализации

### Фаза 3 — Smart Loading

1. Entity-extraction из task_text (email-адреса, имена) → загружать только релевантные страницы
2. `wiki_lint` как плановый тип задачи
3. Версионирование wiki (git-like, через временны́е метки в файлах)

---

## Риски и Ограничения

**Галлюцинации в wiki**: Агент может записать неверный факт. Митигация: wiki-записи с `source: task_id` + lint-фаза проверяет противоречия.

**Разрастание контекста**: При большой wiki INDEX.md + все страницы = много токенов. Митигация: загружать только страницу своего task_type + упомянутые entities.

**Устаревание**: Факт актуален на момент записи. Митигация: `last_seen: date` на каждой записи, lint удаляет старые.

**Масштаб**: При сотнях сессий wiki растёт. Митигация: как отмечает сам Карпати — при большом масштабе добавить vector search поверх wiki-файлов.

---

## Взаимодействие с DSPy

Два DSPy-компонента — `prompt_builder.py` и `evaluator.py` — напрямую влияют на то, что попадает в wiki и откуда wiki черпает свою ценность.

### prompt_builder: статичная wiki vs динамическая

`PromptAddendum` signature содержит ~120 строк жёстко прописанных правил в docstring:

```python
class PromptAddendum(dspy.Signature):
    """...
    ## Person Lookup
    If the task mentions a person by name:
    - First bullet MUST be: search contacts/ for that person's record
    ...
    ## Bulk Scanning
    For tasks that count, aggregate...
    """
```

Это и есть **статичная wiki** — знания, накопленные вручную и зашитые в сигнатуру. Проблема: они обновляются только через ручной коммит.

**Отношение wiki ↔ prompt_builder:**

```
Сейчас:
  DSPy signature docstring  =  жёстко захардкоженные паттерны
  COPRO оптимизирует текст docstring по примерам

С wiki:
  DSPy signature docstring  =  минимальный скелет (формат вывода, rejection rules)
  wiki/patterns/<type>.md   =  живые паттерны, растущие из реальных задач
  prompt_builder получает wiki как дополнительный input-field
```

**Конкретное изменение сигнатуры:**

```python
class PromptAddendum(dspy.Signature):
    """Generate 3–6 bullet points of task-specific guidance.
    Bullet 1: which folder to open first. Bullet 2: key risk.
    Use wiki_context as primary knowledge source — it contains proven patterns
    specific to THIS vault. Docstring rules are fallback only."""

    task_type: str = dspy.InputField(...)
    task_text: str = dspy.InputField(...)
    vault_tree: str = dspy.InputField(...)
    agents_md: str = dspy.InputField(...)
    wiki_context: str = dspy.InputField(
        desc="pre-loaded wiki: proven patterns and errors for this task type"
    )
    addendum: str = dspy.OutputField(...)
```

Wiki становится **первичным источником**, docstring — запасным. По мере роста wiki hardcoded-правила из docstring можно постепенно вычищать.

**COPRO-оптимизация с учётом wiki:** при оптимизации `optimize_prompts.py` в примеры (`dspy_examples.jsonl`) будет включён wiki_context того времени → компилированная программа учится использовать wiki эффективно.

---

### evaluator: источник сигнала для wiki

Evaluator — самый ценный источник обновлений wiki, потому что его выходы уже **качественно отфильтрованы**.

#### Rejection → errors.md

Когда evaluator отклоняет задачу, он генерирует `issues_str` + `correction_hint`:

```python
# evaluator возвращает:
EvalVerdict(
    approved=False,
    issues=["OUTCOME_OK but done_ops is empty", "task required file write"],
    correction_hint="OUTCOME_NONE_CLARIFICATION"
)
```

Это прямой кандидат для `/_wiki/errors.md`:

```markdown
## [email] OUTCOME_OK без done_ops
Причина: агент заявил об успехе, не выполнив ни одной записи.
Correction: проверить что write() был вызван до report_completion.
source: evaluator, 2026-04-19
```

#### Approval → patterns/

Когда evaluator одобряет с `approved=True`, у него есть `completed_steps` — последовательность шагов, которая **доказанно привела к успеху**. Это кандидат для `/_wiki/patterns/<task_type>.md`:

```markdown
## Доказанный workflow (email, 2026-04-19)
1. search("from:<sender>") — нашёл историю
2. read /contacts/<id>.json — получил account_manager
3. write /outbox/... — отправил с CC
source: evaluator-approved, task_id: t041
```

#### Evaluator как гейткипер wiki

Вместо того чтобы агент записывал в wiki свободно, evaluator может верифицировать wiki-обновления:

```
wiki_update_phase():
  агент генерирует предложение обновления
       ↓
  evaluator.evaluate_wiki_update(proposed_entry, evidence=step_facts)
       ↓
  approved → write to /_wiki/
  rejected → skip (не засоряем wiki галлюцинациями)
```

#### Skepticism level из wiki

Wiki может влиять на `skepticism` при вызове evaluator. Если в `/_wiki/errors.md` есть запись для данного task_type — автоматически повышать скептицизм:

```python
# В loop.py перед вызовом evaluate_completion():
skepticism = "mid"
if wiki_has_known_errors(task_type, wiki_context):
    skepticism = "high"  # этот тип задач раньше вызывал ошибки
```

---

### Временны́е шкалы: wiki vs DSPy

| Компонент | Когда обновляется | Как обновляется |
|-----------|------------------|-----------------|
| Wiki | После каждой задачи (онлайн) | Агент пишет файлы в `/_wiki/` |
| DSPy compiled program | Батчево через `optimize_prompts.py` | COPRO оптимизирует по `dspy_examples.jsonl` |
| DSPy signature docstring | При коммите в код | Вручную разработчиком |

**Ключевое:** wiki и DSPy не конкурируют — они работают на разных временны́х шкалах. Wiki — быстрый онлайн-слой (свежие паттерны), DSPy — медленный оффлайн-слой (оптимизированные инструкции).

### Петля обратной связи

```
Задача N
  → evaluator approval + step_facts
  → wiki update (/_wiki/patterns/email.md)

Задача N+1
  → prephase загружает wiki
  → prompt_builder получает wiki_context
  → агент работает с учётом прошлого опыта
  → лучший результат → лучший пример в dspy_examples.jsonl

optimize_prompts.py (оффлайн)
  → COPRO видит примеры с wiki_context
  → учится генерировать addendum эффективнее
  → compiled program улучшается
```

Wiki кормит DSPy примерами лучшего качества; DSPy генерирует лучший addendum; агент решает задачи лучше; evaluator одобряет больше → wiki растёт точнее.

---

## Связь с Существующими Компонентами

- `prephase.py:run_prephase()` — точка интеграции загрузки wiki
- `loop.py:run_loop()` — точка интеграции пост-completion обновления
- `prompt.py:build_system_prompt()` — добавить блок `_WIKI` в релевантные task types
- `prompt_builder.py:PromptAddendum` — добавить `wiki_context` как InputField, вычистить hardcoded правила
- `evaluator.py:evaluate_completion()` — источник rejection→errors.md и approval→patterns/
- `log_compaction.py:build_digest()` — wiki-кандидаты из step_facts
- `agent/classifier.py` — добавить `wiki_lint` как тип задачи (Фаза 3)
