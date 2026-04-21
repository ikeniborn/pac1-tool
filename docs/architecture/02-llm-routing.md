# 02 — LLM-маршрутизация

Как запрос к LLM проходит через классификацию задачи, выбор модели и четыре уровня провайдеров (Anthropic SDK / Claude Code (`iclaude` subprocess) → OpenRouter → Ollama).

## Общая схема

```mermaid
flowchart TB
    Task([task_text]) --> Regex[regex fast-path<br/>classifier.classify_task]
    Regex -->|preject/email match| Fast[task_type готов]
    Regex -->|нет match| LLMCls[classify_task_llm<br/>DSPy ChainOfThought]
    LLMCls --> Fast

    Fast --> Router[ModelRouter.<br/>resolve_after_prephase]
    Router --> Lookup[_select_model task_type]
    Lookup --> Cfg[_adapt_config<br/>ollama_options overlay]

    Cfg --> Dispatch[dispatch.dispatch]

    subgraph Tier[Four-Tier Dispatch]
        direction TB
        T1a[Tier 1a: Anthropic SDK<br/>anthropic/*]
        T1b[Tier 1b: Claude Code<br/>claude-code/*<br/>iclaude subprocess / OAuth]
        T2[Tier 2: OpenRouter<br/>OpenAI SDK]
        T3[Tier 3: Ollama<br/>OpenAI-compatible]
        T1a -.->|429/502/503| T2
        T1b -.->|None after retries| T2
        T2 -.->|429/502/503| T3
    end

    Dispatch --> Tier
    Tier --> RawResp[raw text<br/>call_llm_raw]
    RawResp --> Back([loop получает NextStep])

    style Regex fill:#e1f5ff
    style Router fill:#fff4e1
    style Tier fill:#e1e1ff
```

## ModelRouter: роутинг по типу задачи

```mermaid
flowchart LR
    Env[ENV vars<br/>MODEL_*] --> Init[ModelRouter __init__]
    JSON[models.json<br/>provider + options] --> Init

    Init --> Fields{{ModelRouter fields}}
    Fields --> DefF[default]
    Fields --> ClsF[classifier]
    Fields --> EvalF[evaluator]
    Fields --> PbF[prompt_builder]
    Fields --> TypeF[email / lookup /<br/>inbox / queue /<br/>capture / crm /<br/>temporal / preject]

    Task[task_text] --> Resolve[resolve_after_prephase]
    Resolve --> ClassCall[classify_task_llm]
    ClassCall --> Select[_select_model type]

    Select -->|type-specific set| Override[use MODEL_&lt;TYPE&gt;]
    Select -->|not set| Fallback[use MODEL_DEFAULT]

    Override --> Config[model cfg from models.json]
    Fallback --> Config
    Config --> Adapt[_adapt_config<br/>ollama_options_classifier<br/>и т.д.]
    Adapt --> Out([model_id, cfg, task_type])

    style Env fill:#e1f5ff
    style JSON fill:#e1f5ff
    style Resolve fill:#fff4e1
```

### Таблица маппинга

| Task type | ENV переменная | Роль в агенте |
|---|---|---|
| `preject` | `MODEL_PREJECT` | Немедленный отказ (внешние сервисы) |
| `email` | `MODEL_EMAIL` | Составление письма в `/outbox/` |
| `inbox` | `MODEL_INBOX` | Обработка одного входящего |
| `queue` | `MODEL_QUEUE` → `MODEL_INBOX` | Пакетная обработка inbox |
| `lookup` | `MODEL_LOOKUP` | Read-only запросы к vault |
| `capture` | `MODEL_CAPTURE` | Фиксация сниппета в путь |
| `crm` | `MODEL_CRM` | Reschedule/reconnect + write |
| `temporal` | `MODEL_TEMPORAL` → `MODEL_LOOKUP` | Даты-относительные запросы |
| `distill` | — | Анализ + write summary (default) |
| `default` | `MODEL_DEFAULT` | Всё остальное |
| — | `MODEL_CLASSIFIER` | Классификация (обязательная) |
| — | `MODEL_EVALUATOR` | Reviewer перед submission |
| — | `MODEL_PROMPT_BUILDER` | Генерация DSPy-адендума |

## Classifier: regex + DSPy

```mermaid
flowchart TB
    In([task_text]) --> RegexCheck{regex match?}
    RegexCheck -->|_PREJECT_RE| Preject[return 'preject']
    RegexCheck -->|_EMAIL_RE| Email[return 'email']
    RegexCheck -->|no match| VaultHint[подгружаем vault_hint:<br/>AGENTS.MD + tree]

    VaultHint --> DspyCheck{compiled program?<br/>data/classifier_program.json}
    DspyCheck -->|yes| ChainOfThought[dspy.ChainOfThought<br/>ClassifyTask signature]
    DspyCheck -->|no| RawLLM[call_llm_raw<br/>raw classification prompt]

    ChainOfThought --> Parse[parse JSON<br/>task_type]
    RawLLM --> Parse
    Parse --> Valid{валидный тип?}
    Valid -->|yes| Ret[return task_type]
    Valid -->|no| Fallback[keyword search →<br/>default]
    Fallback --> Ret

    style RegexCheck fill:#e1f5ff
    style DspyCheck fill:#fff4e1
    style Ret fill:#e1ffe1
```

Wiki-based type hints (см. [07 — Wiki-память](07-wiki-memory.md)) добавляются в `vault_hint` для снижения flip-ов между `inbox/queue`.

## Four-Tier Dispatch

```mermaid
flowchart TB
    Call([call_llm_raw system, user, model, cfg]) --> Detect[provider detection<br/>by model prefix]

    Detect -->|anthropic/*| T1Anthropic[Anthropic SDK]
    Detect -->|claude-code/*| T1CC[Claude Code<br/>iclaude subprocess]
    Detect -->|openrouter/*| T2OpenRouter[OpenRouter]
    Detect -->|*:cloud or *<br/>via Ollama| T3Ollama[Ollama]

    T1Anthropic --> T1Call[messages.create<br/>+ thinking_budget]
    T1CC --> T1CCCall[cc_client.cc_complete<br/>--output-format json<br/>--strict-mcp-config empty<br/>cwd=tmpdir, env stripped]
    T2OpenRouter --> T2Call[chat.completions<br/>+ response_format]
    T3Ollama --> T3Call[chat/completions<br/>json_object enforced]

    T1Call --> Check1{429/502/503?}
    T1CCCall --> CheckCC{timeout/empty?}
    T2Call --> Check2{429/502/503?}
    T3Call --> Check3{429/502/503?}

    Check1 -->|нет| OkResp[raw text + tokens]
    CheckCC -->|нет| OkResp
    Check2 -->|нет| OkResp
    Check3 -->|нет| OkResp

    Check1 -->|да| Backoff1[exp backoff<br/>+ fallback to T2]
    CheckCC -->|да| CCRetry[subprocess restart<br/>CC_MAX_RETRIES+1]
    CCRetry -->|исчерпаны| Return([None → loop retry])
    Check2 -->|да| Backoff2[exp backoff<br/>+ fallback to T3]
    Check3 -->|да| Backoff3[exp backoff<br/>retry]

    Backoff1 --> T2Call
    Backoff2 --> T3Call
    Backoff3 --> T3Call

    OkResp --> Trace[tracer.emit<br/>dispatch_call]
    Trace --> Return

    style T1Anthropic fill:#e1e1ff
    style T1CC fill:#ffe1e1
    style T2OpenRouter fill:#e1e1ff
    style T3Ollama fill:#e1e1ff
```

### Особенности провайдеров

| Провайдер | JSON mode | Extended thinking | Retry |
|---|---|---|---|
| **Anthropic** | через `response_format` / native | `thinking_budget` | 429/502/503 |
| **Claude Code** | system-prompt trailer `"Return ONLY JSON"` (у CLI нет `response_format`) | `--effort low/medium/high/max` (маппинг в профилях `cc_*`) | `CC_MAX_RETRIES+1` subprocess-рестартов |
| **OpenRouter** | `response_format=json_object/json_schema` | — | 429/502/503 |
| **Ollama** | `response_format=json_object` (принудительно) | — | 429/502/503 |

- `probe_structured_output(model, cfg)` — динамически определяет возможности модели (cache в `.cache/`).
- `get_anthropic_model_id(model)` — нормализация имени (`anthropic/claude-opus-4` → `claude-opus-4-20250514`).
- Таймауты httpx: **read 180 s**, **connect 10 s**.

### Claude Code tier (изоляция iclaude)

Когда модель имеет префикс `claude-code/*` (и `CC_ENABLED=1`), `dispatch.py` перенаправляет вызов в `cc_client.cc_complete()` **вместо** Anthropic-tier — это взаимоисключающий выбор, а не каскад. `iclaude` запускается как stateless subprocess с полной изоляцией от host-проекта:

- `cwd=tempfile.mkdtemp()` — нет auto-discovery `CLAUDE.md` из проекта.
- `--no-save` — нет сессионной истории в `~/.claude/projects`.
- `--strict-mcp-config --mcp-config <empty.json>` — пустой список MCP-серверов, никаких tools модели не передаётся (stateless LLM use).
- `--print --output-format json` — headless non-interactive режим, parseable envelope.
- `--system-prompt <sys>` — явный system prompt с трейлером `"Return ONLY a valid JSON object"` (у CLI нет `response_format`).
- `env` очищен: `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` / `OPENAI_API_KEY` удаляются при `CC_STRIP_PROJECT_ENV=1` — iclaude использует собственный OAuth.
- `start_new_session=True` + `killpg` SIGTERM→5s→SIGKILL для чистой остановки по таймауту.

Retry: до `CC_MAX_RETRIES+1` попыток с паузой `CC_RETRY_DELAY_S` между рестартами subprocess (по аналогии с Ollama). После исчерпания — `None`, и loop.py инициирует общий retry.

## models.json: структура конфигурации

```mermaid
flowchart LR
    File[models.json] --> Profiles[_profiles<br/>переиспользуемые<br/>option blocks]
    File --> Entries[model entries<br/>anthropic/claude-opus-4<br/>openrouter/...<br/>minimax-m2.7:cloud<br/>...]

    Profiles --> DefP[default:<br/>num_ctx, temperature]
    Profiles --> ClsP[classifier:<br/>temperature=0.0, seed=1]
    Profiles --> EvalP[evaluator:<br/>temperature=0.1, seed=1]

    Entries --> Fields[provider<br/>max_completion_tokens<br/>thinking_budget<br/>ollama_options<br/>ollama_options_classifier]

    Fields --> Adapt[_adapt_config<br/>в ModelRouter]
    DefP --> Adapt
    ClsP --> Adapt
    EvalP --> Adapt

    Adapt --> Cfg[финальный cfg<br/>в dispatch]
```

## Ключевые файлы

| Файл | Что делает |
|---|---|
| `agent/dispatch.py` | 4-tier оркестрация, `call_llm_raw`, retry, probe |
| `agent/cc_client.py` | Claude Code tier: spawn `iclaude --print --output-format json`, парсинг envelope |
| `agent/classifier.py` | `classify_task` (regex), `classify_task_llm` (DSPy), `ModelRouter` |
| `agent/dspy_lm.py` | `DispatchLM` — адаптер `dspy.BaseLM` поверх `call_llm_raw` |
| `models.json` | Per-model и per-task-type конфигурация |

## Тесты

- `tests/test_classifier.py` — проверка типизации (regex + LLM fallback).
- `tests/test_capability_cache.py` — кеширование `probe_structured_output`.
