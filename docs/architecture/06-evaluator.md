# 06 — Evaluator

Критический gate перед `vm.answer()`: ревью предложенного исхода на соответствие задаче и реально выполненным операциям.

## Роль в life-cycle шага

```mermaid
flowchart LR
    LLM[LLM NextStep] --> Tool{tool?}
    Tool -->|read/list/...| Exec[выполнить]
    Tool -->|report_completion| EvalGate[evaluate_completion]

    EvalGate --> Verbatim[check_quoted_values_verbatim<br/>hard gate]
    Verbatim -->|mismatch| Hint1[reject: 'fix quote']
    Verbatim -->|ok| DspyEval[dspy.ChainOfThought<br/>EvaluateCompletion]

    DspyEval --> Dec{approved?}
    Dec -->|да| Answer[vm.answer outcome]
    Dec -->|нет + hint| Inject[inject hint<br/>back to loop]
    Dec -->|max_rejections| Force[force approve]

    style EvalGate fill:#fff4e1
    style Verbatim fill:#ffe1e1
    style Answer fill:#e1ffe1
```

## EvaluateCompletion signature

```
Input:
  - proposed_outcome  : OUTCOME_OK | OUTCOME_DENIED_SECURITY |
                        OUTCOME_NONE_CLARIFICATION |
                        OUTCOME_NONE_UNSUPPORTED | OUTCOME_ERR_INTERNAL
  - done_operations   : ['WRITTEN: /outbox/5.json', 'READ: /contacts/maya.json', ...]
  - task_text         : оригинальный текст
  - skepticism_level  : low | mid | high

Output (ChainOfThought):
  - reasoning         : рассуждение модели
  - approved          : bool
  - issues            : list[str] — что не так
  - correction_hint   : str — как исправить
```

## Skepticism levels

```mermaid
flowchart LR
    Low[low<br/>approve unless<br/>obvious contradiction] --> Med[mid<br/>verify outcome<br/>vs evidence]
    Med --> High[high<br/>assume mistake,<br/>search errors actively]

    style Low fill:#e1ffe1
    style Med fill:#fff4e1
    style High fill:#ffe1e1
```

Настраивается через `EVAL_SKEPTICISM=low|mid|high` (по умолчанию `mid`).

## Verbatim gate (hard)

Отдельный предпроверочный gate, не зависящий от LLM.

```mermaid
flowchart TB
    Task[task_text] --> Quoted[найти quoted strings<br/>заканчивающиеся на<br/>. , ! ? ; :]
    Quoted --> ExtractW[извлечь writes<br/>из done_operations]

    Quoted --> Compare{для каждого quote<br/>с пунктуацией}
    ExtractW --> Compare

    Compare -->|full form есть| Ok[ok]
    Compare -->|только stripped<br/>без пунктуации| Fail[fail:<br/>'Quick note' без '.'<br/>при 'Quick note.' в задаче]

    Fail --> Hint[hint: 'include trailing<br/>punctuation verbatim']
    Ok --> Pass[pass → DSPy gate]

    style Fail fill:#ffe1e1
    style Pass fill:#e1ffe1
```

**Зачем это руками**: LLM-критик склонен paraphrase и дропать финальную пунктуацию, хотя бенчмарк проверяет exact match. Жёсткий предварительный регекс-gate ловит это до ChainOfThought.

## Fail-open policy

```mermaid
flowchart TB
    Entry[evaluate_completion] --> Enabled{EVALUATOR_ENABLED=1?}
    Enabled -->|нет| Skip[auto-approve]
    Enabled -->|да| Verbatim[verbatim gate]

    Verbatim -->|fail| Reject1[reject with hint]
    Verbatim -->|ok| LoadProg{compiled program?}

    LoadProg -->|yes| Dspy[dspy.ChainOfThought]
    LoadProg -->|no| Bare[bare signature]

    Dspy --> Try{try/except}
    Bare --> Try

    Try -->|success| Parse[parse approved/issues/hint]
    Try -->|any error| FailOpen[auto-approve<br/>log error]

    Parse --> Return[return approved, hint]
    FailOpen --> Return
    Skip --> Return
    Reject1 --> Return

    style FailOpen fill:#ffe1e1
    style Skip fill:#f0f0f0
```

**Принцип**: evaluator никогда не блокирует задачу. Любой сбой → auto-approve. Это предотвращает превращение критика в источник отказов.

## Rejection loop

```mermaid
flowchart TB
    Completion[completion #1] --> Eval1[evaluate]
    Eval1 -->|approved| Submit1[vm.answer]
    Eval1 -->|reject + hint| Inject1[inject hint в log]
    Inject1 --> Completion2[completion #2]
    Completion2 --> Eval2[evaluate]
    Eval2 -->|approved| Submit2[vm.answer]
    Eval2 -->|reject + hint| Check{rejections ≥<br/>EVAL_MAX_REJECTIONS?}
    Check -->|да| Force[force approve<br/>submit as-is]
    Check -->|нет| Inject2
    Inject2 --> CompletionN[completion #N]

    style Force fill:#ffe1e1
    style Submit1 fill:#e1ffe1
    style Submit2 fill:#e1ffe1
```

По умолчанию `EVAL_MAX_REJECTIONS=2` — критик может отклонить максимум 2 раза; третий completion проходит принудительно.

## Per-task-type evaluator

Благодаря оптимизации из [04 — DSPy и оптимизация](04-dspy-optimization.md), для разных типов задач могут быть разные скомпилированные evaluator-программы. Загрузка по цепочке:

```
data/evaluator_<task_type>_program.json
  → data/evaluator_program.json
  → bare signature
```

## Интеграция с loop.py

```mermaid
sequenceDiagram
    participant L as loop
    participant E as evaluator
    participant VM as PCM

    L->>L: LLM выдал report_completion
    L->>E: evaluate_completion(completion, log, task_text, ...)

    E->>E: check_quoted_values_verbatim
    alt mismatch
        E-->>L: (False, hint)
        L->>L: inject hint в log
        Note over L: следующий шаг
    else ok
        E->>E: dspy.ChainOfThought(EvaluateCompletion)
        alt approved
            E-->>L: (True, None)
            L->>VM: vm.answer(outcome, message, refs)
        else reject
            E-->>L: (False, hint)
            L->>L: inject hint
        else max_rejections reached
            E-->>L: (True, None) — force
            L->>VM: vm.answer
        end
    end
```

## Конфигурация

```bash
EVALUATOR_ENABLED=1           # включить критика (по умолчанию)
EVAL_SKEPTICISM=mid           # low|mid|high
EVAL_EFFICIENCY=mid           # low|mid|high — бюджет токенов
EVAL_MAX_REJECTIONS=2         # лимит отклонений
MODEL_EVALUATOR=...           # отдельная модель (иначе — основная агента)
```

## Ключевые файлы

| Файл | Экспорты |
|---|---|
| `agent/evaluator.py` | `evaluate_completion`, `check_quoted_values_verbatim`, `EvaluateCompletion` sig |
| `agent/dspy_lm.py` | `DispatchLM` — используется для вызова |
| `data/evaluator_program.json` | Скомпилированная программа (см. [04](04-dspy-optimization.md)) |
| `data/dspy_eval_examples.jsonl` | Собранные примеры для COPRO |

## Тесты

`tests/test_evaluator.py` покрывает:
- `check_quoted_values_verbatim` — trailing punctuation match.
- `evaluate_completion` — fail-open на ошибках DSPy/LLM.
- Rejection loop — cap на `EVAL_MAX_REJECTIONS`.
- Различные уровни `skepticism`.
