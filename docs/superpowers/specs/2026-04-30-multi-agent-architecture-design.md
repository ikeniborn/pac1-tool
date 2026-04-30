# Multi-Agent Architecture: Hub-and-Spoke

**Date:** 2026-04-30  
**Status:** Approved  
**Scope:** Рефакторинг монолитного агента в 10 изолированных агентов с типизированными контрактами (in-process)

---

## 1. Контекст

Текущая архитектура — монолит с God Object `loop.py` (2442 строки). Модули связаны прямыми импортами, бизнес-логика перемешана с диспетчеризацией, безопасностью и stall-recovery. Цель: изолировать агентов друг от друга через типизированные Pydantic-контракты, сохранив все существующие функции.

**Ключевые ограничения:**
- In-process изоляция (не subprocess, не сеть)
- Существующие модули не переписываются — агенты являются обёртками
- Все env-флаги и DSPy-программы продолжают работать

---

## 2. Архитектура

### Hub-and-Spoke

```
                    ┌──────────────────────────────────────┐
                    │             Orchestrator              │
                    │  agent/orchestrator.py                │
                    └───────────────────┬──────────────────┘
                                        │ TaskInput
          ┌─────────────────────────────┼──────────────────────┐
          ▼                             ▼                      ▼
 ┌─────────────────┐       ┌────────────────────┐   ┌──────────────────┐
 │ ClassifierAgent │       │  WikiGraphAgent     │   │  PlannerAgent    │
 │ classifier.py   │       │  wiki.py            │   │  contract_phase  │
 │ task_types.py   │       │  wiki_graph.py      │   │  prompt_builder  │
 └────────┬────────┘       └─────────┬──────────┘   │  _route_task     │
          │ ClassificationResult     │ WikiContext   └───────┬──────────┘
          └──────────────────────────┴───────────────────────┘
                                        │ ExecutionPlan
                                        │ (содержит Contract)
                                        ▼
                    ┌──────────────────────────────────────┐
                    │           ExecutorAgent               │
                    │  loop.py (цикл ≤30 шагов + dispatch) │
                    │                                       │
                    │  каждый шаг:                          │
                    │  step → SecurityAgent → SecurityCheck │
                    │       → StepGuardAgent → StepValid.   │◄──┐
                    │                                       │   │ rejected +
                    │  при stall:                           │   │ feedback
                    │  state → StallAgent → StallHint       │   │
                    │                                       │   │
                    │  при бюджете токенов:                 │   │
                    │  log → CompactionAgent → CompactedLog │   │
                    │                                       │   │
                    │  при ReportTaskCompletion:            │   │
                    │  report ──────────────────────────────┼───┤
                    └──────────────────┬────────────────────┘   │
                                       │ CompletionRequest      │
                                       ▼                        │
                    ┌──────────────────────────────────────┐    │
                    │           VerifierAgent               │    │
                    │  evaluator.py                         │    │
                    │  hard-gates + DSPy review             │    │
                    └──────────────────┬────────────────────┘    │
                                       │ VerificationResult      │
                                       │ approved=False ─────────┘
                                       │ approved=True
                                       ▼
                    ┌──────────────────────────────────────┐
                    │         ExecutionResult               │
                    │  → Orchestrator                       │
                    │  → WikiGraphAgent.write_feedback()    │
                    └──────────────────────────────────────┘
```

**VerifierAgent** — часть петли ExecutorAgent, не финальный шаг оркестратора. При `approved=False` фидбек возвращается в цикл как user-сообщение, шаги продолжаются.

**StepGuardAgent** проверяет соответствие каждого шага `Contract` из `ExecutionPlan` до dispatch.

`prephase` и `WikiGraphAgent.read` запускаются параллельно в оркестраторе (они независимы).

---

## 3. Файловая структура

```
agent/
  orchestrator.py          ← новый, заменяет pipeline в __init__.py
  __init__.py              ← re-export: from agent.orchestrator import run_agent
  contracts/
    __init__.py            ← все Pydantic-контракты (единственный shared import)
  agents/
    classifier_agent.py    ← обёртка над classifier.py
    wiki_graph_agent.py    ← обёртка над wiki.py + wiki_graph.py
    planner_agent.py       ← обёртка над contract_phase + prompt_builder + _route_task
    executor_agent.py      ← обёртка над loop.py (цикл + dispatch)
    security_agent.py      ← обёртка над security.py
    stall_agent.py         ← обёртка над stall.py
    compaction_agent.py    ← обёртка над log_compaction.py
    step_guard_agent.py    ← обёртка над contract_monitor.py
    verifier_agent.py      ← обёртка над evaluator.py
```

**Правило изоляции:** агенты импортируют только из `agent.contracts` и своих внутренних модулей. Оркестратор — единственный, кто импортирует агентов.

---

## 4. Типизированные контракты

Все модели живут в `agent/contracts/__init__.py`.

```python
# Вход для всего pipeline
class TaskInput(BaseModel):
    task_text: str
    harness_url: str
    trial_id: str

# ClassifierAgent
class ClassificationResult(BaseModel):
    task_type: str
    model: str
    model_cfg: dict
    confidence: float

# WikiGraphAgent.read
class WikiReadRequest(BaseModel):
    task_type: str
    task_text: str

class WikiContext(BaseModel):
    patterns_text: str
    graph_section: str
    injected_node_ids: list[str]

# PlannerAgent
class PlannerInput(BaseModel):
    task_input: TaskInput
    classification: ClassificationResult
    wiki_context: WikiContext

class ExecutionPlan(BaseModel):
    base_prompt: str
    addendum: str
    contract: Contract           # из contract_models.py
    route: Literal["EXECUTE", "DENY", "CLARIFY", "UNSUPPORTED"]
    in_tokens: int
    out_tokens: int

# SecurityAgent (per-step)
class SecurityRequest(BaseModel):
    tool_name: str
    tool_args: dict
    task_type: str
    message_text: str | None = None

class SecurityCheck(BaseModel):
    passed: bool
    violation_type: str | None = None  # "injection" | "write_scope" | "contamination"
    detail: str | None = None

# StepGuardAgent (per-step)
class StepGuardRequest(BaseModel):
    step_index: int
    tool_name: str
    tool_args: dict
    contract: Contract

class StepValidation(BaseModel):
    valid: bool
    deviation: str | None = None
    suggestion: str | None = None

# StallAgent
class StallRequest(BaseModel):
    step_index: int
    fingerprints: list[str]
    error_counts: dict[str, int]
    steps_without_write: int

class StallResult(BaseModel):
    detected: bool
    hint: str | None = None
    escalation_level: int = 0  # 0=нет, 1=hint, 2=эскалация, 3=re-эскалация

# CompactionAgent
class CompactionRequest(BaseModel):
    messages: list[dict]
    step_facts: list[dict]
    preserve_prefix_len: int
    token_budget: int

class CompactedLog(BaseModel):
    messages: list[dict]
    tokens_saved: int

# VerifierAgent
class CompletionRequest(BaseModel):
    report: ReportTaskCompletion  # из models.py
    task_type: str
    task_text: str
    wiki_context: WikiContext
    contract: Contract

class VerificationResult(BaseModel):
    approved: bool
    feedback: str | None = None
    rejection_count: int
    hard_gate_triggered: str | None = None  # "verbatim" | "grounding" | "write_scope"

# ExecutorAgent
class ExecutorInput(BaseModel):
    task_input: TaskInput
    plan: ExecutionPlan
    wiki_context: WikiContext
    prephase: PrephaseResult      # из prephase.py

class ExecutionResult(BaseModel):
    status: Literal["completed", "denied", "timeout", "error"]
    outcome: str
    token_stats: dict[str, int]
    step_facts: list[dict]
    injected_node_ids: list[str]
    rejection_count: int

# WikiGraphAgent.write_feedback
class WikiFeedbackRequest(BaseModel):
    task_type: str
    task_text: str
    execution_result: ExecutionResult
    wiki_context: WikiContext
    score: float  # 1.0 = success, 0.0 = failure
```

---

## 5. Orchestrator

**Примечание о синхронности:** текущий `run_agent()` синхронный, `main.py` вызывает его из `ThreadPoolExecutor`. Параллельный prephase + wiki read реализуется через `ThreadPoolExecutor` внутри оркестратора (не `asyncio`), чтобы не менять вызывающий код. `async def` в псевдокоде ниже — иллюстрация параллелизма, не буквальная реализация.

**Примечание о prephase:** реальная сигнатура `run_prephase(vm: PcmRuntimeClientSync, task_text: str)`, где `vm` создаётся из `harness_url`. Оркестратор создаёт `vm` перед параллельным запуском.

**Примечание о rejection_count:** `ExecutorAgent` накапливает счётчик отказов Verifier-а across multiple `ReportTaskCompletion` внутри одного цикла. `VerificationResult.rejection_count` — значение на момент этого конкретного вызова, `ExecutionResult.rejection_count` — итоговое за весь цикл.

```python
# agent/orchestrator.py (sync, параллелизм через ThreadPoolExecutor)
def run_agent(router: ModelRouter, harness_url: str, task_text: str, trial_id: str) -> dict:
    task_input = TaskInput(task_text=task_text, harness_url=harness_url, trial_id=trial_id)

    # 1. Классификация
    classification = ClassifierAgent().run(task_input)

    # Ранний выход для preject
    if classification.task_type == TASK_PREJECT:
        return _preject_result()

    # 2. Параллельно: prephase + wiki read (ThreadPoolExecutor)
    vm = PcmRuntimeClientSync(harness_url)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prephase_fut = pool.submit(run_prephase, vm, task_text)
        wiki_fut = pool.submit(WikiGraphAgent().read, WikiReadRequest(
            task_type=classification.task_type,
            task_text=task_text,
        ))
        prephase, wiki_context = prephase_fut.result(), wiki_fut.result()

    # 3. Планирование
    plan = PlannerAgent().run(PlannerInput(
        task_input=task_input,
        classification=classification,
        wiki_context=wiki_context,
    ))

    if plan.route != "EXECUTE":
        return _non_execute_result(plan.route)

    # 4. Исполнение (VerifierAgent вызывается внутри ExecutorAgent)
    result = ExecutorAgent(
        security=SecurityAgent(),
        step_guard=StepGuardAgent(),
        stall=StallAgent(),
        compaction=CompactionAgent(),
        verifier=VerifierAgent(),
    ).run(ExecutorInput(
        task_input=task_input,
        plan=plan,
        wiki_context=wiki_context,
        prephase=prephase,
    ))

    # 5. Feedback в wiki/graph
    WikiGraphAgent().write_feedback(WikiFeedbackRequest(
        task_type=classification.task_type,
        task_text=task_text,
        execution_result=result,
        wiki_context=wiki_context,
        score=1.0 if result.status == "completed" else 0.0,
    ))

    return result.token_stats
```

---

## 6. Стратегия миграции

Принцип: никакой переписки с нуля. Каждый агент — тонкая обёртка, `loop.py` очищается, не заменяется.

| Фаза | Содержание | Проверка |
|---|---|---|
| 0 | `agent/contracts/__init__.py` — все контракты | импорты без ошибок |
| 1 | Leaf-агенты: Security, Stall, Compaction, StepGuard, Classifier | unit-тесты каждого |
| 2 | `WikiGraphAgent` (read + write_feedback) | существующие wiki-тесты |
| 3 | `VerifierAgent` + `PlannerAgent` | существующие evaluator-тесты |
| 4 | `ExecutorAgent` — вынести `_route_task` в Planner, заменить прямые вызовы на DI | полный прогон benchmark |
| 5 | `orchestrator.py` — перенести pipeline из `__init__.py` | `main.py` без изменений |

**Правила:**
- Один агент = один PR
- `agent/contracts/` — единственный shared import между агентами
- Оркестратор — единственный, кто импортирует агентов
- `loop.py` не удаляется, очищается от security/stall/compaction вызовов
- Тесты на каждой фазе перед следующей

---

## 7. Что не меняется

- `main.py` — вызывает `run_agent()` как сейчас
- Все env-флаги (`WIKI_ENABLED`, `EVALUATOR_ENABLED`, и т.д.)
- DSPy-программы (`data/prompt_builder_*_program.json`, и т.д.)
- `models.json`, `task_types.json`, wiki-страницы
- gRPC/protobuf стаки (`bitgn/`)
- Все 9 PCM-инструментов агента
- `FIX-N` нумерация в CHANGELOG
