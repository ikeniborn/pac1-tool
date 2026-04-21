# 04 — DSPy и оптимизация промптов

Подсистема на базе DSPy, которая компилирует три сигнатуры (classifier, prompt_builder, evaluator) через алгоритм COPRO по собранным примерам.

## Общая схема workflow

```mermaid
flowchart TB
    Run[make run / make task] --> Agent[агент выполняет задачу]

    Agent --> Classifier[classify_task_llm<br/>ClassifyTask sig]
    Agent --> Builder[build_dynamic_addendum<br/>PromptAddendum sig]
    Agent --> Evaluator[evaluate_completion<br/>EvaluateCompletion sig]

    Agent --> Score[harness.EndTrial<br/>score 0..1]

    Score --> Record[dspy_examples.record_*]

    Record -->|builder| BuilderEx[data/dspy_examples.jsonl]
    Record -->|evaluator| EvalEx[data/dspy_eval_examples.jsonl]
    Record -->|errors| ErrEx[data/dspy_errors.jsonl]

    BuilderEx -->|≥30| Optimize[optimize_prompts.py]
    EvalEx -->|≥20| Optimize

    Optimize --> Copro[COPRO<br/>breadth×depth<br/>prompt refinement]
    Copro --> Compiled[data/*_program.json]

    Compiled -.auto-load on next run.-> Agent

    style Record fill:#e1f5ff
    style Optimize fill:#fff4e1
    style Compiled fill:#e1ffe1
```

## Три сигнатуры DSPy

```mermaid
flowchart LR
    subgraph ClassifyTask[ClassifyTask sig]
        CTIn[task_text<br/>vault_hint]
        CTOut[task_type]
        CTIn --> CTOut
    end

    subgraph PromptAddendum[PromptAddendum sig]
        PAIn[task_text<br/>vault_tree_text<br/>vault_context_summary]
        PAOut[addendum<br/>3-6 bullets]
        PAIn --> PAOut
    end

    subgraph EvaluateCompletion[EvaluateCompletion sig]
        ECIn[proposed_outcome<br/>done_operations<br/>task_text<br/>skepticism_level]
        ECOut[approved<br/>issues<br/>correction_hint]
        ECIn --> ECOut
    end

    style ClassifyTask fill:#e1f5ff
    style PromptAddendum fill:#fff4e1
    style EvaluateCompletion fill:#f5e1ff
```

Все три подключаются через `dspy.context(lm=DispatchLM(...))` — то есть используют общий 4-tier dispatch (включая Claude Code через `claude-code/*` префикс у `MODEL_EVALUATOR` / `MODEL_PROMPT_BUILDER` / `MODEL_OPTIMIZER`).

## Сбор примеров во время выполнения

```mermaid
sequenceDiagram
    participant Loop as agent/loop.py
    participant Builder as prompt_builder
    participant Eval as evaluator
    participant Rec as dspy_examples
    participant FS as data/*.jsonl

    Loop->>Builder: build_dynamic_addendum
    Builder-->>Loop: addendum (3-6 bullets)

    Note over Loop: задача выполнена
    Loop->>Eval: evaluate_completion(...)
    Eval-->>Loop: (approved, hint)

    Note over Loop: end_trial даёт score

    Loop->>Rec: record_example(<br/>task_text, task_type,<br/>addendum, score)
    Rec->>FS: append to dspy_examples.jsonl

    Loop->>Rec: record_eval_example(<br/>task_text, outcome,<br/>ops, score)
    Rec->>FS: append to dspy_eval_examples.jsonl

    Note over Rec: vault_tree и AGENTS.MD<br/>НЕ сохраняются<br/>(inflate x4–5)
```

### Что не сохраняется

| Поле | Почему |
|---|---|
| `vault_tree_text` | Почти константа — раздувает JSONL в 4-5 раз |
| `AGENTS.MD content` | То же самое, приводит к drift при paraphrase |
| `done_operations` полностью | Хранится только компактный summary |

## optimize_prompts.py: цикл оптимизации

```mermaid
flowchart TB
    Start["uv run python<br/>optimize_prompts.py<br/>--target builder/evaluator"] --> LoadEx[загрузить примеры<br/>из dspy_*.jsonl]

    LoadEx --> Split[train/eval split<br/>default 80/20]
    Split --> TrainSet[trainset: dspy.Example]
    Split --> DevSet[devset: dspy.Example]

    TrainSet --> InitProg[Initialize program<br/>Predict / ChainOfThought]
    InitProg --> Teleprompt[COPRO teleprompter]

    subgraph CoproLoop[COPRO цикл]
        direction TB
        Breadth[breadth=4<br/>параллельных кандидатов] --> Eval1[оценка на devset]
        Eval1 --> Select[выбор best candidates]
        Select --> Depth{"depth &lt; 2?"}
        Depth -->|да| Refine[refine prompts]
        Refine --> Breadth
        Depth -->|нет| Done[финальная программа]
    end

    Teleprompt --> CoproLoop
    CoproLoop --> Save[program.save<br/>data/&lt;target&gt;_program.json]

    Save --> Report[отчёт: accuracy,<br/>before/after,<br/>примеры разочарований]

    style LoadEx fill:#e1f5ff
    style CoproLoop fill:#fff4e1
    style Save fill:#e1ffe1
```

## Per-task-type оптимизация

```mermaid
flowchart LR
    Ex[data/dspy_examples.jsonl] --> Split[_split_by_task_type]
    Split --> Email["examples[email]"]
    Split --> Inbox["examples[inbox]"]
    Split --> Capture["examples[capture]"]
    Split --> Other["..."]

    Email -->|>=N| OptE[optimize per-type] --> PE[data/prompt_builder_<br/>email_program.json]
    Inbox -->|>=N| OptI[optimize per-type] --> PI[data/prompt_builder_<br/>inbox_program.json]
    Capture -->|>=N| OptC[optimize per-type] --> PC[data/prompt_builder_<br/>capture_program.json]
    Other -->|merged| OptG[optimize global] --> PG[data/prompt_builder_<br/>program.json]

    style PE fill:#e1ffe1
    style PI fill:#e1ffe1
    style PC fill:#e1ffe1
    style PG fill:#fff4e1
```

Fallback-цепочка при загрузке программы в `build_dynamic_addendum`:
```
per-type program → global program → bare signature (fail-open)
```

## Evaluator optimization: per-task-type маршрутизация

Отдельная оптимизация для `evaluator` проводится по тем же правилам, с делением по `task_type`. Это позволяет критику быть более скептичным на `email` и более мягким на `lookup`.

```mermaid
flowchart LR
    EvalEx[data/dspy_eval_examples.jsonl] --> Router[route by task_type]
    Router --> PerType[per-type evaluator programs]
    Router --> Global[global evaluator program]

    PerType --> Load[loaded in evaluator.py]
    Global --> Load
    Load --> EvalCall[evaluate_completion]

    style Router fill:#fff4e1
```

## Конфигурация COPRO

```bash
# optimize_prompts.py читает env
COPRO_BREADTH=4        # параллельных кандидатов на итерации
COPRO_DEPTH=2          # итераций refinement
DSPY_COLLECT=1         # включить сбор примеров в runtime
```

### Метрика

`COPRO` минимизирует `1 - mean(score)` по devset. Метрика — score от harness, нормализованный в [0, 1].

## DispatchLM: мост между DSPy и 4-tier

```mermaid
flowchart LR
    DspyPredict[dspy.Predict<br/>/ ChainOfThought] --> BaseLM[DispatchLM<br/>subclass of dspy.BaseLM]
    BaseLM --> Forward[forward prompt, **kw]
    Forward --> Raw[call_llm_raw<br/>dispatch.py]

    Raw --> T1[Anthropic]
    Raw --> TCC[Claude Code<br/>iclaude]
    Raw --> T2[OpenRouter]
    Raw --> T3[Ollama]

    T1 --> Resp[_Response shim<br/>OpenAI-compatible]
    TCC --> Resp
    T2 --> Resp
    T3 --> Resp

    Resp --> Shim["choices[0].message.content"]
    Shim --> DspyPredict

    style BaseLM fill:#fff4e1
```

`DispatchLM` прозрачно переиспользует retry/fallback из [02 — LLM-маршрутизация](02-llm-routing.md).

## Fail-open: отсутствие скомпилированной программы

```mermaid
flowchart TB
    Call[build_dynamic_addendum] --> Check{program file exists?}
    Check -->|да| Load[dspy.load]
    Check -->|нет| Bare[dspy.Predict<br/>bare signature]

    Load --> Valid{load ok?}
    Valid -->|да| Use[use program]
    Valid -->|нет| Bare

    Use --> Run[program.forward]
    Bare --> Run

    Run --> Ok{успешно?}
    Ok -->|да| Return[addendum]
    Ok -->|нет| Empty[return '', 0, 0<br/>fail-open]

    style Check fill:#e1f5ff
    style Empty fill:#ffe1e1
```

То же самое для `evaluator`: при любом сбое → auto-approve (никогда не блокирует).

## Ключевые файлы

| Файл | Назначение |
|---|---|
| `optimize_prompts.py` | CLI для COPRO: `--target builder\|evaluator` |
| `agent/dspy_lm.py` | `DispatchLM` — `dspy.BaseLM` adapter |
| `agent/dspy_examples.py` | `record_example`, `record_eval_example`, загрузчики |
| `agent/prompt_builder.py` | `PromptAddendum` signature + `build_dynamic_addendum` |
| `agent/evaluator.py` | `EvaluateCompletion` signature + `evaluate_completion` |
| `agent/classifier.py` | `ClassifyTask` signature + `classify_task_llm` |
| `data/prompt_builder_*.json` | скомпилированные builder-программы |
| `data/evaluator_program.json` | скомпилированная evaluator-программа |
| `data/dspy_examples.jsonl` | Собранные примеры builder |
| `data/dspy_eval_examples.jsonl` | Собранные примеры evaluator |
| `data/dspy_errors.jsonl` | Ошибки при загрузке / форсированные fail-open |

## Порог и запуск

```bash
# Собрать примеры автоматически (по ходу запуска задач)
make run

# Когда накопится ≥30 builder / ≥20 evaluator примеров
uv run python optimize_prompts.py --target builder
uv run python optimize_prompts.py --target evaluator

# Скомпилированные программы подгружаются автоматически
# при следующем run — без изменения кода
```
