# GEPA integration & extensions — design spec

**Дата**: 2026-04-26
**Контекст**: Замена/coexistence COPRO → GEPA в трёх DSPy-цепочках PAC1-tool (`prompt_builder`, `evaluator`, `classifier`). Документ-источник: `docs/prompt-optimization-alternatives.md` (раздел "Рекомендации для PAC1-tool", Приоритет 1).

## 1. Цели и не-цели

### Цели

- Прозрачное переключение per-target между COPRO и GEPA через env-переменные (`OPTIMIZER_BUILDER`, `OPTIMIZER_EVALUATOR`, `OPTIMIZER_CLASSIFIER`) для A/B-сравнения и постепенной миграции.
- Перевести метрики на единый контракт `dspy.Prediction(score, feedback)`, где `feedback` — детерминированный текстовый сигнал, построенный из полей trace example без дополнительных LLM-вызовов.
- Поддержать ConfidenceAdapter GEPA для `classifier`, когда модель реально возвращает logprobs (OpenRouter open-weight, Ollama).
- Сохранять Pareto-фронтир GEPA рядом с main-программой для оффлайн-анализа.
- Reflection LM = task LM (`MODEL_OPTIMIZER`); опциональный `MODEL_GEPA_REFLECTION` оставлен как hook на будущее.

### Не-цели

- Не оптимизируем agent loop / dispatch / security gates — это область Trace (раздел 12 в обзорном документе), не данного spec'а.
- Не вводим LLM-judge для построения feedback на каждом примере (остаётся правило-ориентированным).
- Не реализуем surrogate-confidence (N-sample voting) для tiers без logprobs — отдельная follow-up задача.
- Не меняем формат сохранённых compiled-программ (`*_program.json`) — `agent/prompt_builder.py`/`evaluator.py`/`classifier.py` продолжают грузить их без изменений.

## 2. Архитектурный подход

Adapter-протокол + два бэкенда (вариант B из брейншторма).

### 2.1 Раскладка модулей

```
agent/optimization/
  __init__.py              # re-exports
  base.py                  # OptimizerProtocol, CompileResult, BackendError
  copro_backend.py         # CoproBackend(OptimizerProtocol)
  gepa_backend.py          # GepaBackend(OptimizerProtocol)
  feedback.py              # build_builder_feedback / _evaluator_ / _classifier_
  metrics.py               # три метрики, возвращают dspy.Prediction(score, feedback)
  budget.py                # GEPA budget resolution (auto level + override)
  logger.py                # OptimizeLogger (вынесли из scripts/optimize_prompts.py)

scripts/optimize_prompts.py  # ~150 строк: CLI, model resolve, диспатч на бэкенд per-target
```

### 2.2 Контракт `OptimizerProtocol`

```python
class OptimizerProtocol(Protocol):
    name: str  # "copro" | "gepa"
    def compile(
        self,
        program: dspy.Module,
        trainset: list[dspy.Example],
        metric: Callable,           # (ex, pred, trace) -> dspy.Prediction
        save_path: Path,
        log_label: str,
        *,
        task_lm: dspy.LM,
        prompt_lm: dspy.LM,         # та же модель, отдельный max_tokens бюджет
        adapter: dspy.Adapter,      # ChatAdapter | JSONAdapter | ConfidenceAdapter
        threads: int,
    ) -> CompileResult: ...
```

`CompileResult { compiled, pareto_programs: list[dspy.Module] | None, stats: dict }`. `pareto_programs` заполняется только GEPA-бэкендом.

### 2.3 Выбор бэкенда

```python
def _select_backend(target: str) -> OptimizerProtocol:
    kind = os.environ.get(
        f"OPTIMIZER_{target.upper()}",
        os.environ.get("OPTIMIZER_DEFAULT", "copro"),
    ).lower()
    return GepaBackend() if kind == "gepa" else CoproBackend()
```

Per-target env (`OPTIMIZER_BUILDER` и т.д.) бьёт `OPTIMIZER_DEFAULT`.

### 2.4 Что НЕ меняется

- `agent/prompt_builder.py`, `agent/evaluator.py`, `agent/classifier.py` — продолжают грузить сохранённый JSON через `predictor.load()`. Формат не меняется.
- DSPy-signatures (`PromptAddendum`, `EvaluateCompletion`, `ClassifyTask`) — без правок.
- Per-task_type passes остаются (global + per-type для каждого target'а). Backend применяется ко всем проходам.

## 3. Метрики и детерминированный feedback

### 3.1 Общая сигнатура

```python
def metric(ex: dspy.Example, pred, trace=None) -> dspy.Prediction:
    score = ...                                      # 0.0 / 0.5 / 1.0
    feedback = build_*_feedback(ex, pred, score)     # str, до ~400 символов
    return dspy.Prediction(score=score, feedback=feedback)
```

GEPA читает оба поля. COPRO берёт только `.score` через адаптер-обёртку — это сохраняет единый контракт метрик.

### 3.2 Builder feedback (`prompt_builder`)

Источник: `data/dspy_examples.jsonl`. Будут добавлены поля `stall_detected`, `write_scope_violations` (см. 5.1).

| Сигнал | Feedback (шаблон) |
|---|---|
| `score == 1.0` + ≥3 bullet | `"OK: addendum led to score=1.0; keep bullet density ≥3."` |
| `score == 1.0` + <3 bullet | `"Score=1.0 but addendum has only N bullets — terse may regress on harder cases; aim for 3-5."` |
| `score == 0.0` + `stall_detected` | `"Task failed (stall after step K). Addendum did not surface anti-loop guidance for tool=X."` |
| `score == 0.0` + `write_scope_violations` | `"Task failed: agent wrote to /Y/ but task type {tt} requires /outbox/. Addendum should encode write-scope rule."` |
| `score == 0.0` (generic) | `"Task failed. Addendum produced N bullets for task_type={tt}; consider mentioning {hint_for_tt}."` |
| addendum пуст / без bullet | `"Addendum has no bullet structure — bullets ('- ...') are required."` |

`hint_for_tt` — статический dict task_type → одна фраза-подсказка (например, `inbox: "inbox tasks require classification before write"`, `email: "email tasks must end in /outbox/"`).

### 3.3 Evaluator feedback

Источник: `data/dspy_eval_examples.jsonl`.

| Сигнал | Feedback |
|---|---|
| `predicted == expected` | `"Correct: {expected}."` |
| Predicted `yes`, expected `no`, `done_ops` пуст и outcome `OUTCOME_OK` | `"False approve: agent claimed OUTCOME_OK without any write/delete ops. Tighten the 'side-effects required' check for task_type={tt}."` |
| Predicted `yes`, expected `no`, `task_text` truncated/ambiguous | `"False approve: task_text was ambiguous/truncated and agent answered without clarification. Should have rejected → CLARIFICATION."` |
| Predicted `no`, expected `yes` | `"False reject: outcome was actually correct (benchmark score=1.0). Avoid over-skepticism on task_type={tt}; the {done_ops_short} were sufficient."` |
| `proposed_outcome` ∈ refusal-set + agent_message обоснован + score=1 | `"Correct refusal kept: {refusal_kind} matches the task constraint."` |

### 3.4 Classifier feedback

Источник: `get_classifier_trainset()` (`task_text`, `vault_hint`, `task_type`).

| Сигнал | Feedback |
|---|---|
| match | `"Correct: {task_type}."` |
| `expected=email`, `predicted=lookup` | `"Misclassified: task implies sending an email (action verb 'send/write/email'); lookup is read-only. Hint: presence of recipient name → email."` |
| `expected=inbox`, `predicted=default` | `"Misclassified: task references /inbox/ items implicitly via 'process'/'classify'/'sort'; default is too generic."` |
| `expected=temporal`, `predicted=think` | `"Misclassified: temporal markers ('next week', 'before Friday', date in task_text); think is for open-ended reasoning."` |
| Generic mismatch | `"Misclassified: predicted={p}, expected={e}. Task text contains tokens [{top_tokens}] that align with {e}."` |

Топовые confused pairs захардкожены в `feedback.py`. Остальные пары — generic шаблон.

### 3.5 Размещение

`agent/optimization/feedback.py` — три pure-функции, каждая ≤60 строк, без зависимостей от dspy-runtime. Покрываются юнит-тестами.

## 4. GEPA backend

### 4.1 Структура

```python
class GepaBackend:
    name = "gepa"

    def compile(self, program, trainset, metric, save_path, log_label, *,
                task_lm, prompt_lm, adapter, threads) -> CompileResult:
        budget_kwargs = resolve_budget()
        eff_adapter = self._maybe_confidence_adapter(program, adapter)
        dspy.configure(lm=task_lm, adapter=eff_adapter)

        teleprompter = dspy.GEPA(
            metric=metric,
            reflection_lm=prompt_lm,
            **budget_kwargs,
            num_threads=threads,
            track_stats=True,           # включает Pareto frontier
        )
        compiled = teleprompter.compile(program, trainset=trainset)

        compiled.save(str(save_path))
        pareto = self._extract_pareto(compiled)
        self._save_pareto(pareto, save_path)
        return CompileResult(compiled, pareto, stats={...})
```

### 4.2 Budget resolution (`budget.py`)

```python
def resolve_budget() -> dict:
    override = os.environ.get("GEPA_BUDGET_OVERRIDE")
    if override:
        # формат: "max_full_evals=20" или "max_metric_calls=200"
        k, _, v = override.partition("=")
        return {k.strip(): int(v.strip())}
    level = os.environ.get("GEPA_AUTO", "light").lower()  # light|medium|heavy
    return {"auto": level}
```

`auto=light` ≈ ×2 LLM-вызовов от COPRO breadth=4 depth=2. Реальная стоимость отслеживается через `OptimizeLogger` (`lm_call` events).

### 4.3 ConfidenceAdapter routing

Активируется **только** если target = classifier И модель оптимизатора возвращает logprobs:

```python
def _maybe_confidence_adapter(self, program, fallback):
    if not isinstance(program.signature, type(ClassifyTask)):
        return fallback
    if not _model_supports_logprobs():  # читает models.json: provider in {openrouter, ollama}
        return fallback
    return dspy.ConfidenceAdapter()
```

Если ConfidenceAdapter падает — fail-open до базового adapter'а с warning'ом.

### 4.4 Logprobs research — Claude Code tier

Текущее состояние (2026-04):

| Tier | logprobs | Что нужно |
|---|---|---|
| Anthropic SDK (`messages.create`) | **Нет в публичном API** | Параметр `logprobs`/`top_logprobs` отсутствует в Messages API для `claude-opus-4-7`/`claude-sonnet-4-6`. |
| Claude Code (`iclaude` subprocess) | **Нет** | CLI обёртка поверх того же API + OAuth tier. Stdout содержит только финальный текст. |
| OpenRouter | **Частично** | Для Anthropic-моделей через OR — нет (OR проксирует на Anthropic). Для open-weight (Llama, DeepSeek через TogetherAI/Fireworks) — да: `logprobs: true`, `top_logprobs: N` в request body. |
| Ollama | **Да** | Доступно в raw streaming API. |

**Что нужно проверить перед фактическим включением ConfidenceAdapter**:

1. Подтвердить статус Anthropic API на момент реализации — https://docs.anthropic.com/en/api/messages, искать `logprobs`. Anthropic периодически расширяет API.
2. Для каждой модели с `provider: "openrouter"` в `models.json` проверить https://openrouter.ai/models/<id> графу "Logprobs".
3. В `agent/dispatch.py:ollama_complete()` вытащить per-token logprobs из raw response и пробросить в DSPy LM ответ.

**Если logprobs недоступны** (наш случай для Anthropic-only стека) — surrogate confidence через self-consistency:

| Метод | Описание | Цена |
|---|---|---|
| N-sample voting | `n=5` с `temperature=0.7`, доля согласий = confidence-прокси | ×5 |
| Explicit confidence prompt | Добавить `confidence: float` outputfield в `ClassifyTask` | ×1, шумно |
| Two-pass abstain | Pass 1: классификация. Pass 2: «уверен?» yes/no | ×2 |

**Решение для PAC1-tool на старте**: surrogate-методы НЕ реализуем. ConfidenceAdapter активируется только для реальных logprobs (OpenRouter open-weight, Ollama). Для Anthropic/CC — JSONAdapter, GEPA даёт выигрыш и без logprobs (через Pareto + reflection).

**Research-эксперимент** для будущей оценки целесообразности surrogate:

```bash
make run TASKS='t01,t02,...t50'
uv run python scripts/analyze_task_types.py --confusion-matrix
```

Если confused-rate < 10% — ConfidenceAdapter не нужен. Если > 10% — рассмотреть surrogate как follow-up (отдельный FIX).

### 4.5 Pareto frontier

GEPA с `track_stats=True` хранит несколько кандидатов, оптимальных по разным subset'ам. Сохраняем рядом с main:

```
data/prompt_builder_program.json                # main (best aggregate)
data/prompt_builder_program_pareto/
    0.json
    1.json
    ...
    index.json                                  # {"0": {"score": 0.84, "covers": [...]}, ...}
```

`agent/prompt_builder.py` НЕ меняется — продолжает грузить main. Pareto-программы — для оффлайн-анализа и потенциального A/B (вне этого spec'а).

Если `OPTIMIZER_*=copro` — Pareto-каталог не создаётся (`pareto_programs=None`).

### 4.6 Failure modes

| Сценарий | Поведение |
|---|---|
| GEPA не установлен | `BackendError: GEPA not available, install with 'uv add dspy-ai[gepa]'`, exit 2 |
| ConfidenceAdapter упал | warning, fall back на JSONAdapter |
| Budget исчерпан до сходимости | GEPA сохраняет лучший на момент остановки; `run_end` со `status: "budget_exhausted"` |
| Reflection LM упала на одной мутации | GEPA внутренний retry; при повторах — `dspy_errors.jsonl` + `status: "error"` |

### 4.7 Логи

`OptimizeLogger` уже различает `target=builder/global` vs `builder/global/meta`. Добавляем:

- `target=builder/global/reflection` — для reflection LM-вызовов GEPA
- `event="gepa_pareto"` — список scores на Pareto-фронтире после compile

## 5. COPRO backend

Существующий код `_run_copro_*` переезжает в `copro_backend.py` без логических изменений:

```python
class CoproBackend:
    name = "copro"

    def compile(self, program, trainset, metric, save_path, log_label, *,
                task_lm, prompt_lm, adapter, threads) -> CompileResult:
        dspy.configure(lm=task_lm, adapter=adapter)
        teleprompter = COPRO(
            prompt_model=prompt_lm,
            metric=lambda ex, pr, t=None: metric(ex, pr, t).score,  # COPRO ждёт скаляр
            breadth=_int_env("COPRO_BREADTH", 4),
            depth=_int_env("COPRO_DEPTH", 2),
            init_temperature=_float_env("COPRO_TEMPERATURE", 0.9),
        )
        compiled = teleprompter.compile(
            program, trainset=trainset,
            eval_kwargs={"num_threads": threads, "display_progress": True, "display_table": 0},
        )
        compiled.save(str(save_path))
        return CompileResult(compiled=compiled, pareto_programs=None, stats={})
```

Единый контракт метрики (`dspy.Prediction(score, feedback)`) сохраняется — COPRO просто игнорит `.feedback`.

## 6. План миграции

Шаги независимы по логике, но порядок гарантирует, что каждый следующий полагается на инфраструктуру предыдущего. После каждого шага существующий COPRO-pipeline должен работать как раньше.

1. **Скаффолд `agent/optimization/`** — пустые файлы, `OptimizerProtocol`, перенос `OptimizeLogger` без изменения сигнатуры.
2. **Перенос метрик в `metrics.py`** — три функции, временно возвращают `dspy.Prediction(score=..., feedback="")`. Все существующие тесты проходят.
3. **`feedback.py` + юнит-тесты** — детерминированные builder'ы. Подключение в метрики. COPRO работает без изменений.
4. **Поля trace** — добавить `stall_detected`, `write_scope_violations` в `agent/dspy_examples.py:save_example()` (читается из `loop.py` stats).
5. **`copro_backend.py`** — рефакторинг `_run_copro_*` в один backend. Контрольная точка: прогнать `--target builder/evaluator/classifier` и сверить compiled JSON с pre-миграционными (smoke-test на 5 примерах). Это гарантия что миграция не сломала COPRO.
6. **`gepa_backend.py` базовый** — без ConfidenceAdapter и Pareto, только compile + save. `uv add dspy-ai[gepa]`. Прогнать `OPTIMIZER_BUILDER=gepa uv run scripts/optimize_prompts.py --target builder` на маленьком trainset (≤20 примеров).
7. **Pareto-сохранение** — каталог `*_program_pareto/` + `index.json`.
8. **ConfidenceAdapter routing** — `_model_supports_logprobs()` читает `models.json` provider; правка `dispatch.py` для пробрасывания `logprobs=True` при `provider in {openrouter, ollama}`. Fail-open.
9. **Документация** — `CLAUDE.md` (Optimization Workflow), `.env.example`, `docs/architecture/04-dspy-optimization.md`.

Шаги 1–5 — без риска, COPRO работает прежним образом. Шаги 6–8 — opt-in через env. Roll-back: убрать env-переменные.

## 7. Изменения в `scripts/optimize_prompts.py`

После миграции файл сжимается до ~150 строк. Один универсальный runner:

```python
def _run_target(target: str, program_factory, trainset_loader, metric):
    backend = _select_backend(target)
    task_lm = _LoggingDispatchLM(model, cfg, max_tokens=..., target=target)
    prompt_lm = _LoggingDispatchLM(model, cfg, max_tokens=COPRO_PROMPT_MAX_TOKENS,
                                    target=f"{target}/meta")
    adapter = dspy.ChatAdapter() if _ollama_only else dspy.JSONAdapter()
    backend.compile(
        program_factory(), trainset_loader(), metric, save_path,
        log_label=target, task_lm=task_lm, prompt_lm=prompt_lm,
        adapter=adapter, threads=COPRO_THREADS,
    )

def optimize_builder(...):
    _run_target("builder/global", lambda: dspy.Predict(PromptAddendum),
                lambda: _builder_trainset(...), _builder_metric)
    for tt in eligible_types:
        _run_target(f"builder/{tt}", ...)
```

## 8. Тесты

| Файл | Покрывает | Объём |
|---|---|---|
| `tests/test_optimization_feedback.py` | 3 builder'а × 4–6 правил каждый = ~15 unit-тестов | ~150 строк |
| `tests/test_optimization_backend_select.py` | env-роутинг `OPTIMIZER_*`; default copro; per-target бьёт default | ~50 строк |
| `tests/test_optimization_budget.py` | `resolve_budget()`: auto=light/medium/heavy + override syntax | ~30 строк |
| `tests/test_optimization_smoke.py` (slow-marked, optional) | end-to-end на 5 примерах с `DummyLM` — оба бэкенда compile без ошибок | ~80 строк |

Реальные LLM-вызовы (live GEPA/COPRO) не тестируются автоматически — проверяются вручную через smoke-run на маленьком trainset перед мерджем.

## 9. Новые env-переменные (`.env.example`)

```ini
# Optimizer selection (gepa | copro). Per-target overrides default.
OPTIMIZER_DEFAULT=copro
OPTIMIZER_BUILDER=gepa
OPTIMIZER_EVALUATOR=copro
OPTIMIZER_CLASSIFIER=gepa

# GEPA budget — auto preset; light=≈2× COPRO baseline, heavy=≈10×
GEPA_AUTO=light
# Optional fine-grained override; e.g. "max_full_evals=30" or "max_metric_calls=400"
GEPA_BUDGET_OVERRIDE=

# Optional: separate reflection model (default: same as MODEL_OPTIMIZER)
# MODEL_GEPA_REFLECTION=
```

## 10. Acceptance criteria

- `OPTIMIZER_*=copro` для всех трёх — поведение и compiled JSON эквивалентны pre-миграции (smoke-сравнение на 5 примерах).
- `OPTIMIZER_BUILDER=gepa` запускается успешно, сохраняет main + Pareto, compiled program загружается в `agent/prompt_builder.py` без падений.
- Юнит-тесты `test_optimization_feedback.py`, `test_optimization_backend_select.py`, `test_optimization_budget.py` зелёные.
- `make run TASKS='t01,t05,t11'` после переключения builder на GEPA не регрессирует — score не падает > 5%.
- Документация обновлена (`CLAUDE.md`, `.env.example`, `docs/architecture/04-dspy-optimization.md`).

## 11. Open questions / follow-ups (вне scope)

- Surrogate confidence (N-sample voting) для Anthropic/CC tier — отдельный FIX, активация по результатам confusion-matrix эксперимента (раздел 4.4).
- Использование Pareto-программ для runtime-роутинга (выбор программы под task_type из фронтира) — отдельный эксперимент.
- Trace integration (раздел 12 обзорного документа) — оптимизация всего agent loop совместно с промптами; выходит за рамки данного spec'а.
