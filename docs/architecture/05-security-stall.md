# 05 — Безопасность и stall-detection

Два взаимосвязанных слоя, защищающих loop: pipeline-защита от prompt-injection и детектор зацикливаний.

## Общая картина защиты

```mermaid
flowchart TB
    Step[Шаг loop] --> Sec[Security pipeline]
    Step --> Stl[Stall detector]

    subgraph Sec[security.py]
        direction TB
        Norm[1. Нормализация<br/>zero-width / NFKC / leet]
        Inj[2. Injection check<br/>regex patterns]
        Contam[3. Contamination<br/>vault paths / tree out]
        Scope[4. Write-scope<br/>email→/outbox/ only]
        Otp[5. OTP elevation<br/>/docs/channels/otp.txt]

        Norm --> Inj --> Contam --> Scope --> Otp
    end

    subgraph Stl[stall.py]
        direction TB
        Loop3[Signal 1<br/>3× same action]
        Err2[Signal 2<br/>2× same path error]
        Expl6[Signal 3a<br/>6+ steps no write]
        Esc12[Signal 3b<br/>12+ steps escalation]

        Loop3 -.-> Hint1[inject hint + retry LLM]
        Err2 -.-> Hint2[inject hint + retry LLM]
        Expl6 -.-> Hint3[inject hint only]
        Esc12 -.-> Hint4[force retry LLM]
    end

    Sec --> Verdict[allow / deny + reason]
    Stl --> Adjust[hint / retry]

    style Sec fill:#ffe1e1
    style Stl fill:#fff4e1
```

## Security: стадия нормализации

```mermaid
flowchart LR
    In[raw text] --> Zw[strip zero-width<br/>U+200B / 200C / 200D<br/>U+2060 / FEFF]
    Zw --> Nfkc[NFKC unicode<br/>homoglyphs → ASCII]
    Nfkc --> Leet[leet substitution<br/>0→o 1→l 3→e<br/>4→a 5→s @→a]
    Leet --> Out[normalized]

    style In fill:#e1f5ff
    style Out fill:#e1ffe1
```

**FIX-203** — без нормализации простые injection-паттерны обходились через `0verride`/`1gnore` и zero-width символы.

## Security: injection pipeline

```mermaid
flowchart TB
    Input[task_text + tool_result text] --> Pre[_run_pre_route]

    Pre --> N1[_normalize_for_injection]
    N1 --> Regex1{_INJECTION_RE match?}
    Regex1 -->|ignore previous<br/>disregard<br/>new task<br/>system prompt<br/>report_completion| Block1[block]

    Regex1 -->|нет| TaskCheck{task_type?}
    TaskCheck -->|inbox/queue| Inbox[_INBOX_INJECTION_PATTERNS<br/>read docs<br/>override rules<br/>admin elevation<br/>credential harvest]
    TaskCheck -->|нет| Allow

    Inbox -->|match| Block2[block]
    Inbox -->|нет| WriteCheck{is write?}

    WriteCheck -->|да| Payload[_check_write_payload_injection<br/>embedded commands<br/>conditional execute<br/>auth-bridge claims]
    Payload -->|match| Block3[block]
    Payload -->|нет| Allow

    WriteCheck -->|нет| Allow[allow]

    Block1 --> Deny[inject: 'denied for security']
    Block2 --> Deny
    Block3 --> Deny
    Allow --> Dispatch[выполнить tool]

    style Deny fill:#ffe1e1
    style Allow fill:#e1ffe1
```

## Security: contamination (email writes)

```mermaid
flowchart TB
    Action[write to /outbox/] --> ExtractBody[extract email body]
    ExtractBody --> Check{содержит?}

    Check -->|/contacts/, /accounts/<br/>vault paths| Block1[block]
    Check -->|tree chars ├ └ ──| Block2[block]
    Check -->|'Result of Req_'| Block3[block]
    Check -->|'AGENTS.MD' refs| Block4[block]
    Check -->|чисто| Allow[allow]

    Block1 --> Reject[OUTCOME_DENIED_SECURITY]
    Block2 --> Reject
    Block3 --> Reject
    Block4 --> Reject

    style Check fill:#e1f5ff
    style Reject fill:#ffe1e1
```

**FIX-206** — агент ранее копировал в email содержимое tree-вывода, выдавая структуру vault.

## Security: write-scope

```mermaid
flowchart TB
    Write[write/delete/move/mkdir] --> L1[Layer 1 — все типы]

    L1 --> Sys{/docs/* или<br/>/AGENTS.MD?}
    Sys -->|да| Except{task=inbox/queue<br/>И path=/docs/channels/otp.txt<br/>И action=delete?}
    Except -->|да| AllowOtp[OTP elevation]
    Except -->|нет| Deny1[deny]
    Sys -->|нет| L2

    L2[Layer 2 — email only] --> Email{task_type=email?}
    Email -->|да| OutboxCheck{path начинается<br/>с /outbox/?}
    OutboxCheck -->|да| Allow[allow]
    OutboxCheck -->|нет| Deny2[deny]
    Email -->|нет| Allow

    Deny1 --> Err[error msg<br/>→ loop]
    Deny2 --> Err
    AllowOtp --> Allow

    style Sys fill:#e1f5ff
    style Deny1 fill:#ffe1e1
    style Deny2 fill:#ffe1e1
    style Allow fill:#e1ffe1
```

**FIX-250** — email-агент мог писать в `/contacts/`, что попадало в CRM систему vault.

## Stall detection: три ортогональных сигнала

```mermaid
flowchart TB
    Step[step N] --> Fp[compute fingerprint<br/>tool:path:args_hash]
    Fp --> DequeUpd[fingerprints.append last 10]
    DequeUpd --> Facts[append _StepFact]

    Facts --> S1{Signal 1:<br/>3 последних fp одинаковы?}
    S1 -->|да| H1[hint: 'same tool 3× — try different']
    H1 --> Retry1[retry LLM once]

    S1 -->|нет| S2{Signal 2:<br/>error_counts<br/>tool,path,code ≥ 2?}
    S2 -->|да| H2[hint: 'path doesn't exist<br/>— list parent']
    H2 --> Retry2[retry LLM once]

    S2 -->|нет| S3a{Signal 3a:<br/>≥ 6 steps<br/>без write/delete/move/mkdir?}
    S3a -->|да| H3[hint: 'take action or<br/>OUTCOME_NONE_CLARIFICATION']
    H3 --> NoRetry[no retry]

    S3a -->|нет| S3b{Signal 3b:<br/>≥ 12 steps без action?}
    S3b -->|да| H4[STALL ESCALATION]
    H4 --> ForceRetry[force retry LLM<br/>FIX-323: re-fire 12/18/24]

    S3b -->|нет| Ok[продолжить шаг]

    Retry1 --> Ok
    Retry2 --> Ok
    NoRetry --> Ok
    ForceRetry --> Ok

    style S1 fill:#e1f5ff
    style S2 fill:#e1f5ff
    style S3a fill:#e1f5ff
    style S3b fill:#fff4e1
```

## Структуры stall-детектора

```mermaid
flowchart LR
    subgraph State[состояние в loop]
        FP[fingerprints<br/>deque max=10]
        EC[error_counts<br/>Counter]
        SF[step_facts<br/>list of _StepFact]
        SW[steps_since_write<br/>int]
    end

    subgraph Fact[_StepFact]
        K[kind: list/read/search/<br/>write/delete/move/mkdir/stall]
        P[path]
        S[summary]
        E[error code]
    end

    Step[каждый шаг] -->|update| State
    Fact -.extract.-> SF
    SF -->|build_digest| Digest[compact summary<br/>для hint context]
```

## Формат fingerprint и error_count

```python
fingerprint = f"{tool}:{path}:{hash(args)}"   # deque
error_key   = (tool, path, error_code)        # Counter
```

- `error_code` — стабилизированный код ошибки из PCM (`NOT_FOUND`, `DENIED`, `INVALID_PATH` и т. д.).
- Одна и та же ошибка на одном пути 2 раза подряд → подсказка "не существует, проверь родителя".

## Поток обработки stall в loop

```mermaid
sequenceDiagram
    participant Loop as run_loop
    participant St as stall._check_stall
    participant Retry as stall._handle_stall_retry
    participant LLM as dispatch

    Loop->>St: (fingerprints, errors, facts, steps_since_write)
    St-->>Loop: hint or None

    alt hint есть + retry_allowed
        Loop->>Retry: (job, log, model, ..., call_llm_fn)
        Retry->>LLM: call_llm_raw(hint appended)
        LLM-->>Retry: new NextStep
        Retry-->>Loop: (new job, stall_active=false, retry_fired=true, tokens)
    else только hint
        Loop->>Loop: append hint в log
        Note over Loop: следующий шаг увидит hint
    end

    Loop->>Loop: продолжить шаг
```

## Outcome-коды, связанные с защитой

| Код | Кем выставляется | Когда |
|---|---|---|
| `OUTCOME_DENIED_SECURITY` | agent / security gates | injection / contamination / scope |
| `OUTCOME_NONE_CLARIFICATION` | agent / stall | exploration stall без прогресса |
| `OUTCOME_NONE_UNSUPPORTED` | agent / classifier | preject |

## Ключевые файлы

| Файл | Функции |
|---|---|
| `agent/security.py` | `_normalize_for_injection`, `_INJECTION_RE`, `_INBOX_INJECTION_PATTERNS`, `_CONTAM_PATTERNS`, `_check_write_scope`, `_check_write_payload_injection` |
| `agent/stall.py` | `_check_stall`, `_handle_stall_retry` |
| `agent/log_compaction.py` | `_StepFact`, `_extract_fact`, `build_digest` (используется stall для hint context) |

## FIX-метки (по CHANGELOG.md)

| FIX | Что исправлено |
|---|---|
| FIX-203 | Нормализация injection-текста (zero-width + NFKC + leet) |
| FIX-206 | Contamination gate на email writes |
| FIX-214 | Формат валидации `From:`/`Channel:` в inbox |
| FIX-215 | Inbox-specific injection-паттерны |
| FIX-250 | Write-scope enforcement (email → только `/outbox/`) |
| FIX-321 | Write-payload injection detection |
| FIX-323 | Re-fire stall escalation на 12/18/24 шагах |

## Тесты

`tests/test_security_gates.py` покрывает:
- `_normalize_for_injection` (zero-width, leet, NFKC).
- `_INJECTION_RE` и `_INBOX_INJECTION_PATTERNS`.
- `_check_write_scope` (email/outbox, system paths, OTP exception).
- Contamination detection на email writes.
