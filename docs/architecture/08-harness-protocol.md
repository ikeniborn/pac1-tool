# 08 — Harness и PCM

Два внешних интерфейса через gRPC-Connect over HTTP: сервис `HarnessService` управляет прогоном бенчмарка, сервис `PcmRuntime` предоставляет 9 vault-инструментов.

## Два сервиса

```mermaid
flowchart TB
    Agent[PAC1 Agent] -->|control plane| Harness[HarnessService<br/>GetBenchmark<br/>StartRun<br/>StartTrial<br/>EndTrial<br/>SubmitRun]
    Agent -->|data plane| PCM[PcmRuntime<br/>9 tools + answer]

    Harness -->|trial URL| AssignPcm[назначает PcmRuntime<br/>для каждого trial]
    AssignPcm --> PCM

    PCM --> Vault[(Vault filesystem<br/>sandboxed)]
    Harness --> Scoring[Scoring engine]

    style Harness fill:#e1f5ff
    style PCM fill:#fff4e1
```

## Protocol stack

```mermaid
flowchart LR
    Proto[proto/bitgn/*.proto<br/>Protocol Buffers 3] -->|buf generate| Stubs[bitgn/*_pb2.py<br/>bitgn/*_connect.py]
    Stubs --> Client[Connect Sync Client]
    Client --> HTTP[httpx HTTP/1.1 или HTTP/2]
    HTTP --> Wire[gRPC-Connect wire<br/>JSON или binary protobuf]
    Wire --> Server[BitGN server]

    style Proto fill:#e1f5ff
    style Stubs fill:#fff4e1
```

`bitgn/_connect.py` — тонкая обёртка над `ConnectClient` (gRPC-Connect sync). **Файлы `bitgn/*` — сгенерированы; редактировать нельзя** (`make proto` перезаписывает).

## HarnessService

```mermaid
sequenceDiagram
    participant Main as main.py
    participant H as HarnessService

    Main->>H: Status()
    H-->>Main: ok

    Main->>H: GetBenchmark(benchmark_id)
    H-->>Main: Benchmark{tasks: [...], metadata}

    Main->>H: StartRun(name, benchmark_id, api_key)
    H-->>Main: run_id

    loop по всем trials
        Main->>H: StartTrial(trial_id)
        H-->>Main: Trial{task_text, harness_url}
        Note over Main: harness_url — адрес PcmRuntime<br/>для этого конкретного trial
        Note over Main: выполнение задачи → agent
        Main->>H: EndTrial(trial_id)
        H-->>Main: Score{value: 0..1, detail: [...]}
    end

    Main->>H: SubmitRun(run_id, force=true)
    H-->>Main: finalized
```

## PcmRuntime: 9 инструментов + answer

```mermaid
flowchart TB
    subgraph ReadOps[read операции]
        Tree[tree<br/>root, level]
        Find[find<br/>root, name, type, limit]
        Search[search<br/>root, pattern, limit]
        List[list<br/>path]
        Read[read<br/>path, start/end_line]
        Context[context<br/>→ date, user, ...]
    end

    subgraph MutOps[мутации]
        Write[write<br/>path, content,<br/>start/end_line]
        Delete[delete<br/>path]
        MkDir[mkdir<br/>path]
        Move[move<br/>from_name, to_name]
    end

    subgraph Finish[финализация]
        Answer[answer<br/>message, outcome, refs]
    end

    ReadOps --> VFS[(Virtual FS)]
    MutOps --> VFS
    Finish --> Scorer[Scoring]

    style ReadOps fill:#e1f5ff
    style MutOps fill:#fff4e1
    style Finish fill:#e1ffe1
```

## Формальная таблица инструментов

| Tool | Request fields | Response | Назначение |
|---|---|---|---|
| `tree` | `root`, `level` | TreeResponse(nodes) | Рекурсивное дерево vault |
| `find` | `root`, `name`, `type`, `limit` | `list[str]` | Поиск по имени |
| `search` | `root`, `pattern`, `limit` | `list[SearchMatch]` | Full-text поиск |
| `list` | `path` | `list[ListEntry]` | Listing директории |
| `read` | `path`, `number`, `start_line`, `end_line` | `content` | Чтение файла/диапазона |
| `write` | `path`, `content`, `start_line`, `end_line` | empty | Create/overwrite/append |
| `delete` | `path` | empty | Удаление |
| `mkdir` | `path` | empty | Создание директории |
| `move` | `from_name`, `to_name` | empty | Переименование |
| `context` | — | `content (JSON)` | Метаданные задачи (дата, user) |
| `answer` | `message`, `outcome`, `refs` | empty | Финализация |

## Pydantic layer: NextStep и Req_*

```mermaid
flowchart TB
    LLM[LLM raw JSON] --> Extract[json_extract.py]
    Extract --> Normalize[_normalize_parsed]
    Normalize --> NextStep[NextStep pydantic]

    NextStep --> Current[current_state]
    NextStep --> Reasoning[reasoning]
    NextStep --> Function[function]

    Function --> ReqRead[Req_Read path, ...]
    Function --> ReqWrite[Req_Write path, content, ...]
    Function --> ReqSearch[Req_Search root, pattern, ...]
    Function --> Others[Req_List, Req_Tree,<br/>Req_Find, Req_Delete,<br/>Req_MkDir, Req_Move,<br/>Req_Context,<br/>Req_ReportCompletion]

    Others --> ToPb[convert к protobuf]
    ReqRead --> ToPb
    ReqWrite --> ToPb
    ReqSearch --> ToPb

    ToPb --> VMCall[vm.&lt;tool&gt; req]
    VMCall --> PbResp[protobuf response]
    PbResp --> Format[format result text]
    Format --> LogAppend[log.append user=result]

    style NextStep fill:#fff4e1
    style ToPb fill:#e1f5ff
```

`agent/models.py` определяет:
- `NextStep` — контейнер ответа LLM.
- `Req_Read`, `Req_Write`, ..., `Req_ReportCompletion` — 10 discriminated unions.

## Outcome enum (из `proto/bitgn/vm/pcm.proto`)

```mermaid
flowchart LR
    Out[Outcome enum] --> Ok[OUTCOME_OK<br/>успех]
    Out --> Sec[OUTCOME_DENIED_SECURITY<br/>injection / scope]
    Out --> Clar[OUTCOME_NONE_CLARIFICATION<br/>ambiguous task]
    Out --> Unsup[OUTCOME_NONE_UNSUPPORTED<br/>external service]
    Out --> Err[OUTCOME_ERR_INTERNAL<br/>agent error]

    style Ok fill:#e1ffe1
    style Sec fill:#ffe1e1
    style Clar fill:#fff4e1
    style Unsup fill:#fff4e1
    style Err fill:#ffe1e1
```

## Пример запроса `write`

```mermaid
sequenceDiagram
    participant LLM
    participant Loop as agent/loop
    participant Pyd as NextStep/<br/>Req_Write
    participant Pb as pcm_pb2.<br/>WriteRequest
    participant Stub as pcm_connect.<br/>PcmRuntimeClientSync
    participant PCM as PcmRuntime

    LLM-->>Loop: {"tool":"write","path":"/outbox/5.json","content":"..."}
    Loop->>Pyd: Req_Write(**args)
    Pyd-->>Loop: validated
    Loop->>Pb: WriteRequest(path=..., content=...)
    Loop->>Stub: vm.write(req)
    Stub->>PCM: POST /bitgn.vm.pcm.PcmRuntime/Write
    PCM-->>Stub: WriteResponse()
    Stub-->>Loop: empty ok
    Loop->>Loop: format "WRITTEN: /outbox/5.json"
    Loop->>Loop: log.append(user=result)
```

## Регенерация protobuf-стабов

```bash
# Makefile target
make proto

# или вручную
buf generate
```

Стабы генерируются в `bitgn/` (flat) и `bitgn/vm/`. Ручные правки будут перезаписаны.

## Ключевые файлы

| Файл | Содержимое |
|---|---|
| `proto/bitgn/harness.proto` | HarnessService definition |
| `proto/bitgn/vm/pcm.proto` | PcmRuntime definition + 9 tools |
| `bitgn/harness_connect.py` | gRPC-Connect stub (HarnessService) |
| `bitgn/harness_pb2.py` | Protobuf message классы |
| `bitgn/vm/pcm_connect.py` | gRPC-Connect stub (PcmRuntime) |
| `bitgn/vm/pcm_pb2.py` | Protobuf message классы |
| `bitgn/_connect.py` | Общая обёртка `ConnectClient` |
| `agent/models.py` | Pydantic-слой (`NextStep`, `Req_*`) |

## Таймауты и ретраи

- HTTP read timeout: **180 s**.
- Connect timeout: **10 s**.
- При `429/502/503` от любого сервиса — retry с экспоненциальным backoff (см. [02 — LLM-маршрутизация](02-llm-routing.md), ту же логику используют и PCM-вызовы через httpx).
