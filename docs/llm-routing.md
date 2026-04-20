# LLM Routing: 3-Tier Dispatch

Описывает архитектуру маршрутизации LLM-запросов через три уровня провайдеров, управление моделями и capability detection.

---

## Трёхуровневая иерархия провайдеров

```mermaid
flowchart TD
    REQ["LLM-запрос\n(model, messages, cfg)"] --> T1

    subgraph T1["Tier 1: Anthropic SDK"]
        ANT["anthropic.Anthropic()\nNative SDK\nExtended thinking support"]
    end

    subgraph T2["Tier 2: OpenRouter"]
        OR["OpenAI(base_url=openrouter)\nCloud fallback\nМного моделей"]
    end

    subgraph T3["Tier 3: Ollama"]
        OLL["OpenAI(base_url=ollama_url)\nLocal fallback\nБез API-ключей"]
    end

    T1 -->|"Ошибка / недоступен\n429 / 502 / 503"| T2
    T2 -->|"Ошибка / Ollama-модель\nнедоступен"| T3
    T3 -->|"json_object failed"| T3B["Ollama plain-text retry"]

    T1 -->|ok| RESP["NextStep JSON"]
    T2 -->|ok| RESP
    T3 -->|ok| RESP
    T3B -->|ok| RESP
```

**Правила выбора tier:**
- `anthropic_client` существует и модель не ollama → Tier 1
- `openrouter_client` существует и модель не ollama → Tier 2
- Иначе → Tier 3 (Ollama)
- Ollama-модели (`name:tag` без `/`) → всегда Tier 3, пропускают T2

---

## Определение провайдера модели

```mermaid
flowchart TD
    CFG["cfg.get('provider')"] --> EXPLICIT{"Явный\nprovider?"}
    EXPLICIT -->|да| USE["Использовать\nanth / or / ollama"]
    EXPLICIT -->|нет| INFER

    INFER["Инференс по имени модели"] --> I1{"'claude' in name?"}
    I1 -->|да| ANT2["anthropic"]
    I1 -->|нет| I2{"'/' в имени?\n(org/model)"}
    I2 -->|да| OR2["openrouter"]
    I2 -->|нет| I3{"'name:tag'\nформат?"}
    I3 -->|да| OLL2["ollama"]
    I3 -->|нет| OR3["openrouter (default)"]
```

`get_provider(model, cfg)` — единственная точка определения провайдера в `dispatch.py`.

---

## Capability Detection: response_format

Разные модели поддерживают разные режимы структурированного вывода. Определяется один раз и кэшируется.

```mermaid
flowchart TD
    GM["get_response_format(model)"] --> CACHE{"В _cap_cache?"}
    CACHE -->|да| RET["Вернуть кэш"]
    CACHE -->|нет| STATIC

    STATIC["_get_static_hint(model)\nпроверка _STATIC_HINTS"] --> SH{"Hint найден?"}
    SH -->|да| STORE["Сохранить в кэш\n(с меткой 'static hint')"]
    SH -->|нет| PROBE

    PROBE["probe_structured_output(client, model)"] --> TRY["Тестовый вызов\nс response_format=json_object"]
    TRY -->|success| JSON_OBJ["Режим: 'json_object'"]
    TRY -->|fail| NONE["Режим: 'none'"]

    JSON_OBJ --> DISK["Сохранить на диск\n_CACHE_FILE\nTTL = 7 дней (FIX-213)"]
    NONE --> DISK
    STORE --> DISK
```

**Режимы response_format:**

| Режим | Когда | Поведение |
|-------|-------|-----------|
| `json_object` | Большинство Ollama/OR моделей | `{"type": "json_object"}` |
| `none` | Модели без поддержки | Без response_format |
| `plain_text` | `plain_text=True` флаг | Пропустить response_format (codegen) |

Кэш хранится в `data/.capability_cache.json`. Записи старше 7 дней удаляются при загрузке.

---

## call_llm_raw(): лёгкий LLM-вызов

Используется классификатором, wiki-lint, route-LLM. В отличие от `_call_llm()` в loop.py — без NextStep-схемы.

```mermaid
sequenceDiagram
    participant CALLER as classifier / wiki / router
    participant CLR as call_llm_raw()
    participant ANT as Anthropic SDK
    participant OR as OpenRouter
    participant OLL as Ollama

    CALLER->>CLR: system, user_msg, model, cfg,\nmax_tokens, plain_text, token_out

    CLR->>CLR: get_provider(model, cfg)

    alt provider == anthropic
        loop max_retries (default 3)
            CLR->>ANT: messages.create()\ntemperature из cfg (FIX-187)
            ANT-->>CLR: content | error
            alt transient error (429/502/503)
                CLR->>CLR: sleep 4s, retry
            else ok
                CLR-->>CALLER: stripped text
            end
        end
    end

    alt anthropic failed / provider != anthropic
        loop max_retries
            CLR->>OR: chat.completions.create()\nresponse_format если поддерживается
            OR-->>CLR: content | error
            alt transient error
                CLR->>CLR: sleep 4s, retry
            else ok
                CLR-->>CALLER: stripped text
            end
        end
    end

    alt openrouter failed / ollama model
        loop max_retries
            CLR->>OLL: chat.completions.create()
            OLL-->>CLR: content | error
            alt json_object failed + не plain_text
                CLR->>OLL: plain-text retry (FIX-136)
                OLL-->>CLR: content
            end
        end
    end

    CLR->>CLR: strip <think>...</think> (FIX-220)
    CLR-->>CALLER: text | None
    note over CLR: token_out обновляется если передан
```

---

## _call_llm(): главный LLM-вызов в loop.py

Используется в основном агентском цикле. Возвращает `NextStep | None` + метрики.

```mermaid
flowchart TD
    CL["_call_llm(log, model, max_tokens, cfg)"] --> PROV["get_provider(model, cfg)"]

    PROV --> ANT_P{"provider ==\nanthropic?"}
    ANT_P -->|да| CONV["_to_anthropic_messages(log)\n→ (system_prompt, messages)\nMerge consecutive same-role"]

    CONV --> ANT_CALL["Anthropic messages.create()\n• temperature (FIX-187)\n• thinking_budget если есть\n• max_tokens cap\n• seed извлекается (FIX-197)"]

    ANT_P -->|нет| OAI["OpenAI-compatible call\n(OR или Ollama)\n• response_format\n• temperature (FIX-211)\n• seed из cfg"]

    ANT_CALL --> THINK["Strip <think> blocks\nОценить thinking_tokens\n= len(think_text) / 4"]
    OAI --> THINK

    THINK --> PARSE["json_extract._extract_json_from_text()\n7-level priority extraction"]
    PARSE --> NORM["_normalize_parsed()\n• wrap bare function\n• truncate plan to 5\n• set task_completed=False"]

    NORM --> VALID{"Pydantic\nvalidation\nNextStep?"}
    VALID -->|ok| RET["Return (NextStep, elapsed_ms,\nin_tok, out_tok,\nthinking_tok, ev_c, ev_ms)"]
    VALID -->|fail| NONE2["Return (None, ...)"]
```

---

## Anthropic: конвертация формата сообщений

Anthropic API требует отдельного `system` параметра. `_to_anthropic_messages()` конвертирует OpenAI-формат.

```mermaid
flowchart TD
    LOG["log: list[dict]\nOpenAI-формат\n[{role, content}, ...]"] --> SYS_EXTRACT

    SYS_EXTRACT["Извлечь первый\n{role: system}\n→ system_prompt string"] --> MERGE

    MERGE["Смержить подряд\nидущие одинаковые role\n(FIX: consecutive merge)"] --> BUILD

    BUILD["Построить messages list\nтолько user/assistant"] --> OUT

    OUT["Return (system_prompt, messages)\nдля Anthropic SDK"]
```

**Важно:** Anthropic не поддерживает `seed`. Значение извлекается из `cfg` для логирования, но не передаётся в API (FIX-197).

---

## models.json: конфигурация моделей

```mermaid
graph TD
    MJSON["models.json"] --> PROF["_profiles\nИменованные пресеты параметров"]
    MJSON --> MODELS["Записи моделей\nmodel_id → config"]

    PROF --> P1["default\ntemp=0.35, seed=1\nnum_ctx=16384"]
    PROF --> P2["classifier\ntemp=0.0, seed=1"]
    PROF --> P3["evaluator\ntemp=0.1, seed=1"]
    PROF --> P4["long_ctx\ntemp=0.2, num_ctx=32768"]
    PROF --> P5["coder\ntemp=0.1, repeat_penalty=1.1"]

    MODELS --> M1["anthropic/claude-haiku-4.5\nprovider: anthropic\nmax_completion_tokens: 4000"]
    MODELS --> M2["anthropic/claude-opus-4.6\nprovider: anthropic\nthinking_budget: 8000"]
    MODELS --> M3["openrouter/...\nresponse_format_hint: json_object\ntemperature: 0.35"]
    MODELS --> M4["qwen3.5:9b\nprovider: ollama\nollama_options: default"]
    MODELS --> M5["deepseek-v3.1:671b-cloud\nprovider: ollama\nollama_options: long_ctx"]
```

**Резолюция профилей** (FIX-119, `main.py` строки 131–137):

```python
# При запуске: строковые ссылки на профили → раскрыть в dict
for model_id, cfg in models.items():
    if isinstance(cfg.get("ollama_options"), str):
        cfg["ollama_options"] = profiles[cfg["ollama_options"]]
```

---

## ModelRouter: маршрутизация по типу задачи

```mermaid
flowchart TD
    MR["ModelRouter\n(из env-переменных + models.json)"] --> RES

    RES["resolve_after_prephase(\ntask_text, pre)"] --> CLS_LLM["classify_task_llm(\ntask_text, model=classifier,\nvault_hint)"]

    CLS_LLM --> TT["task_type"]
    TT --> SEL["_select_model(task_type)"]

    SEL --> E{"MODEL_EMAIL\nесть?"}
    E -->|email| EM["MODEL_EMAIL"]
    SEL --> I{"MODEL_INBOX\nесть?"}
    I -->|inbox| IM["MODEL_INBOX"]
    SEL --> Q{"MODEL_QUEUE\nесть?"}
    Q -->|queue| QM["MODEL_QUEUE\nFallback → MODEL_INBOX"]
    SEL --> D["...другие типы..."]
    SEL --> DEF["MODEL_DEFAULT\n(финальный fallback)"]

    EM & IM & QM & D & DEF --> ADAPT["_adapt_config(cfg, task_type)\noverlay: ollama_options_{task_type}"]
    ADAPT --> OUT2["Return (model_id, cfg, task_type)"]
```

**Переменные окружения для моделей:**

| Переменная | Тип задачи | Fallback |
|-----------|-----------|---------|
| `MODEL_DEFAULT` | все | — |
| `MODEL_EMAIL` | email | MODEL\_DEFAULT |
| `MODEL_LOOKUP` | lookup | MODEL\_DEFAULT |
| `MODEL_INBOX` | inbox | MODEL\_DEFAULT |
| `MODEL_QUEUE` | queue | MODEL\_INBOX → MODEL\_DEFAULT |
| `MODEL_CAPTURE` | capture | MODEL\_DEFAULT |
| `MODEL_CRM` | crm | MODEL\_DEFAULT |
| `MODEL_TEMPORAL` | temporal | MODEL\_DEFAULT |
| `MODEL_PREJECT` | preject | MODEL\_DEFAULT |
| `MODEL_EVALUATOR` | evaluator | MODEL\_DEFAULT |
| `MODEL_PROMPT_BUILDER` | prompt\_builder | MODEL\_CLASSIFIER |
| `MODEL_CLASSIFIER` | classify / wiki-lint | MODEL\_DEFAULT |

---

## Classify: двухуровневая классификация

```mermaid
flowchart TD
    TXT["task_text"] --> REGEX["classify_task()\nRegex fast-path\nO(1) matching"]

    REGEX --> HC{"Высокая уверенность?\n(preject, email)"}
    HC -->|да| SKIP_LLM["Пропустить LLM\nReturn task_type"]

    HC -->|нет / default| VHINT["_count_tree_files(prephase_log)\n→ vault_hint строка"]
    VHINT --> LLM_C["classify_task_llm()\ncall_llm_raw() + plain-text prompt\nReturn JSON {type: X}"]

    LLM_C --> PARSE_C{"JSON parse\nуспешен?"}
    PARSE_C -->|да| EXT["Извлечь task_type\nиз поля 'type'"]
    PARSE_C -->|нет| RE_EXT["Regex extraction\n{\"type\": \"X\"}"]
    RE_EXT --> KW{"Ключевое слово\nв тексте?"}
    KW -->|да| KW_TYPE["task_type по ключевому слову"]
    KW -->|нет| FALLBACK["Regex fallback\nclassify_task()"]

    EXT & KW_TYPE & FALLBACK --> FINAL["Return task_type"]
```

**Regex-правила классификации** (приоритет сверху вниз):

| Тип | Паттерн |
|-----|---------|
| `preject` | calendar invite / sync to external / upload to salesforce |
| `queue` | work through / take care of / process bulk inbox |
| `inbox` | process/check/handle + single inbox/inbound |
| `email` | send/compose/write email + recipient/subject |
| `lookup` | find/search contact/account / count\_query без write |
| `capture` | capture + snippet/from/into |
| `crm` | reschedule/reconnect + date arithmetic |
| `temporal` | N days ago / in N days / what date |
| `distill` | analyze/summarize/evaluate (think words) |
| `default` | всё остальное |

---

## Write-protection в dispatch()

`dispatch()` реализует code-level защиту независимо от агентских решений (FIX-205):

```mermaid
flowchart TD
    D["dispatch(vm, cmd)"] --> TYPE{"Req_Write\nили Req_Delete?"}
    TYPE -->|нет| ROUTE["Маршрутизировать\nk vm.method()"]

    TYPE -->|да| PW{"path in\n_PROTECTED_WRITE?\n/AGENTS.MD"}
    PW -->|да| OTP_EX{"cmd == Req_Delete\n+ path == /docs/channels/otp.txt\n(FIX-154)"}
    OTP_EX -->|да| ROUTE
    OTP_EX -->|нет| ERR1["Return ERROR:\nprotected path"]

    PW -->|нет| PP{"path.startswith(\n_PROTECTED_PREFIX)?\n/docs/channels/"}
    PP -->|да| OTP_EX2{"otp.txt\nexception?"}
    OTP_EX2 -->|да| ROUTE
    OTP_EX2 -->|нет| ERR2["Return ERROR:\nprotected prefix"]

    PP -->|нет| ROUTE
```

---

## Think-блоки: обработка extended thinking

Anthropic-модели с `thinking_budget` возвращают `<think>...</think>` блоки внутри ответа.

```mermaid
flowchart TD
    RAW["Сырой текст\nот модели"] --> THK_RE["_THINK_RE.sub('', raw)\nУдалить <think>...</think>"]
    THK_RE --> CLEAN["Очищенный текст\nдля JSON extraction"]

    RAW --> TKCOUNT["thinking_tokens ≈\nlen(think_text) / 4\n(оценка, не точный счёт)"]
    TKCOUNT --> STATS["Передать в\nelapsed / token stats"]
```

`LOG_LEVEL=DEBUG` → think-блоки дополнительно логируются в файл задачи.

---

## Transient-error retry

```mermaid
flowchart TD
    CALL["API call"] --> ERR{"Ошибка?"}
    ERR -->|нет| OK["Return response"]
    ERR -->|да| TRANS{"Transient?\n(TRANSIENT_KWS:\nrate_limit, 429,\n502, 503, timeout,\noverloaded)"}
    TRANS -->|нет| RAISE["Re-raise / Return None"]
    TRANS -->|да| SLEEP["sleep(4s)"]
    SLEEP --> COUNT{"attempt <\nmax_retries?"}
    COUNT -->|да| CALL
    COUNT -->|нет| RAISE
```

`max_retries=3` по умолчанию → до 4 попыток на tier. Суммарно с тремя tier: до 12 попыток перед финальным отказом.
