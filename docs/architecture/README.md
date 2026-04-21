# Архитектура PAC1-Tool

Python-агент для бенчмарка BitGN PAC1, управляющий персональным knowledge-vault через 9 инструментов PCM (`tree`, `find`, `search`, `list`, `read`, `write`, `delete`, `mkdir`, `move`, `report_completion`). Связь с harness — Protobuf + gRPC-Connect.

## Обзор на одном экране

```mermaid
flowchart LR
    Harness[BitGN Harness<br/>gRPC-Connect] --> Main[main.py<br/>ThreadPoolExecutor]
    Main --> Agent[agent.run_agent]

    subgraph Agent_Pipeline[Конвейер обработки задачи]
        direction TB
        Prephase[prephase<br/>tree+AGENTS.MD+context] --> Classifier[classifier<br/>task type + model]
        Classifier --> Prompt[prompt<br/>system prompt]
        Prompt --> Builder[prompt_builder<br/>DSPy addendum]
        Builder --> Loop[loop ≤30 steps]
    end

    Agent --> Agent_Pipeline

    subgraph Step_Cycle[Шаг loop]
        direction TB
        Dispatch[dispatch<br/>4-tier LLM] --> JSON[json_extract]
        JSON --> Stall[stall detect]
        Stall --> Security[security gates]
        Security --> Tool[PCM tool]
        Tool --> Eval[evaluator<br/>pre-submit review]
    end

    Loop --> Step_Cycle
    Step_Cycle --> VM[PCM Runtime<br/>9 tools]
    VM --> Vault[(Vault<br/>filesystem)]

    Loop -.wiki fragment.-> Wiki[data/wiki/]
    Loop -.traces.-> Tracer[logs/*/traces.jsonl]

    style Harness fill:#e1f5ff
    style VM fill:#fff4e1
    style Vault fill:#f0f0f0
    style Wiki fill:#f5e1ff
```

## Ключевые архитектурные решения

| Паттерн | Реализация | Зачем |
|---|---|---|
| **Discovery-First** | Пути vault не хардкодятся; агент читает `AGENTS.MD` | Переносимость между профилями vault |
| **Four-Tier Dispatch** | Anthropic SDK / Claude Code (`iclaude`) → OpenRouter → Ollama, ретраи на `429/502/503` | Устойчивость к перебоям + локальный OAuth-фолбэк без API-ключей |
| **Codegen-prompt** | Модель пишет Python-код, а не сырой JSON | Сложный анализ (агрегации, даты) |
| **Prefix-Compaction** | Первые system+few-shot сохраняются, середина сжимается | Удержание ≤40K токенов в контексте |
| **Fail-Open DSPy** | Отсутствие скомпилированной программы → baseline | Агент работает без оптимизации |
| **Multi-Stage Security** | Нормализация → injection → contamination → write-scope → OTP | Защита от prompt-injection |
| **Stall Detection** | 3 сигнала: action-loop / path-error / exploration | Выход из зацикливаний |
| **Wiki-Memory** | Фрагменты per-task → LLM-lint в страницы | Кросс-сессионная память |

## Разделы документации по доменам

1. [**01 — Поток выполнения**](01-execution-flow.md) — `main.py`, `run_agent`, `loop.py`, жизненный цикл шага.
2. [**02 — LLM-маршрутизация**](02-llm-routing.md) — four-tier `dispatch.py` (+ `cc_client.py`), `classifier.py`, `ModelRouter`, `models.json`.
3. [**03 — Prompt-система**](03-prompt-system.md) — `prompt.py` (статический), `prephase.py` (discovery), `prompt_builder.py` (DSPy addendum).
4. [**04 — DSPy и оптимизация**](04-dspy-optimization.md) — сигнатуры, `optimize_prompts.py`, COPRO, сбор примеров.
5. [**05 — Безопасность и stall-detection**](05-security-stall.md) — `security.py`, `stall.py`, многоуровневый pipeline защиты.
6. [**06 — Evaluator**](06-evaluator.md) — `evaluator.py`, pre-submission review, verbatim-gate.
7. [**07 — Wiki-память**](07-wiki-memory.md) — `wiki.py`, fragments/pages/lint, кросс-сессионные знания.
8. [**08 — Harness и PCM**](08-harness-protocol.md) — `bitgn/`, `proto/`, 9 инструментов, gRPC-Connect.
9. [**09 — Наблюдаемость**](09-observability.md) — `tracer.py`, `log_compaction.py`, JSONL-трейсы.

## Дерево модулей

```mermaid
graph TD
    main[main.py] --> agent_init[agent/__init__.py]
    main --> harness[bitgn/harness_connect]

    agent_init --> loop[agent/loop.py]
    agent_init --> classifier[agent/classifier.py]
    agent_init --> prephase[agent/prephase.py]
    agent_init --> prompt[agent/prompt.py]
    agent_init --> builder[agent/prompt_builder.py]
    agent_init --> wiki[agent/wiki.py]
    agent_init --> pcm[bitgn/vm/pcm_connect]

    loop --> dispatch[agent/dispatch.py]
    loop --> evaluator[agent/evaluator.py]
    loop --> security[agent/security.py]
    loop --> stall[agent/stall.py]
    loop --> jsonx[agent/json_extract.py]
    loop --> compact[agent/log_compaction.py]
    loop --> tracer[agent/tracer.py]
    loop --> models[agent/models.py]

    builder --> dspy_lm[agent/dspy_lm.py]
    evaluator --> dspy_lm
    classifier --> dspy_lm
    dspy_lm --> dispatch

    classifier --> dispatch
    security --> classifier

    optimize[optimize_prompts.py] --> builder
    optimize --> evaluator
    optimize --> classifier
    optimize --> dspy_lm

    style main fill:#ffe1e1
    style loop fill:#e1ffe1
    style dispatch fill:#e1e1ff
    style optimize fill:#fff4e1
```

## Где что лежит

| Путь | Содержимое |
|---|---|
| `main.py` | Точка входа, подключение к harness, ThreadPoolExecutor |
| `agent/` | Ядро агента: loop, dispatch, классификатор, security и т.д. |
| `bitgn/` | Сгенерированные gRPC-Connect стабы (не редактировать вручную) |
| `proto/bitgn/` | `.proto` определения (harness + PCM) |
| `data/wiki/` | Страницы/фрагменты wiki-памяти |
| `data/*.json` | Скомпилированные DSPy-программы (COPRO) |
| `data/*.jsonl` | Собранные примеры для оптимизации |
| `models.json` | Конфигурация моделей и per-task маршрутизация |
| `logs/<ts>_<model>/` | Лог-артефакты одного запуска (stdout, traces) |
| `tests/` | Тесты: classifier, json_extract, evaluator, security_gates |

## Запуск

```bash
make sync                           # uv sync
make run                            # все задачи бенчмарка
make task TASKS='t01,t02'           # подмножество
uv run python -m agent.tracer logs/<file>.jsonl   # реплей
uv run python optimize_prompts.py --target builder
uv run python optimize_prompts.py --target evaluator
```
