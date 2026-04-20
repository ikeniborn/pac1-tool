# Execution Flow: Полный путь выполнения задачи

Описывает поток управления от `main.py` до финального `vm.answer()`, включая все фазы, хуки и ветки принятия решений.

---

## Верхний уровень: main.py → run_agent()

```mermaid
flowchart TD
    ENV["Переменные окружения\n.secrets / .env"] --> MAIN

    MAIN["main.py:main()"] --> ROUTER["ModelRouter\nиз models.json + env"]
    MAIN --> BENCH["harness.get_benchmark()\n→ trial_ids"]
    MAIN --> RUNID["harness.start_run()"]

    RUNID --> LINT1["wiki_lint() #1\n(если WIKI_LINT_ENABLED)"]
    LINT1 --> POOL["ThreadPoolExecutor\n(PARALLEL_TASKS потоков)"]

    POOL --> TRIAL["_run_single_task(trial_id)"]
    TRIAL --> HCLIENT["HarnessServiceClientSync\nstart_trial() → harness_url + instruction"]
    HCLIENT --> AGENT["run_agent(router, harness_url, task_text)"]
    AGENT --> RESULT["EndTrial → score"]
    RESULT --> TABLE["Строка в таблице результатов"]

    POOL --> LINT2["wiki_lint() #2\n(после ThreadPool)"]
    LINT2 --> SUBMIT["harness.submit_run()"]
    SUBMIT --> SUMMARY["_write_summary() → итоговая таблица"]
```

---

## run_agent(): сборка контекста перед циклом

```mermaid
flowchart TD
    A["run_agent(router, harness_url, task_text)"] --> VM["PcmRuntimeClientSync\n@ harness_url"]

    VM --> PREJECT{"task_type == preject?\n(быстрый regex)"}
    PREJECT -->|да| DENY["vm.answer(OUTCOME_NONE_UNSUPPORTED)\nReturn немедленно"]
    PREJECT -->|нет| PRE

    PRE["run_prephase(vm, task_text)"] --> TREE["PCM: tree -L 2 /\n→ vault layout"]
    TREE --> AGMD["PCM: read AGENTS.MD\n(root + first-level dirs)"]
    AGMD --> PRELOAD["PCM: list + read\nдиректорий из AGENTS.MD\n(кроме data-dirs)"]
    PRELOAD --> CTX["PCM: context()\n→ task metadata, current date"]
    CTX --> VDATE["Инференс VAULT_DATE\nиз date-prefixed файлов\n→ accounts/*.json fallback"]
    VDATE --> PRERES["PrephaseResult\n(log, preserve_prefix,\nagents_md, vault_tree,\ninbox_files)"]

    PRERES --> CLASSIFY["router.resolve_after_prephase()\nclassify_task_llm() с AGENTS.MD\n→ (model_id, cfg, task_type)"]

    CLASSIFY --> WIKI_BASE["load_wiki_base()\nerrors + contacts + accounts"]
    WIKI_BASE --> WIKI_PAT["load_wiki_patterns(task_type)"]
    WIKI_PAT --> SYS["build_system_prompt(task_type)\n→ task-specific блоки"]

    SYS --> PB{"PROMPT_BUILDER\n_ENABLED?"}
    PB -->|да| ADD["build_dynamic_addendum(\ntask_text, task_type,\nagents_md, vault_tree)\n→ 3–6 bullets"]
    PB -->|нет| LOOP
    ADD --> LOOP

    LOOP["run_loop(vm, model, task_text,\npre, cfg, task_type)"] --> STATS["stats dict\n(tokens, steps, outcome,\nstep_facts, done_ops)"]
    STATS --> WF["_write_wiki_fragment(\ntask_type, outcome, stats)"]
    WF --> RET["Return stats"]
```

---

## run_loop(): детальный шаг выполнения

```mermaid
flowchart TD
    START["run_loop()"] --> PREROUTE["_run_pre_route()\ninject detect + semantic routing"]

    PREROUTE --> RR{"route?"}
    RR -->|DENY_SECURITY| EARLY1["vm.answer(OUTCOME_DENIED_SECURITY)\nReturn"]
    RR -->|CLARIFY| EARLY2["vm.answer(OUTCOME_NONE_CLARIFICATION)\nReturn"]
    RR -->|UNSUPPORTED| EARLY3["vm.answer(OUTCOME_NONE_UNSUPPORTED)\nReturn"]
    RR -->|EXECUTE| STEPLOOP

    STEPLOOP["for i in range(30)"] --> STEP["_run_step(i, ...)"]
    STEP --> DONE{"task complete\nили fatal error?"}
    DONE -->|да| END["Return _st_to_result()"]
    DONE -->|нет| STEPLOOP
```

### _run_step(): внутренний цикл шага

```mermaid
flowchart TD
    STEP["_run_step(i)"] --> TIMEOUT{"Превышен\nTASK_TIMEOUT_S?"}
    TIMEOUT -->|да| TOUT["Return True (fatal)"]
    TIMEOUT -->|нет| COMPACT

    COMPACT["_compact_log()\nесли log > порог"] --> LLM["_call_llm(log, model, max_tokens, cfg)\n→ NextStep | None"]

    LLM --> PARSE{"NextStep\nуспешно?"}
    PARSE -->|None / ошибка| RETRY["_handle_stall_retry()\nstall detection + hint"]
    RETRY --> NEXT["Continue (следующий шаг)"]
    PARSE -->|ok| PRE_D

    PRE_D["_pre_dispatch(job, task_type)"] --> GUARD{"Guard\nсработал?"}
    GUARD -->|error msg| INJECT["Инжектировать error\nв log как user msg\nContinue"]
    GUARD -->|ok| GROUNDING

    GROUNDING["Auto-populate\ngrounding_refs\n(FIX-232)"] --> FGATE{"format-gate\nили security\ninterceptor?"}
    FGATE -->|fired| OVERRIDE["Подменить job на\nreport_completion\nc security outcome"]
    FGATE -->|ok| DUAL

    DUAL["Dual-write check\n(FIX-255)"] --> EVAL_G{"EVALUATOR_ENABLED\n+ task_completed?"}

    EVAL_G -->|да| EVAL["evaluate_completion(\ntask_text, task_type,\nreport, done_ops, digest)"]
    EVAL --> EV_RES{"EvalVerdict\napproved?"}
    EV_RES -->|rejected < MAX_EVAL| HINT["Инжектировать\ncorrection_hint\nContinue"]
    EV_RES -->|rejected >= MAX| FORCE["Force submit\nignore evaluator"]
    EV_RES -->|approved| DISPATCH_CALL
    EVAL_G -->|нет| DISPATCH_CALL

    DISPATCH_CALL["dispatch(vm, job.function)\n→ result_txt"] --> POST

    POST["_post_dispatch(job, txt, task_type)"] --> FACTS["_extract_fact()\n→ step_facts.append()"]
    FACTS --> STALL_UPD["Обновить fingerprints,\nsteps_since_write,\nerror_counts"]
    STALL_UPD --> TASK_C{"task_completed?"}
    TASK_C -->|да| RET["Return True"]
    TASK_C -->|нет| RET2["Return False"]
```

---

## _pre_dispatch(): защитные проверки (в порядке приоритета)

```mermaid
flowchart TD
    PD["_pre_dispatch(job, task_type)"] --> W1{"Wildcard delete?\n/folder/*"}
    W1 -->|да| E1["ERROR: wildcard reject"]

    W1 -->|нет| W2{"Scope-restricted\ndelete? (FIX-267)"}
    W2 -->|да| E2["ERROR: scope restrict"]

    W2 -->|нет| W3{"Format-gate fired\n+ write/delete?"}
    W3 -->|да| E3["ERROR: format gate block"]

    W3 -->|нет| W4{"Cross-account entity\nmismatch? (inbox)"}
    W4 -->|да| E4["ERROR: cross-account"]

    W4 -->|нет| W5{"Delete-only task\n+ write op?"}
    W5 -->|да| E5["ERROR: write blocked"]

    W5 -->|нет| W6{"Reschedule pre-check\nfails?"}
    W6 -->|да| E6["ERROR: reschedule guard"]

    W6 -->|нет| W7{"Lookup task\n+ mutation?"}
    W7 -->|да| E7["ERROR: lookup read-only"]

    W7 -->|нет| W8{"Write-scope\nviolation?\n(security.py)"}
    W8 -->|да| E8["ERROR: write scope"]

    W8 -->|нет| W9{"Empty path?"}
    W9 -->|да| E9["ERROR: empty path"]

    W9 -->|нет| PREP["Подготовка:\n• Auto-list parent\n• Track listed_dirs\n• JSON auto-sanitize (FIX-268)\n• Pre-write snapshot (FIX-251)\n• Pre-write date validate"]
    PREP --> OK["Return None (ok)"]

    E1 & E2 & E3 & E4 & E5 & E6 & E7 & E8 & E9 --> ERR["Return error_msg"]
```

---

## _post_dispatch(): хуки после успешного tool call

```mermaid
flowchart TD
    PO["_post_dispatch(job, txt, task_type)"]

    PO --> P1["Post-search expansion\n(FIX-129): пустой search\ncontact → retry с ≤2 вариантами"]
    P1 --> P2["JSON field verify\n_verify_json_write()\n(после write)"]
    P2 --> P3["Outbox seq.json\nавто-управление (FIX-260)"]
    P3 --> P4["Cross-account hint\n(FIX-252/263)"]
    P4 --> P5["OTP delete reminder"]
    P5 --> P6["Inbox filename\ninjection check"]
    P6 --> P7["Inbox content\ninjection scan (FIX-215)"]
    P7 --> P8["Channel trust\ndetection (FIX-284)"]
    P8 --> P9["Contact verification\n(FIX-237/246)"]
    P9 --> P10["Company/account\nverification (FIX-240)"]
    P10 --> P11["Invoice cross-account\ncheck"]
    P11 --> P12["Reschedule date\nverification (FIX-226)"]
    P12 --> P13["Distill card/thread\nreminder"]
```

---

## _run_pre_route(): семантическая маршрутизация до цикла

```mermaid
sequenceDiagram
    participant LOOP as run_loop
    participant PREROUTE as _run_pre_route
    participant CACHE as _ROUTE_CACHE
    participant LLM as _call_llm (router)
    participant SEC as security.py

    LOOP->>PREROUTE: task_text, pre, model

    PREROUTE->>SEC: _normalize_for_injection(task_text)
    SEC-->>PREROUTE: normalized_text

    PREROUTE->>SEC: _INBOX_INJECTION_PATTERNS match?
    alt инъекция найдена (prephase inbox)
        PREROUTE-->>LOOP: return True (DENY)
    end

    PREROUTE->>CACHE: sha256(task_text[:800])
    alt cache hit
        CACHE-->>PREROUTE: cached TaskRoute
    else cache miss
        PREROUTE->>LLM: TaskRoute schema\n(injection_signals, route, reason)
        LLM-->>PREROUTE: TaskRoute | None
        alt None / retry failed
            PREROUTE->>PREROUTE: _ROUTER_FALLBACK (EXECUTE/CLARIFY)
        end
        PREROUTE->>CACHE: store result
    end

    alt route == DENY_SECURITY
        PREROUTE-->>LOOP: True (early exit)
    else route == CLARIFY / UNSUPPORTED
        PREROUTE-->>LOOP: True (early exit)
    else route == EXECUTE
        PREROUTE-->>LOOP: False (продолжить цикл)
    end
```

---

## Сжатие лога (_compact_log)

```mermaid
flowchart LR
    LOG["Текущий log\n[system, few-shot,\nprephase ctx,\n...шаги...]"] --> CHECK{"len > порог?"}
    CHECK -->|нет| PASSTHRU["log без изменений"]
    CHECK -->|да| COMPACT

    COMPACT["_compact_log(\nmax_tool_pairs=7,\npreserve_prefix,\nstep_facts)"] --> KEEP["Сохранить:\n• preserve_prefix (system+few-shot)\n• последние 7×2 сообщений"]

    KEEP --> DIGEST["build_digest(step_facts)\n→ LISTED / READ / FOUND\n/ DONE / ERRORS / STALLS"]
    DIGEST --> SUMMARY["Сообщение role:user\n'Previous steps summary: ...'"]
    SUMMARY --> OUT["Сжатый log\n(prefix + summary + recent)"]
```

---

## Обнаружение зависания (stall.py)

```mermaid
flowchart TD
    STALL["_check_stall(\nfingerprints, steps_since_write,\nerror_counts, step_facts)"] --> S1{"Последние 3\nfingerprint одинаковы?"}
    S1 -->|да| H1["HINT: action loop\n+ контекст из step_facts\nПредложить: другой инструмент"]

    S1 -->|нет| S2{"(tool, path, code)\nError ≥ 2 раз?"}
    S2 -->|да| H2["HINT: path error\nПредложить: list parent dir"]

    S2 -->|нет| S3{"steps_since_write ≥ 6?"}
    S3 -->|нет| OK["Return None (нет зависания)"]
    S3 -->|да: 6–11 шагов| H3["HINT: exploration stall\n(мягкий)"]
    S3 -->|да: ≥12 шагов| H4["STALL ESCALATION\n(заглавными, жёсткий)"]

    H1 & H2 & H3 & H4 --> INJECT["Инжектировать hint\nв log как user msg\n_StepFact(kind=stall)\nПовторный LLM-вызов"]
```

---

## Evaluator gate: условия вызова и bypass

```mermaid
flowchart TD
    EG{"EVALUATOR_ENABLED\n+ job.task_completed?"} -->|нет| SKIP["Пропустить evaluator\n→ dispatch()"]

    EG -->|да| BYPASS{"Bypass\nусловия?"}

    BYPASS -->|security_interceptor_fired| B1["Bypass: security"]
    BYPASS -->|format_gate_fired| B2["Bypass: format gate"]
    BYPASS -->|task_type == lookup| B3["Bypass: read-only"]
    BYPASS -->|reschedule task| B4["Bypass: reschedule"]
    BYPASS -->|admin message| B5["Bypass: admin"]
    BYPASS -->|email task| B6["Bypass: email"]
    BYPASS -->|OTP task| B7["Bypass: OTP"]
    BYPASS -->|contact not found| B8["Bypass: not found"]

    B1 & B2 & B3 & B4 & B5 & B6 & B7 & B8 --> SKIP

    BYPASS -->|нет bypass| CALL["evaluate_completion(\ntask_text, task_type,\nreport, done_ops,\ndigest_str, model, cfg,\nskepticism, efficiency)"]

    CALL --> VER{"EvalVerdict\napproved?"}
    VER -->|True| DISPATCH["→ dispatch() (submit)"]
    VER -->|False\nrejections < MAX_EVAL_REJECTIONS| HINT["correction_hint\n→ log\nContinue цикл"]
    VER -->|False\nrejections >= MAX| FORCE["Force dispatch\n(игнорировать evaluator)"]
```

---

## Итоговая схема: полный путь одной задачи

```mermaid
sequenceDiagram
    participant H as Harness
    participant M as main.py
    participant A as run_agent
    participant PRE as prephase
    participant CLS as classifier
    participant W as wiki
    participant PB as prompt_builder
    participant LR as _run_pre_route
    participant STEP as _run_step ×N
    participant EVAL as evaluator
    participant PCM as PcmRuntime

    H->>M: instruction + harness_url
    M->>A: run_agent()
    A->>PRE: tree / AGENTS.MD / docs / context / VAULT_DATE
    PRE->>PCM: 4–8 tool calls
    PCM-->>PRE: vault context
    PRE-->>A: PrephaseResult

    A->>CLS: classify_task_llm(task_text, pre)
    CLS-->>A: (model, cfg, task_type)

    A->>W: load_wiki_base() + load_wiki_patterns()
    W-->>A: wiki pages (или "" если пусто)

    A->>PB: build_dynamic_addendum()
    PB-->>A: 3–6 bullets (или "" если disabled)

    A->>LR: _run_pre_route()
    LR->>PCM: (нет tool calls — только LLM)
    LR-->>A: EXECUTE / early exit

    loop До 30 шагов
        STEP->>STEP: _call_llm → NextStep JSON
        STEP->>STEP: _pre_dispatch guards
        STEP->>PCM: tool call
        PCM-->>STEP: result
        STEP->>STEP: _post_dispatch hooks
        opt task_completed + evaluator enabled
            STEP->>EVAL: evaluate_completion()
            EVAL-->>STEP: approved / correction_hint
        end
    end

    STEP->>PCM: report_completion(outcome, message, refs)
    PCM-->>STEP: (acknowledged)
    A->>W: write_fragment(task_type, outcome, step_facts)
    A-->>M: stats dict
    M->>H: EndTrial (score)
```
