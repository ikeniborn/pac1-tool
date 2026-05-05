---
wiki_sources:
  - "agent/dispatch.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - dispatch
  - llm
aliases:
  - "call_llm_raw"
  - "четырёхуровневый dispatch"
---

# Dispatch (agent/dispatch.py)

Низкоуровневый модуль, объединяющий два ответственности: (1) маршрутизацию LLM-вызовов по четырём тирам, (2) dispatch PCM-инструментов (Pydantic-модели → gRPC-вызовы к харнессу). Также загружает `.secrets` / `.env` и инициализирует клиентов.

## Основные характеристики

### Четыре тира LLM

| Тир | Условие активации | Примечания |
|-----|------------------|------------|
| Anthropic SDK | `provider='anthropic'` или имя содержит "claude" | Нет `seed`, есть `temperature` |
| Claude Code CLI | `provider='claude-code'` и `CC_ENABLED=1` | Subprocess `iclaude`, stateless, без fallback в следующий тир |
| OpenRouter | `provider='openrouter'` или имя с "/" | Поддерживает `seed`, `temperature`, `logprobs` |
| Ollama | Ollama-формат (`name:tag` без "/") или `provider='ollama'` | Нет `max_tokens`, plain-text retry при пустом ответе |

- **`MODEL_FALLBACK`** (env) — если все тиры primary-модели вернули None, повторяется с fallback-моделью (1 попытка, `{}` cfg)
- **Transient errors** (`TRANSIENT_KWS`): 429, 502, 503, timeout → retry 3× с задержкой 4 с
- **Hard connection errors** (`HARD_CONNECTION_KWS`): broken pipe, ECONNRESET → cap 1 retry, задержка 2 с
- **Capability cache**: определение поддержки `response_format` — сначала static hints (`_STATIC_HINTS`), потом runtime probe; кэш персистируется в `.cache/capability_cache.json` с TTL 7 дней (FIX-213)

### PCM dispatch

`dispatch(vm, cmd)` принимает Pydantic-модель и вызывает соответствующий gRPC-метод на `PcmRuntimeClientSync`. Защита записи: `_PROTECTED_WRITE` (`/AGENTS.MD`) и `_PROTECTED_PREFIX` (`/docs/channels/`) блокируют write/delete/move, кроме `otp.txt` (FIX-205).

## Ключевые функции

- `call_llm_raw(system, user_msg, model, cfg, ...)` — публичный API, включает MODEL_FALLBACK
- `_call_raw_single_model(...)` — внутренний, один проход по всем тирам без fallback
- `probe_structured_output(client, model)` — определить поддержку `json_object`/`json_schema`
- `get_provider(model, cfg)` — определить тир по имени модели или явному `cfg['provider']`
- `is_ollama_model(model)` — True если формат `name:tag` без "/"
- `get_anthropic_model_id(model)` — маппинг алиасов к Anthropic API ID

## Env-переменные

- `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` — ключи доступа
- `OLLAMA_BASE_URL` — адрес Ollama (default: `http://localhost:11434/v1`)
- `CC_ENABLED=1` — включить Claude Code тир
- `MODEL_FALLBACK` — модель для последнего шанса
- `LLM_HTTP_READ_TIMEOUT_S` (default 180), `LLM_HTTP_CONNECT_TIMEOUT_S` (default 10)
- `LOG_LEVEL=DEBUG` — логировать `<think>` блоки

## Связанные концепции

- [[cc-client]] — реализация Claude Code тира (iclaude subprocess)
- [[orchestrator]] — использует dispatch для PCM-инструментов
- [[classifier]] — использует `call_llm_raw` для LLM-классификации
