---
wiki_sources:
  - docs/architecture/02-llm-routing.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, dispatch, llm-routing, classifier, claude-code]
---

# LLM-маршрутизация

Как запрос проходит через классификацию задачи, выбор модели и четыре уровня провайдеров.

## Четыре уровня (Four-Tier Dispatch)

```
Anthropic SDK (anthropic/*)
  → если 429/502/503: fallback to OpenRouter

Claude Code tier (claude-code/*)
  → iclaude subprocess / OAuth (взаимоисключающий с Anthropic, не каскад)
  → если timeout/empty: retry CC_MAX_RETRIES+1

OpenRouter (openrouter/*)
  → если 429/502/503: fallback to Ollama

Ollama (ollama или cloud)
  → retry с exponential backoff
```

## ModelRouter: маппинг task_type → модель

| Task type | ENV | Роль |
|---|---|---|
| `preject` | `MODEL_PREJECT` | Немедленный отказ |
| `email` | `MODEL_EMAIL` | Письмо в /outbox/ |
| `inbox` | `MODEL_INBOX` | Один входящий |
| `queue` | `MODEL_QUEUE` → `MODEL_INBOX` | Batch inbox |
| `lookup` | `MODEL_LOOKUP` | Read-only запросы |
| `capture` | `MODEL_CAPTURE` | Запись сниппета |
| `crm` | `MODEL_CRM` | Reschedule + write |
| `temporal` | `MODEL_TEMPORAL` → `MODEL_LOOKUP` | Даты-relative |
| `distill` | — | Анализ + summary |
| — | `MODEL_CLASSIFIER` | Классификация (обязательная) |
| — | `MODEL_EVALUATOR` | Reviewer перед submission |

## Classifier: regex + DSPy

```
task_text
  → regex fast-path (_PREJECT_RE, _EMAIL_RE)
  → DSPy ChainOfThought (compiled data/classifier_program.json)
     или raw LLM prompt (fallback)
  → validate → return task_type
```

## Claude Code tier (изоляция iclaude)

При `claude-code/*` + `CC_ENABLED=1` → `cc_client.cc_complete()`:
- `cwd=tempfile.mkdtemp()` — нет auto-discovery CLAUDE.md
- `--no-save` — нет сессионной истории
- `--strict-mcp-config --mcp-config <empty.json>` — пустой MCP
- `--print --output-format json` — headless режим
- `env` очищен от API keys при `CC_STRIP_PROJECT_ENV=1`
- `start_new_session=True` + killpg SIGTERM→5s→SIGKILL

## Особенности провайдеров

| Провайдер | JSON mode | Extended thinking | Retry |
|---|---|---|---|
| Anthropic | `response_format` / native | `thinking_budget` | 429/502/503 |
| Claude Code | system-prompt trailer | `--effort low/.../max` | CC_MAX_RETRIES+1 |
| OpenRouter | `response_format=json_object/json_schema` | — | 429/502/503 |
| Ollama | принудительно `json_object` | — | 429/502/503 |

## Ключевые файлы

| Файл | Что делает |
|---|---|
| `agent/dispatch.py` | 4-tier оркестрация, `call_llm_raw`, retry |
| `agent/cc_client.py` | Claude Code tier |
| `agent/classifier.py` | `classify_task` (regex), `classify_task_llm` (DSPy), `ModelRouter` |
| `agent/dspy_lm.py` | `DispatchLM` — адаптер для DSPy |
| `models.json` | Per-model и per-task-type конфигурация |
