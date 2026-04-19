# Wiki-Memory: Mermaid-схемы

## 1. Общий flow: чтение и запись wiki в рамках одной задачи

```mermaid
flowchart TD
    START([make run]) --> LINT[wiki_lint\nfragments/ → pages/]
    LINT --> POOL[ThreadPoolExecutor]

    POOL --> PRE[run_prephase]
    PRE --> A[Этап A\nload pages/errors.md\n+ entities по task_text]
    A --> CLASSIFY[classifier → task_type]
    CLASSIFY --> B[Этап B\nload pages/task_type.md]
    B --> BUILDER[build_dynamic_addendum\nwiki_context=patterns]
    BUILDER --> LOOP[run_loop ≤30 шагов]

    LOOP --> OUTCOME{outcome}

    OUTCOME -->|OUTCOME_OK\n+ evaluator approved| WS[write_fragment\ncategory: task_type\n+ entities]
    OUTCOME -->|OUTCOME_OK\n+ evaluator rejected| WE1[write_fragment\ncategory: errors\neval issues + hint]
    OUTCOME -->|OUTCOME_DENIED_SECURITY| WE2[write_fragment\ncategory: errors\ninjection pattern]
    OUTCOME -->|OUTCOME_NONE_CLARIFICATION| WE3[write_fragment\ncategory: errors\nambiguity description]
    OUTCOME -->|Stall / timeout| WE4[write_fragment\ncategory: errors\nstall path + attempts]

    WS --> FRAG[(data/wiki/fragments/)]
    WE1 --> FRAG
    WE2 --> FRAG
    WE3 --> FRAG
    WE4 --> FRAG
```

---

## 2. Жизненный цикл fragments → pages (два прогона)

```mermaid
sequenceDiagram
    participant MR as make run #1
    participant LINT as wiki_lint
    participant FRAG as fragments/
    participant PAGES as pages/
    participant MR2 as make run #2

    MR->>LINT: старт до ThreadPool
    LINT->>FRAG: проверяет — пусто
    LINT->>PAGES: pages/ пусто (первый запуск)

    Note over MR: Параллельные задачи
    MR->>FRAG: t001 OUTCOME_OK → email/t001_…md
    MR->>FRAG: t002 eval rejected → errors/t002_…md

    MR2->>LINT: старт до ThreadPool
    LINT->>FRAG: читает все фрагменты
    LINT->>LINT: llm_merge (дедупликация\nразрешение противоречий)
    LINT->>PAGES: pages/email.md ← workflow t001
    LINT->>PAGES: pages/errors.md ← ошибка t002
    LINT->>FRAG: архивирует обработанные

    Note over MR2: Параллельные задачи
    MR2->>PAGES: t003 prephase читает email.md ✓
    MR2->>PAGES: t004 prephase читает errors.md ✓
    MR2->>FRAG: t003, t004 → новые фрагменты
```

---

## 3. Двухэтапная загрузка wiki в prephase

```mermaid
flowchart LR
    TEXT[task_text] --> A

    subgraph PREPHASE [run_prephase]
        A[Этап A\nдо classify] -->|email-адреса и имена\nиз task_text| A1[pages/errors.md]
        A --> A2[pages/entities.md\n+ entity-страницы]
        A1 --> PREFIX[preserve_prefix]
        A2 --> PREFIX
    end

    PREFIX --> CLASSIFY[classifier\n→ task_type]

    subgraph AFTER_CLASSIFY [после classify]
        CLASSIFY --> B[Этап B] -->|task_type| B1[pages/task_type.md]
        B1 --> PREFIX2[дополняет\npreserve_prefix]
    end

    PREFIX2 --> BUILDER[build_dynamic_addendum\nwiki_context=patterns]
    BUILDER --> LOOP[run_loop\nагент видит wiki\nс первого шага]
```

---

## 4. Петля обратной связи: wiki ↔ DSPy

```mermaid
flowchart TD
    TASK[Задача N] --> LOOP[run_loop]
    LOOP --> EVAL[evaluator]

    EVAL -->|approved\nstep_facts| WP[wiki/fragments\ntask_type.md]
    EVAL -->|rejected\nissues + hint| WE[wiki/fragments\nerrors.md]

    WP --> LINT2[wiki_lint]
    WE --> LINT2
    LINT2 --> PAGES[pages/]

    PAGES --> PRE2[prephase\nЗадача N+1]
    PRE2 --> BUILDER2[prompt_builder\nwiki_context=patterns]
    BUILDER2 --> LOOP2[run_loop\nлучший результат]
    LOOP2 --> EX[dspy_examples.jsonl\nс wiki_context]

    EX --> COPRO[optimize_prompts.py\nCOPRO offline]
    COPRO --> PROG[compiled program\nучится использовать wiki]
    PROG --> BUILDER2
```

---

## 5. Роль evaluator как гейткипера wiki

```mermaid
flowchart TD
    LOOP[run_loop завершается] --> RC[report_completion]
    RC --> EV{evaluator}

    EV -->|approved| WUP[wiki_update_phase\nмикро-цикл ≤5 шагов]
    EV -->|rejected| ERR[программная запись\nв errors.md\nбез LLM-вызова]

    WUP --> AGT[агент генерирует\nпредложение обновления]
    AGT --> EVWIKI{evaluator\nevaluate_wiki_update}
    EVWIKI -->|approved| WRITE[write_fragment\ncategory: task_type\n+ entities]
    EVWIKI -->|rejected| SKIP[skip\nне засоряем wiki\nгаллюцинациями]

    ERR --> EFRAG[write_fragment\ncategory: errors\nstruct template]

    WRITE --> FRAG[(fragments/)]
    EFRAG --> FRAG
```

---

## 6. Физическое расположение данных и потоки чтения/записи

```mermaid
graph LR
    subgraph DISK [Локальный диск]
        subgraph WIKI [data/wiki/]
            PAGES[pages/\nerrors.md\nemail.md\ncrm.md\nentities.md\n…]
            FRAGS[fragments/\nerrors/\nemail/\nentities/\n…]
            ARCH[archive/]
        end
        DSPY[data/\nprompt_builder_program.json\nevaluator_program.json]
    end

    subgraph VAULT [Harness Vault per-trial]
        VF[/contacts/\n/inbox/\n/outbox/\n…]
    end

    PAGES -->|read_text до prephase\nбез vault-инструментов| PRE[prephase.py]
    PRE --> LOOP[run_loop]
    LOOP --> VF
    VF --> LOOP
    LOOP -->|write_text после run_loop\nновый файл на задачу| FRAGS
    FRAGS -->|llm_merge\nначало make run| PAGES
    FRAGS -->|архив| ARCH
```
