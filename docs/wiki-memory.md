# Wiki-Memory: Постоянная память агента между сессиями

> Inspired by [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

Реализовано в `agent/wiki.py`. Вызывается из `main.py` и `agent/__init__.py`.

---

## Проблема

Между сессиями агент теряет всё накопленное знание. Каждая задача решается с нуля:

- Не знает паттернов ошибок, которые уже встречались
- Не помнит, что find() ненадёжен для поиска по имени — нужен search()
- Повторно допускает одни и те же ошибки

Wiki решает это через **дистилляцию опыта** в человекочитаемые Markdown-страницы.

---

## Физическое расположение

Wiki живёт на **локальном диске** рядом с DSPy-данными — не внутри harness vault (vault изолирован per-trial и не персистентен между запусками):

```
pac1-tool/data/wiki/
├── pages/                  # Скомпилированные страницы (lint пишет, задачи читают)
│   ├── errors.md           # Ловушки и решения
│   ├── contacts.md         # Паттерны работы с контактами
│   ├── accounts.md         # Паттерны работы с аккаунтами
│   ├── email.md            # Паттерны email-задач
│   ├── inbox.md            # Паттерны inbox-задач
│   ├── queue.md            # Паттерны queue-задач
│   ├── crm.md              # Паттерны crm-задач
│   ├── lookup.md           # Паттерны lookup-задач
│   ├── temporal.md         # Паттерны temporal-задач
│   └── ...                 # Остальные task_type страницы
├── fragments/              # Append-only записи (задачи пишут, lint читает)
│   ├── errors/
│   ├── email/
│   ├── contacts/
│   ├── accounts/
│   └── .../
└── archive/                # Обработанные fragments (для отладки)
    ├── errors/
    └── .../
```

Чтение: `Path("data/wiki/pages/…").read_text()` — **без vault-инструментов**.
Запись: `Path("data/wiki/fragments/…").write_text()` — после run\_loop, **один файл на задачу**.

---

## Интеграция в жизненный цикл задачи

### Где wiki читается (в prephase)

`agent/__init__.py:run_agent()` вызывает wiki **в два этапа**:

**Этап A — базовые страницы (после prephase, до run\_loop):**

```python
from agent.wiki import load_wiki_base, load_wiki_patterns

wiki_base = load_wiki_base(task_text)
# Загружает: pages/errors.md + pages/contacts.md + pages/accounts.md
# Форматирует с заголовками: "## Wiki: Known Errors & Solutions", etc.
```

**Этап B — страница типа задачи (после classify):**

```python
wiki_patterns = load_wiki_patterns(task_type)
# Загружает: pages/{task_type}.md
# Форматирует: "## Wiki: {task_type} Patterns\n{content}"
```

Оба результата инжектируются в `pre.log` до `run_loop`. Контент попадает в `preserve_prefix` — **не компактируется** на протяжении всей сессии.

**Fail-open**: оба вызова возвращают `""` если страница не существует — агент работает без wiki до первого накопления.

### Где wiki обновляется (после run\_loop)

После завершения `run_loop()` вызывается `format_fragment()` + `write_fragment()`:

```python
# agent/__init__.py:_write_wiki_fragment()
pairs = format_fragment(
    outcome=stats["outcome"],
    task_type=task_type,
    task_id=task_id,
    task_text=task_text,
    step_facts=stats["step_facts"],
    done_ops=stats["done_ops"],
    stall_hints=stats["stall_hints"],
    eval_last_call=stats["eval_last_call"],
)
for content, category in pairs:
    write_fragment(task_id, category, content)
```

`format_fragment()` возвращает **список пар `(content, category)`** — один вызов может породить несколько фрагментов:

| Условие | category | Содержит |
|---------|----------|----------|
| OUTCOME\_OK | `task_type` | done\_ops, step\_facts, stall\_hints, eval summary |
| OUTCOME\_DENIED\_SECURITY | `errors` | То же |
| OUTCOME\_NONE\_CLARIFICATION | `errors` | То же |
| Есть stall\_hints (любой outcome) | `errors` | То же |
| Есть факты из `contacts/` в step\_facts | `contacts` | Только contact-факты |
| Есть факты из `accounts/` в step\_facts | `accounts` | Только account-факты |

> **Важно:** entity-фрагменты (contacts, accounts) пишутся **всегда независимо от outcome** — это накопление структурных знаний о vault.

---

## Структура фрагмента

`_build_raw_fragment()` создаёт YAML front-matter + секции:

```markdown
---
task_id: t041
task_type: email
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Send a reply to john@acme.com about the Q2 report'
---

DONE OPS:
- WRITTEN: /outbox/2026-04-20_reply_to_john.json

STEP FACTS:
- read: /contacts/john.json → name: John Smith, account_id: acct_007
- read: /accounts/acct_007.json → name: Acme Corp, account_manager: sarah@acme.com
- write: /outbox/2026-04-20_reply_to_john.json → WRITTEN

EVALUATOR:
approved: true
steps: searched contacts, read account, wrote outbox

STALL HINTS:
(only if stall occurred)
```

Entity-фрагмент (`_build_entity_raw()`) — упрощённый: только task\_id, date и список фактов.

---

## Lint: компиляция fragments → pages

### Когда запускается

`run_wiki_lint(model, cfg)` вызывается **дважды** в `main.py`:

```python
# Перед ThreadPoolExecutor — компилирует фрагменты прошлых запусков
if WIKI_LINT_ENABLED:
    run_wiki_lint(model=router.classifier, cfg=router.configs[router.classifier])

with ThreadPoolExecutor(max_workers=PARALLEL_TASKS) as pool:
    ...   # параллельные задачи пишут новые fragments

# После ThreadPoolExecutor — компилирует фрагменты этого запуска
if WIKI_LINT_ENABLED:
    run_wiki_lint(model=router.classifier, cfg=router.configs[router.classifier])
```

### Алгоритм

```python
def run_wiki_lint(model, cfg):
    for category in sorted(fragments_dir.iterdir()):
        fragments = sorted(frag_dir.glob("*.md"))
        existing = read_page(category)          # текущая страница
        new_entries = [f.read_text() for f in fragments]

        merged = _llm_synthesize(existing, new_entries, category, model, cfg)

        pages_dir / f"{category}.md".write_text(merged)

        # Архивировать, а не удалять
        for f in fragments:
            f.rename(archive_dir / category / f.name)
```

**Fail-open**: если LLM-синтез недоступен — `_concat_merge()` просто конкатенирует фрагменты в страницу.

### LLM-синтез (Variant C)

Каждая категория имеет **свой системный промт** в `_LINT_PROMPTS`:

| Категория | Суть промта | Запрет |
|-----------|-------------|--------|
| `errors` | Извлечь паттерны ошибок: name / condition / root cause / solution | Записи без actionable solution |
| `contacts` | Доказанные workflow, риски, инсайты | Индивидуальные записи о контактах (`## john@...`) |
| `accounts` | Доказанные workflow, риски, инсайты | Индивидуальные записи об аккаунтах (`## acct_NNN`) |
| `queue` | Workflow и паттерны | Vault-специфичные данные: handles, usernames, OTP tokens |
| `inbox` | Workflow и паттерны | Vault-специфичные данные: handles, имена, channel entries |
| _остальные_ | `_pattern_default`: workflow, риски, инсайты | — |

Промт передаётся через `call_llm_raw()` с `plain_text=True` и `max_tokens=4000`.

---

## Параллельность без гонок

**Проблема:** несколько потоков хотят обновить одну страницу одновременно.

**Решение — append-only fragments:**

```python
def write_fragment(task_id: str, category: str, content: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = fragments_dir / category / f"{task_id}_{ts}.md"
    path.write_text(content)
    # Нет read-modify-write → нет гонок
```

`t041_20260420T100000Z.md` и `t042_20260420T100030Z.md` — разные файлы.

**Гарантии:**

| Момент | Что видит задача |
|--------|-----------------|
| Первый `make run` | Пустые pages (wiki не накоплена) |
| Второй `make run` | pages содержат знания из первого run |
| Параллельные задачи в одном run | Одинаковые стабильные pages (lint прошёл до них) |
| Задача в текущем run | НЕ видит fragments других задач этого же run |

---

## Категории и маппинг типов задач

```python
# wiki.py
_TYPE_TO_PAGE: dict[str, str] = {
    "email":    "email",
    "inbox":    "inbox",
    "crm":      "crm",
    "lookup":   "lookup",
    "temporal": "temporal",
    "queue":    "queue",
    "capture":  "capture",
    "distill":  "distill",
    "think":    "think",
    "default":  "default",
}
```

Три базовые страницы (`errors`, `contacts`, `accounts`) загружаются **для всех типов задач** через `load_wiki_base()`. Страница типа задачи — только для соответствующих через `load_wiki_patterns()`.

---

## Жизненный цикл за два прогона

```
─── make run #1 ─────────────────────────────────────────────────────
  Lint: fragments/ пусто → ничего не делает

  Параллельные задачи:
    t001: wiki = "" (пусто)
          run_loop → OUTCOME_OK
          write_fragment("t001", "email", "<raw fragment>")
          write_fragment("t001", "contacts", "<entity facts>")

    t002: wiki = "" (пусто)
          run_loop → OUTCOME_NONE_CLARIFICATION
          write_fragment("t002", "errors", "<raw fragment>")

  После ThreadPool:
    Lint: email/t001 → pages/email.md
          errors/t002 → pages/errors.md
          contacts/t001 → pages/contacts.md
          Архивирует фрагменты

─── make run #2 ─────────────────────────────────────────────────────
  Lint: fragments/ пусто → ничего не делает
        (фрагменты уже скомпилированы в конце run #1)

  Параллельные задачи:
    t003: wiki_base = errors.md + contacts.md + accounts.md ✓
          wiki_patterns("email") = email.md ✓
          run_loop → агент видит накопленный опыт

    t004: run_loop → OUTCOME_OK
          write_fragment("t004", "email", …)

  После ThreadPool:
    Lint: email/t004 + email.md (existing) → обновлённый email.md
```

---

## Связь с DSPy-компонентами

### prompt\_builder (prompt\_builder.py)

DSPy `PromptAddendum` signature содержит захардкоженные правила в docstring — это **статичная wiki**. Живая wiki дополняет её динамически:

```
Сейчас:
  wiki_base + wiki_patterns → инжектируются в log до run_loop
  → агент видит накопленный опыт

Будущее (Phase 3):
  wiki_context передаётся как дополнительный input-field в PromptAddendum
  → COPRO оптимизирует с учётом wiki_context
```

### evaluator (evaluator.py)

Evaluator — источник ценного сигнала для wiki:

- `approved=True` + `step_facts` → фрагмент идёт в `task_type` категорию (доказанный workflow)
- `approved=False` + `issues_str` → фрагмент идёт в `errors` (correction hint)

Petля обратной связи:

```
Задача N → evaluator rejection → errors fragment
  → Lint → pages/errors.md
  → Задача N+1 → load_wiki_base() → агент видит ловушку
  → лучший результат → evaluator approves
  → email fragment → pages/email.md растёт
```

---

## Переменные окружения

| Переменная | Описание |
|-----------|----------|
| `WIKI_LINT_ENABLED=1` | Включить wiki lint (по умолчанию включён в main.py) |
| `LOG_LEVEL=DEBUG` | Логировать записи фрагментов (`[wiki] fragment written: …`) |

---

## Публичный API (agent/wiki.py)

```python
def load_wiki_base(task_text: str = "") -> str
# Загрузить errors.md + contacts.md + accounts.md для всех задач
# Fail-open: "" если страницы нет

def load_wiki_patterns(task_type: str) -> str
# Загрузить страницу паттернов для конкретного типа задачи
# Fail-open: "" если страницы нет

def write_fragment(task_id: str, category: str, content: str) -> None
# Thread-safe append-only запись фрагмента
# Имя файла: {task_id}_{UTC_timestamp}.md

def format_fragment(
    outcome, task_type, task_id, task_text,
    step_facts, done_ops, stall_hints, eval_last_call
) -> list[tuple[str, str]]
# Сформировать список (content, category) для последующего write_fragment
# Всегда извлекает entity-фрагменты из step_facts

def run_wiki_lint(model: str = "", cfg: dict | None = None) -> None
# Скомпилировать fragments → pages через LLM-синтез (Variant C)
# Fail-open: concat-fallback если LLM недоступен
# Архивирует обработанные фрагменты в archive/
```

---

## Ограничения и трейдоффы

**Знания из текущего run не видны другим задачам того же run** — осознанный трейдофф ради отсутствия блокировок.

**Галлюцинации в wiki** — агент записывает интерпретацию, не факты. Митигация: LLM-синтез при lint удаляет записи без actionable solution; категорийные промты запрещают vault-специфичные данные.

**Рост контекста** — при большой wiki `errors.md + contacts.md + accounts.md + task_type.md` ≈ много токенов. Попадает в `preserve_prefix` — не компактируется. Будущая митигация: entity-extraction из task\_text для точечной загрузки (Phase 3).

**INDEX.md не реализован** — навигационная страница описана в design docs, но не в текущем коде. Lint работает напрямую по категориям.
