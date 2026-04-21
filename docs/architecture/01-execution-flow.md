# 01 — Поток выполнения

Конвейер от `make run` до вызова `vm.answer()`: точка входа, prephase, главный loop и lifecycle одного шага.

## От harness до завершения задачи

```mermaid
sequenceDiagram
    autonumber
    participant U as make run
    participant M as main.py
    participant H as BitGN Harness
    participant A as agent.run_agent
    participant VM as PCM Runtime
    participant LLM as dispatch LLM

    U->>M: запуск CLI
    M->>M: load .env / .secrets / models.json
    M->>H: GetBenchmark(id)
    H-->>M: список задач
    M->>H: StartRun(name, api_key)
    H-->>M: run_id

    loop ThreadPoolExecutor (PARALLEL_TASKS)
        M->>H: StartTrial(trial_id)
        H-->>M: task_text, harness_url
        M->>A: run_agent(router, harness_url, task_text)
        A->>VM: tree / read(AGENTS.MD) / context
        A->>A: classify + build prompt + dspy addendum

        loop ≤30 steps
            A->>LLM: dispatch(log, model, cfg)
            LLM-->>A: NextStep(JSON)
            A->>A: stall / security / evaluator
            A->>VM: PCM tool call
            VM-->>A: result
        end

        A->>VM: vm.answer(outcome, message, refs)
        A-->>M: token stats
        M->>H: EndTrial(trial_id)
        H-->>M: score + detail
    end

    M->>H: SubmitRun(run_id, force=true)
```

## Оркестрация в main.py

```mermaid
flowchart TB
    Start([main]) --> LoadEnv[Load env:<br/>.env, .secrets, models.json]
    LoadEnv --> Tee[_setup_log_tee<br/>logs/&lt;ts&gt;_&lt;model&gt;/]
    Tee --> Router[init ModelRouter]
    Router --> Connect[HarnessServiceClientSync]
    Connect --> GetBench[GetBenchmark]
    GetBench --> StartRun[StartRun]

    StartRun --> Pool[ThreadPoolExecutor<br/>max_workers=PARALLEL_TASKS]
    Pool -->|per task| Worker[_run_single_task]

    Worker --> StartTrial[client.start_trial]
    StartTrial --> RunAgent[run_agent]
    RunAgent --> EndTrial[client.end_trial]
    EndTrial --> Stats[collect stats]

    Stats -.все задачи.-> Submit[SubmitRun force=true]
    Submit --> Summary[per-task / per-model<br/>token + score report]
    Summary --> End([exit])

    style Pool fill:#e1ffe1
    style RunAgent fill:#fff4e1
```

## run_agent: конвейер одной задачи

```mermaid
flowchart TB
    In([task_text]) --> Prephase[run_prephase]

    subgraph PP[prephase.py]
        direction TB
        Tree[vm.tree root=/ level=2] --> ReadAGENTS[vm.read /AGENTS.MD]
        ReadAGENTS --> Preload[auto-preload referenced folders]
        Preload --> Ctx[vm.context]
        Ctx --> BuildLog[build log + preserve_prefix<br/>system + few-shot pair]
    end

    Prephase --> PP
    PP --> PreResult[PrephaseResult<br/>log, preserve_prefix,<br/>agents_md, vault_tree]

    PreResult --> Classify[router.resolve_after_prephase]
    Classify --> TaskType[task_type + model + cfg]

    TaskType --> BuildPrompt[build_system_prompt task_type]
    BuildPrompt --> Addendum[build_dynamic_addendum<br/>DSPy fail-open]
    Addendum --> Inject[_inject_addendum]

    Inject --> Loop[run_loop ≤30 steps]
    Loop --> Wiki[_write_wiki_fragment<br/>fail-open]
    Wiki --> Out([token stats])

    style Prephase fill:#fff4e1
    style Classify fill:#e1f5ff
    style Loop fill:#e1ffe1
```

## Жизненный цикл одного шага loop

```mermaid
flowchart TB
    Step([step N ≤ 30]) --> Compact[_compact_log<br/>prefix + last 5]
    Compact --> Call[dispatch<br/>LLM call]
    Call --> Extract[_extract_json_from_text<br/>7-level priority]
    Extract --> Norm[_normalize_parsed]
    Norm --> NextStep[NextStep pydantic]

    NextStep --> StallCk[_check_stall]
    StallCk -->|hint| Retry[_handle_stall_retry<br/>re-call LLM once]
    StallCk -->|ok| PreRoute[_run_pre_route<br/>security]
    Retry --> PreRoute

    PreRoute -->|block| Deny[inject denial,<br/>back to Step]
    PreRoute -->|ok| Action{tool?}

    Action -->|report_completion| EvalGate[evaluate_completion<br/>optional]
    EvalGate -->|reject| Hint[inject hint,<br/>back to Step]
    EvalGate -->|approve| Answer[vm.answer]
    Answer --> Exit([return stats])

    Action -->|read/list/search| ReadOp[PCM call]
    Action -->|write/delete/<br/>move/mkdir| ScopeCk[_check_write_scope]
    ScopeCk -->|deny| Deny
    ScopeCk -->|ok| WriteOp[PCM call]

    ReadOp --> Compress[_compact_tool_result]
    WriteOp --> Compress
    Compress --> Fact[_extract_fact → _StepFact]
    Fact --> Append[log.append user=result]
    Append --> Trace[tracer.emit]
    Trace --> Step

    style Call fill:#e1e1ff
    style StallCk fill:#ffe1e1
    style PreRoute fill:#ffe1e1
    style EvalGate fill:#fff4e1
    style Answer fill:#e1ffe1
```

## Ключевые файлы

| Файл | Роль |
|---|---|
| `main.py` | CLI, подключение к harness, ThreadPoolExecutor, общая статистика |
| `agent/__init__.py` | `run_agent()` — сборка pipeline для одной задачи |
| `agent/prephase.py` | Discovery-фаза: tree, AGENTS.MD, context, few-shot pair |
| `agent/loop.py` | Главный loop ≤30 шагов, оркестрация диспетчера/security/evaluator |
| `agent/models.py` | Pydantic-модели `NextStep`, `Req_Read`, `Req_Write` и т. д. |
| `agent/json_extract.py` | 7-уровневое извлечение JSON из ответа LLM |

## Ограничения и таймауты

- **≤30 шагов на задачу** — после этого форс-ретёрн `OUTCOME_ERR_INTERNAL`.
- **`TASK_TIMEOUT_S`** (по умолчанию 180 s) — принудительное прерывание воркером.
- **`PARALLEL_TASKS`** (по умолчанию 1) — степень параллелизма.
- **≤40K токенов в истории** — обеспечивается `log_compaction` (см. [09 — Наблюдаемость](09-observability.md)).

## Outcome-коды (см. `proto/bitgn/vm/pcm.proto`)

- `OUTCOME_OK` — задача выполнена.
- `OUTCOME_DENIED_SECURITY` — сработала защита.
- `OUTCOME_NONE_CLARIFICATION` — задача неоднозначна.
- `OUTCOME_NONE_UNSUPPORTED` — требует внешнего сервиса.
- `OUTCOME_ERR_INTERNAL` — внутренняя ошибка агента.
