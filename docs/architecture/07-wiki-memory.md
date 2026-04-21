# 07 — Wiki-память

Механизм кросс-сессионной памяти: per-task фрагменты → LLM-lint в страницы → инъекция в preserve_prefix следующих задач.

## Общая схема

```mermaid
flowchart LR
    subgraph Task[задача T]
        Loop[run_loop] --> Wiki1[write_fragment]
    end

    Wiki1 --> FragFS[(data/wiki/<br/>fragments/<br/>category/T.txt)]

    subgraph Lint[run_wiki_lint]
        direction TB
        Scan[scan fragments<br/>by category] --> LLMSyn[LLM synthesis<br/>per-category prompts]
        LLMSyn --> WritePage[write compiled page]
    end

    FragFS --> Lint
    Lint --> PagesFS[(data/wiki/<br/>pages/<br/>category.md)]

    subgraph NextTask[задача T+1]
        Init[agent.run_agent] --> LoadBase[load_wiki_base]
        Init --> LoadPat[load_wiki_patterns]
    end

    PagesFS --> LoadBase
    PagesFS --> LoadPat
    LoadBase --> Inject[inject в preserve_prefix<br/>last user msg]
    LoadPat --> Inject
    Inject --> NextLoop[следующий loop]

    style FragFS fill:#e1f5ff
    style PagesFS fill:#e1ffe1
    style Lint fill:#fff4e1
```

## Директории

```
data/wiki/
├── pages/               # compiled LLM-synth output
│   ├── default.md
│   ├── errors.md
│   ├── contacts.md
│   ├── accounts.md
│   ├── inbox.md
│   ├── queue.md
│   └── crm.md
├── fragments/           # append-only per-task raw writes
│   ├── errors/
│   ├── contacts/
│   ├── inbox/
│   └── ...
└── archive/             # устаревшие/ротированные фрагменты
    ├── accounts/
    └── contacts/
```

## Life-cycle фрагмента

```mermaid
sequenceDiagram
    participant L as run_loop
    participant FMT as format_fragment
    participant WF as write_fragment
    participant Lint as run_wiki_lint
    participant LLM as DispatchLM
    participant PG as pages/

    Note over L: задача выполнена,<br/>outcome известен
    L->>FMT: format_fragment(outcome, task_type, task_id, ops)
    FMT-->>L: list[(content, category)]

    loop для каждого фрагмента
        L->>WF: write_fragment(task_id, category, content)
        WF->>WF: append в fragments/category/T.txt
    end

    Note over L: конец all tasks
    L->>Lint: run_wiki_lint(model, cfg)

    loop для каждой категории
        Lint->>Lint: собрать все fragments
        Lint->>LLM: category-specific synthesis prompt
        LLM-->>Lint: structured page content
        Lint->>PG: write pages/category.md
    end
```

## Когда запускается lint

```mermaid
flowchart LR
    Start[make run] --> LintBefore[run_wiki_lint<br/>first call<br/>компилирует прошлые fragments]
    LintBefore --> Tasks[выполнить задачи]
    Tasks --> LintAfter[run_wiki_lint<br/>second call<br/>компилирует свежие fragments]
    LintAfter --> Submit[submit_run]

    style LintBefore fill:#fff4e1
    style LintAfter fill:#fff4e1
```

Два вызова за запуск:
1. **Перед задачами** — чтобы задачи T+1...T+N видели страницы, собранные из T-1.
2. **После задач** — для следующего запуска.

## Инъекция в prompt

```mermaid
flowchart TB
    Agent[agent.__init__.run_agent] --> LoadBase[load_wiki_base task_text]
    Agent --> LoadPat[load_wiki_patterns task_type]

    LoadBase --> BaseSel[выбор:<br/>errors.md +<br/>contacts.md +<br/>accounts.md]
    LoadPat --> TypeSel[выбор:<br/>&lt;task_type&gt;.md]

    BaseSel --> Combine[combine into<br/>wiki context block]
    TypeSel --> Combine

    Combine --> InjectPre[inject перед task_text<br/>в preserve_prefix]
    InjectPre --> Loop[run_loop сохранит<br/>через compaction]

    style BaseSel fill:#e1f5ff
    style TypeSel fill:#e1f5ff
    style InjectPre fill:#e1ffe1
```

**Ключевое**: блок wiki помещён в `preserve_prefix`, то есть никогда не компактизуется (см. [09](09-observability.md)).

## Per-category synthesis prompts

```mermaid
flowchart LR
    subgraph errors[errors]
        EP[prompt:<br/>extract concrete<br/>error patterns:<br/>name, condition,<br/>root cause, solution]
    end

    subgraph contacts[contacts / accounts]
        CP[prompt:<br/>extract proven sequences<br/>+ risks + insights;<br/>НЕ добавлять<br/>individual entries]
    end

    subgraph inbox[inbox / queue]
        IP[prompt:<br/>extract patterns<br/>+ steps;<br/>НЕ включать<br/>vault-specific data<br/>handles, tokens]
    end

    Frags[fragments/*] --> errors
    Frags --> contacts
    Frags --> inbox

    errors --> EpOut[pages/errors.md]
    contacts --> CpOut[pages/contacts.md<br/>pages/accounts.md]
    inbox --> IpOut[pages/inbox.md<br/>pages/queue.md]
```

**Правила синтеза**:
- Категории `contacts`/`accounts`: не содержат individual records (фрагменты могут, страницы — нет).
- Категории `inbox`/`queue`: не содержат vault-specific handles, channel names, tokens (во избежание leak в другие задачи).
- Категория `errors`: наоборот, максимально конкретные условия и решения.

## Classifier-hints из wiki

```mermaid
flowchart LR
    Classifier[classifier.classify_task_llm] --> LoadPat[load_wiki_patterns]
    LoadPat --> PagesRead[read pages/&lt;type&gt;.md]
    PagesRead --> VaultHint[добавить в vault_hint]
    VaultHint --> LLMCall[LLM классификация]

    style LoadPat fill:#fff4e1
```

Wiki-страницы подгружаются в `vault_hint` для classifier → снижает flip-ы между `inbox` и `queue`.

## Fail-open по всей цепочке

```mermaid
flowchart TB
    Write[write_fragment] --> TryW{file write ok?}
    TryW -->|yes| Ok1[continue]
    TryW -->|no| Log1[log, continue]

    Read[load_wiki_*] --> TryR{file exists?}
    TryR -->|yes| Content[return content]
    TryR -->|no| Empty[return '']

    Lint[run_wiki_lint] --> TryL{LLM ok?}
    TryL -->|yes| Write1[write page]
    TryL -->|no| Skip[skip category]

    style Log1 fill:#ffe1e1
    style Empty fill:#ffe1e1
    style Skip fill:#ffe1e1
```

Wiki-подсистема — опциональная: любой сбой переходит к baseline-поведению без inject.

## Конфигурация

```bash
WIKI_ENABLED=1          # инъекция wiki в prompts
WIKI_LINT_ENABLED=1     # компиляция фрагментов в страницы
```

## Ключевые файлы

| Файл | Что делает |
|---|---|
| `agent/wiki.py` | `load_wiki_base`, `load_wiki_patterns`, `format_fragment`, `write_fragment`, `run_wiki_lint` |
| `data/wiki/pages/` | Компилированные страницы (injected) |
| `data/wiki/fragments/` | Сырые фрагменты per-task |
| `data/wiki/archive/` | Ротированные фрагменты |

## Архитектурное решение

**Вариант C — LLM-синтез** выбран вместо двух альтернатив:
- **A**: Хранить каждый fragment как-есть. Минус: с ростом fragments контекст раздувается.
- **B**: Runtime-дедупликация фрагментов по хэшу. Минус: семантически близкие фрагменты остаются.
- **C** (выбрано): LLM синтезирует структурированные страницы из всех фрагментов категории. Плюс: компактно и структурировано. Минус: стоит LLM-вызова на `run_wiki_lint`.
