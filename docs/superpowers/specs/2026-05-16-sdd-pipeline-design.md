---
title: SDD Pipeline — Design Spec
date: 2026-05-16
status: Draft
review:
  spec_hash: 09814fab2043a1f3
  last_run: 2026-05-16
  phases:
    structure:   { status: passed }
    coverage:    { status: passed }
    clarity:     { status: passed }
    consistency: { status: passed }
  findings:
    - id: F-001
      phase: coverage
      severity: CRITICAL
      section: Scope
      section_hash: bf0f5ba2f0781ed9
      text: "Противоречие: ## Scope включал `agent/prompt.py` как изменяемый файл, но ## Files Unchanged и таблица ## Files Changed не включали его."
      verdict: fixed
      verdict_at: 2026-05-16
    - id: F-002
      phase: clarity
      severity: WARNING
      section: Constraints & Edge Cases
      section_hash: 29c914c94d47746e
      text: "«при необходимости можно добавить лёгкий scoring позже» — нет критерия, при каком условии это необходимо."
      verdict: fixed
      verdict_at: 2026-05-16
    - id: F-003
      phase: clarity
      severity: WARNING
      section: SECURITY + SCHEMA — интеграция в SDD-шаг
      section_hash: 9bd14105ce05b130
      text: "VALIDATE (старая фаза) и VERIFY (новая) используются в одном документе без явного указания переименования."
      verdict: fixed
      verdict_at: 2026-05-16
---

# SDD Pipeline — Design Spec

**Date:** 2026-05-16
**Status:** Draft

## Problem

Текущий пайплайн SQL-центричен и жёстко связан с конкретными фазами:
`RESOLVE → TEST_GEN → SQL_PLAN → SECURITY → SCHEMA → VALIDATE → EXECUTE → ANSWER → EVALUATE`.

Проблемы:
- `RESOLVE` и `SQL_PLAN` избыточны при наличии единой фазы планирования
- Задачи не всегда SQL — архитектура не расширяема на другие типы
- `TDD_ENABLED` — опциональный флаг, тесты не являются first-class citizen
- `LEARN` не накапливается через циклы системно — сессионные правила теряются
- `eval_log` не содержит контекст `PREPHASE` и итоговый `LEARN`
- `EVALUATOR` запускается всегда в фоне, даже при успехе

## Goal

Переработать пайплайн вокруг **SDD (Spec-Driven Development)**:
- Единая фаза `SDD` заменяет `RESOLVE` + `SQL_PLAN`
- `TEST_GEN` становится обязательным отдельным LLM-вызовом после `SDD` (не опциональный флаг)
- Поддержка task_type: пайплайн адаптируется под тип задачи из `PREPHASE`
- Cumulative `LEARN`: каждый цикл получает правила всех предыдущих циклов
- `eval_log` содержит: `PREPHASE` + полный trace + итоговый `learn_ctx`
- `EVALUATOR` запускается только при исчерпании `MAX_STEPS`
- `SDD_ENABLED` заменяет `TDD_ENABLED`; в перспективе — всегда включён

## Scope

Изменения затрагивают:
- `agent/pipeline.py` — полная переработка основного цикла
- `agent/models.py` — новые модели `SddOutput`, `PlanStep`, `TestOutput`
- `agent/prephase.py` — добавить `task_type` в `PrephaseResult`
- `data/prompts/` — новые промпты `sdd.md`, `test_gen.md` (ревизия `test_gen.md`)
- `.env.example` — добавить per-phase model vars
- `agent/evaluator.py` — изменить сигнатуру входа (добавить `learn_ctx`, `prephase`)
- `scripts/propose_optimizations.py` — обновить парсинг `eval_log`

Не затрагивают: `agent/llm.py`, `agent/sql_security.py`, `agent/schema_gate.py`, `agent/test_runner.py`, `agent/trace.py`.

---

## Design

### Pipeline Schema

```
PREPHASE
  → PrephaseResult { task_type, task_text, agents_md, schema_digest, … }
  → prephase_snapshot = serialize(PrephaseResult)  # собирается здесь, пишется в eval_log в конце

learn_ctx: list[str] = []   # накапливается через все циклы

ЦИКЛ (до MAX_STEPS):

  SDD [LLM, получает learn_ctx]
    → SddOutput { spec, plan: list[PlanStep], agents_md_refs }
    → SECURITY check на plan steps типа "sql"
        ✗ → LEARN → learn_ctx.append → continue
    → SCHEMA check на plan steps типа "sql"
        ✗ → LEARN → learn_ctx.append → continue
    ✓ →

  TEST_GEN [LLM, от SDD.spec + task_type]
    → TestOutput { sql_tests, answer_tests }

  EXECUTE [диспетчер по task_type]
    sql   → vm.exec(query) per PlanStep
    other → соответствующий executor

  VERIFY [EXPLAIN + sql_tests | тип-специфичная проверка]
    ✗ → LEARN → learn_ctx.append → continue (новый цикл, новый SDD)
    ✓ →

  ANSWER [LLM]
  VERIFY_ANSWER [answer_tests]
    ✗ → LEARN → learn_ctx.append → retry ANSWER (skip_sql, тот же цикл)
    ✓ → SUCCESS
         eval_log += { trace, learn_ctx, outcome: "ok" }
         vm.answer() → break

MAX_STEPS исчерпаны:
  EVALUATOR [LLM] → лучший цикл из trace
  eval_log += { trace, learn_ctx, outcome: "fail", evaluator }
  vm.answer(best_step_answer | clarification)
```

### LEARN — правила накопления

- `learn_ctx: list[str]` — список правил, по одному на каждый LEARN-вызов
- Передаётся в SDD каждого нового цикла как `# ACCUMULATED RULES` блок
- Не ограничен числом (в отличие от текущих `session_rules[-3:]`)
- **Итоговый `learn_ctx`** записывается в `eval_log` вне зависимости от исхода

### PREPHASE — определение task_type

`PrephaseResult` получает новое поле `task_type: str`.

Логика определения (в `prephase.py`):
- Если в agents.md/schema есть SQL-таблицы и задача упоминает продукты/SKU/инвентарь → `"sql"`
- Если задача на чтение файла из VM → `"read"`
- Если задача на вычисление без DB → `"compute"`
- Default → `"sql"` (обратная совместимость)

`task_type` влияет на:
- Промпт SDD (SQL-специфичные инструкции vs общие)
- EXECUTE диспетчер (выбор executor)
- VERIFY логику (EXPLAIN только для sql)
- TEST_GEN промпт (тип тестов)

### Pydantic-модели

```python
class PlanStep(BaseModel):
    type: Literal["sql", "exec", "read", "compute"]
    description: str
    query: str | None = None       # для type="sql"
    operation: str | None = None   # для других типов
    args: list[str] = []

class SddOutput(BaseModel):
    reasoning: str
    spec: str                      # что должен содержать ответ
    plan: list[PlanStep]           # шаги по порядку
    agents_md_refs: list[str] = []

class TestOutput(BaseModel):
    reasoning: str
    sql_tests: str                 # def test_sql(results): …
    answer_tests: str              # def test_answer(sql_results, answer): …
```

Удаляются: `ResolveOutput`, `ResolveCandidate` (RESOLVE фаза убирается).
`TestGenOutput` переименовывается в `TestOutput`.

### SDD промпт (data/prompts/sdd.md)

Объединяет логику `sql_plan.md` + часть `resolve.md`:
- Получает: task_text, task_type, agents_md, schema_digest, rules, learn_ctx, security_gates
- Генерирует: spec (что вернуть), plan (шаги с типами), agents_md_refs
- Для `task_type=sql`: первые шаги плана могут быть discovery-запросами (DISTINCT/LIKE) — RESOLVE больше не нужен
- Правила из `learn_ctx` вставляются как `# ACCUMULATED RULES` в начало user-сообщения

### TEST_GEN промпт (data/prompts/test_gen.md)

- Получает: SDD.spec, task_type, task_text
- Генерирует: `sql_tests` + `answer_tests` (Python-функции)
- Для `task_type != sql`: `sql_tests` = `def test_sql(results): pass`

### EVALUATOR — изменение поведения

**Было:** запускается всегда в фоновом потоке после каждой задачи.
**Стало:** запускается только при исчерпании `MAX_STEPS`.

Вход `EvalInput` расширяется:
```python
class EvalInput(BaseModel):
    task_id: str
    task_text: str
    task_type: str                  # NEW
    prephase: dict                  # NEW — сериализованный PrephaseResult
    learn_ctx: list[str]            # NEW — накопленные правила
    sgr_trace: list[dict]
    cycles: int
    final_outcome: str
```

Задача EVALUATOR при `outcome=fail`: выбрать лучший цикл из trace (по частичному успеху) и вернуть `best_cycle_idx` + `best_answer`.

### eval_log запись

```json
{
  "task_id": "t01",
  "task_text": "…",
  "task_type": "sql",
  "prephase": { "agents_md": "…", "schema_digest": {…}, … },
  "trace": [
    { "cycle": 1, "sdd": {…}, "verify": "fail", "learn": "rule…" },
    { "cycle": 2, "sdd": {…}, "verify": "ok", "answer": {…} }
  ],
  "learn_ctx": ["rule from cycle 1", …],
  "outcome": "ok",
  "evaluator": null
}
```

При `outcome=fail`:
```json
{
  …,
  "outcome": "fail",
  "evaluator": { "best_cycle": 1, "best_answer": "…", "score": 0.6 }
}
```

### SECURITY + SCHEMA — интеграция в SDD-шаг

`check_sql_queries` и `check_schema_compliance` вызываются сразу после парсинга `SddOutput.plan`, до `TEST_GEN`. Проверяются только шаги с `type="sql"` (шаги других типов проверку не проходят). Ошибка → `LEARN` → `learn_ctx.append` → `continue` (следующий цикл).

`EXPLAIN` (ранее фаза `VALIDATE`, переименована в `VERIFY`) остаётся частью `VERIFY` после `EXECUTE` — не меняется.

### Model Configuration

Каждая LLM-фаза пайплайна использует отдельную env-переменную модели. Если переменная не задана — fallback на `MODEL`.

| Env var | Фаза | LLM-вызов |
|---------|------|-----------|
| `MODEL_SDD` | SDD | генерация spec + plan |
| `MODEL_TEST_GEN` | TEST_GEN | генерация sql_tests + answer_tests |
| `MODEL_EXECUTOR` | ANSWER | синтез итогового ответа пользователю |
| `MODEL_LEARN` | LEARN | извлечение правила из ошибки |

Уже существующие: `MODEL_EVALUATOR` (EVALUATOR-фаза), `MODEL_FALLBACK` (fallback при исчерпании тиров).

Логика выбора в `llm.py` (`call_llm(phase: str, …)`):
```python
phase_model_map = {
    "sdd":      os.getenv("MODEL_SDD"),
    "test_gen": os.getenv("MODEL_TEST_GEN"),
    "executor": os.getenv("MODEL_EXECUTOR"),
    "learn":    os.getenv("MODEL_LEARN"),
    "evaluator": os.getenv("MODEL_EVALUATOR"),
}
model = phase_model_map.get(phase) or os.getenv("MODEL")
```

`agent/llm.py` получает новый обязательный параметр `phase: str`. Все вызовы `call_llm(...)` в `pipeline.py` обновляются.

---

## Files Changed

| File | Change |
|------|--------|
| `agent/pipeline.py` | Полная переработка: `run_pipeline()` новый цикл, убрать `run_resolve`, добавить `_run_sdd`, `_run_test_gen` (ревизия), cumulative `learn_ctx`, `EVALUATOR` только при fail |
| `agent/models.py` | ADD `PlanStep`, `SddOutput`, `TestOutput`; REMOVE `ResolveOutput`, `ResolveCandidate`; RENAME `TestGenOutput` → `TestOutput` |
| `agent/prephase.py` | ADD `task_type: str` в `PrephaseResult`; ADD логику определения task_type |
| `agent/resolve.py` | DELETE (фаза убирается) |
| `data/prompts/sdd.md` | NEW — объединяет sql_plan + resolve логику |
| `data/prompts/test_gen.md` | REVISE — принимает SDD.spec, адаптируется под task_type |
| `data/prompts/sql_plan.md` | DELETE (заменён sdd.md) |
| `data/prompts/resolve.md` | DELETE (заменён sdd.md) |
| `agent/evaluator.py` | MODIFY `EvalInput` — добавить `task_type`, `prephase`, `learn_ctx`; изменить логику выбора лучшего шага |
| `scripts/propose_optimizations.py` | MODIFY парсинг `eval_log` под новую структуру |
| `agent/llm.py` | ADD параметр `phase: str` в `call_llm()`; ADD per-phase model lookup из env |
| `.env.example` | ADD `MODEL_SDD`, `MODEL_TEST_GEN`, `MODEL_EXECUTOR`, `MODEL_LEARN` |

## Files Unchanged

- `agent/sql_security.py`
- `agent/schema_gate.py`
- `agent/test_runner.py`
- `agent/trace.py`
- `agent/json_extract.py`
- `agent/prompt.py`

---

## Constraints & Edge Cases

- **task_type default = "sql"** — обратная совместимость со всеми текущими задачами
- **learn_ctx без лимита** — текущий лимит `session_rules[-3:]` убирается; риск раздувания контекста при большом MAX_STEPS; смягчение: каждый LEARN-вывод ≤ 500 токенов
- **EVALUATOR только при fail** — при успехе eval_log не получает LLM-scored оценку; если нужна оценка при `outcome="ok"` и `cycles > 1` — активировать через `EVAL_ON_SUCCESS=1`
- **RESOLVE убирается** — SDD.plan должен включать discovery-шаги при неизвестных значениях; промпт sdd.md должен явно это предписывать
- **SQL_PLAN убирается** — agents_md_refs теперь генерирует SDD; тест на корректность refs остаётся (пустой refs при наличии index-terms → LEARN)
- **Non-SQL executor** — для `task_type != sql` executor-диспетчер MVP: только `sql` и `read` (чтение файла из VM); остальные типы → clarification

## Out of Scope

- Параллельное выполнение шагов плана (SDD.plan всегда последовательный)
- Multi-agent выполнение
- Хранение learn_ctx между сессиями (только в рамках одного запуска)
- Изменение `agent/mock_vm.py` и mock validation (совместимы с новым пайплайном as-is)

## Known Limitations

- SDD генерирует spec + plan за один LLM-вызов: при сложных задачах один вызов может давать неточный plan; смягчение — промпт sdd.md требует chain-of-thought в `reasoning`
- `task_type` определяется эвристически в PREPHASE — возможны ошибки классификации для гибридных задач
- EVALUATOR при fail выбирает "лучший цикл" по эвристике (частичный успех тестов); качество выбора зависит от качества trace-логирования
