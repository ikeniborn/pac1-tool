# Wiki-Memory: Mermaid-схемы

---

## 1. Полный flow: чтение и запись wiki за одну задачу

```mermaid
flowchart TD
    START([make run]) --> LINT1[wiki_lint\nфрагменты прошлых запусков\n→ pages/]
    LINT1 --> POOL[ThreadPoolExecutor]

    POOL --> PRE[run_prephase\nvault tree + AGENTS.MD]
    PRE --> CLS[classifier\n→ task_type]
    CLS --> WA[load_wiki_base\nerrors + contacts + accounts]
    WA --> WB[load_wiki_patterns\npages/task_type.md]
    WB --> LOOP[run_loop ≤30 шагов]

    LOOP --> OUTCOME{outcome}

    OUTCOME -->|OUTCOME_OK| FF1[format_fragment\ncategory: task_type]
    OUTCOME -->|OUTCOME_DENIED_SECURITY| FF2[format_fragment\ncategory: errors]
    OUTCOME -->|OUTCOME_NONE_CLARIFICATION| FF3[format_fragment\ncategory: errors]
    OUTCOME -->|Stall hints присутствуют| FF4[format_fragment\ncategory: errors]

    FF1 --> EF[+ entity fragments\ncontacts + accounts\nиз step_facts]
    FF2 --> EF
    FF3 --> EF
    FF4 --> EF

    EF --> WF[write_fragment\nappend-only\n{task_id}_{ts}.md]
    WF --> FRAG[(data/wiki/fragments/)]

    POOL -->|после всех задач| LINT2[wiki_lint\nфрагменты этого запуска\n→ pages/]
    LINT2 --> ARCH[архив обработанных\nfragments → archive/]
```

---

## 2. Жизненный цикл fragments → pages (два прогона)

```mermaid
sequenceDiagram
    participant R1 as make run #1
    participant LINT as wiki_lint
    participant FRAG as fragments/
    participant PAGES as pages/
    participant R2 as make run #2

    R1->>LINT: до ThreadPool
    LINT->>FRAG: проверяет — пусто
    note over LINT: ничего не делает

    note over R1: Параллельные задачи
    R1->>FRAG: t001 OUTCOME_OK → email/t001_…md<br/>contacts/t001_…md
    R1->>FRAG: t002 CLARIFICATION → errors/t002_…md

    R1->>LINT: после ThreadPool
    LINT->>FRAG: читает все фрагменты
    LINT->>LINT: LLM synthesis (Variant C)<br/>по категорийным промтам
    LINT->>PAGES: pages/email.md ← workflow t001
    LINT->>PAGES: pages/errors.md ← ловушка t002
    LINT->>PAGES: pages/contacts.md ← entity facts t001
    LINT->>FRAG: перемещает в archive/

    R2->>LINT: до ThreadPool
    LINT->>FRAG: проверяет — пусто
    note over LINT: ничего не делает

    note over R2: Параллельные задачи
    R2->>PAGES: t003 prephase: load_wiki_base() → errors + contacts ✓
    R2->>PAGES: t003: load_wiki_patterns("email") → email.md ✓
    R2->>FRAG: t003, t004 → новые фрагменты

    R2->>LINT: после ThreadPool
    LINT->>LINT: merge existing + new fragments
    LINT->>PAGES: обновлённые страницы (накопление)
```

---

## 3. Двухэтапная загрузка wiki в run_agent()

```mermaid
flowchart LR
    TEXT[task_text] --> PRE

    subgraph PRE [run_prephase]
        direction TB
        P1[vault tree\nAGENTS.MD\ndocs/ preload]
    end

    PRE --> CLS[classifier\n→ task_type]

    subgraph INJECT [run_agent после classify]
        direction TB
        A[load_wiki_base\nerrors.md\ncontacts.md\naccounts.md] --> LOG[pre.log\nappend]
        B[load_wiki_patterns\npages/task_type.md] --> LOG
    end

    CLS --> INJECT

    LOG --> LOOP[run_loop\nагент видит wiki\nс первого шага\nне компактируется]
```

---

## 4. LLM-синтез (Variant C): категорийные промты

```mermaid
flowchart TD
    FRAG[(fragments/\ncategory/)] --> LINT[_llm_synthesize]
    EXISTING[pages/category.md\nexisting] --> LINT

    LINT --> CAT{category}

    CAT -->|errors| PE["Промт: errors\nИзвлечь: name / condition\n/ root cause / solution\nУдалить: без actionable solution"]
    CAT -->|contacts| PC["Промт: contacts\nИзвлечь: workflow, risks, insights\nЗапрет: индивидуальные записи\n## john@... ## cont_NNN"]
    CAT -->|accounts| PA["Промт: accounts\nИзвлечь: workflow, risks, insights\nЗапрет: индивидуальные записи\n## acct_NNN ## CompanyName"]
    CAT -->|queue / inbox| PQ["Промт: queue/inbox\nИзвлечь: workflow, patterns\nЗапрет: vault-специфика\n(handles, usernames, OTP tokens)"]
    CAT -->|остальные| PP["Промт: _pattern_default\nИзвлечь: workflow, risks, insights"]

    PE --> LLM[call_llm_raw\nplain_text=True\nmax_tokens=4000]
    PC --> LLM
    PA --> LLM
    PQ --> LLM
    PP --> LLM

    LLM -->|ok len > 50| OUT[pages/category.md]
    LLM -->|fail| CONCAT[_concat_merge\nfallback: конкатенация]
    CONCAT --> Out2[pages/category.md]
```

---

## 5. Параллельность: append-only fragments

```mermaid
sequenceDiagram
    participant T1 as Поток 1 (t041)
    participant T2 as Поток 2 (t042)
    participant FRAG as fragments/email/

    note over T1,T2: Параллельное выполнение

    T1->>FRAG: write email/t041_20260420T100000Z.md
    T2->>FRAG: write email/t042_20260420T100030Z.md

    note over FRAG: Два разных файла<br/>Нет read-modify-write<br/>Нет гонок
```

```mermaid
flowchart LR
    subgraph BAD["❌ Без fragments (race condition)"]
        direction TB
        R1A[T1: read email.md] --> W1A[T1: write email.md]
        R1B[T2: read email.md] --> W1B[T2: write email.md]
        W1A -. "перезаписывает" .-> W1B
    end

    subgraph GOOD["✓ С fragments (thread-safe)"]
        direction TB
        F1[T1: write t041_{ts}.md]
        F2[T2: write t042_{ts}.md]
        F1 --- LINT2[Lint (однопоточно)\nобъединяет оба]
        F2 --- LINT2
        LINT2 --> PAGE[pages/email.md]
    end
```

---

## 6. Петля обратной связи: wiki ↔ evaluator ↔ DSPy

```mermaid
flowchart TD
    TASK[Задача N] --> LOOP[run_loop]
    LOOP --> EVAL[evaluator]

    EVAL -->|approved: true\nstep_facts| FF_OK[format_fragment\ncategory: task_type]
    EVAL -->|approved: false\nissues + hint| FF_ERR[format_fragment\ncategory: errors]

    FF_OK --> FRAG[(fragments/)]
    FF_ERR --> FRAG

    FRAG --> LINT[wiki_lint\n→ pages/]
    LINT --> PAGES[(pages/)]

    PAGES --> PRE2[prephase\nЗадача N+1\nload_wiki_base + load_wiki_patterns]
    PRE2 --> LOOP2[run_loop\nлучший результат]
    LOOP2 --> EX[dspy_examples.jsonl\nновый пример]

    EX --> COPRO[optimize_prompts.py\nCOPRO offline]
    COPRO --> PROG[compiled program\nулучшается]
    PROG --> PB[prompt_builder\nbuild_dynamic_addendum]
    PB --> LOOP2
```

---

## 7. Физическое расположение: диск vs vault

```mermaid
graph LR
    subgraph DISK["Локальный диск (персистентен между runs)"]
        subgraph WIKI["data/wiki/"]
            PAGES["pages/\nerrors.md\nemail.md\ncontacts.md\naccounts.md\n…"]
            FRAGS["fragments/\nerrors/…\nemail/…\ncontacts/…\n…"]
            ARCH["archive/"]
        end
    end

    subgraph VAULT["Harness Vault (изолирован per-trial)"]
        VF["/contacts/\n/accounts/\n/inbox/\n/outbox/\nAGENTS.MD"]
    end

    PAGES -->|"read_text()\nбез vault-инструментов"| PREPHASE[prephase.py\nrun_agent()]
    PREPHASE --> RUNLOOP[run_loop]
    RUNLOOP <-->|"PCM tool calls\n(read/write/delete/…)"| VF
    RUNLOOP -->|"write_text()\nновый файл на задачу"| FRAGS
    FRAGS -->|"llm_merge\nLint дважды за run"| PAGES
    FRAGS -->|"архив после lint"| ARCH
```
