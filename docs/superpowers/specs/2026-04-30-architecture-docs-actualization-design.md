# Architecture Docs Actualization Design

## Goal

Привести `docs/architecture/` в соответствие с текущим состоянием кодовой базы после рефакторинга в Hub-and-Spoke мультиагентную архитектуру (апрель 2026). Изменения распределяются по существующим файлам без добавления нового.

## Контекст расхождений

С момента последнего обновления документации были реализованы:
- **Hub-and-Spoke рефакторинг**: `agent/orchestrator.py` + `agent/agents/` (9 агентов) + `agent/contracts/__init__.py`
- **Contract phase**: `agent/contract_phase.py`, `data/default_contracts/`, `data/prompts/`
- **Knowledge Graph**: `agent/wiki_graph.py`, `data/wiki/graph.json`, два пути заполнения
- **GEPA backend**: `agent/optimization/` (CoproBackend + GepaBackend), `--target contract`
- **Evaluator wiki injection**: FIX-367 — `reference_patterns` + `graph_insights` в EvaluateCompletion
- Удаление `load_wiki_base` из pipeline (FIX-346/350)

---

## Файл 1: `README.md`

### Изменение 1.1 — Диаграмма «Дерево модулей»

Заменить узел `agent_init[agent/__init__.py]` на трёхуровневую структуру:

```
main → agent_init[agent/__init__.py\n(re-export shim)]
agent_init → orchestrator[agent/orchestrator.py]
orchestrator → contracts[agent/contracts/__init__.py\nPydantic v2 contracts]
orchestrator → agents_pkg[agent/agents/\n9 isolated agents]
agents_pkg → classifier_a[ClassifierAgent]
agents_pkg → wiki_a[WikiGraphAgent]
agents_pkg → planner_a[PlannerAgent]
agents_pkg → executor_a[ExecutorAgent]
agents_pkg → security_a[SecurityAgent]
agents_pkg → stall_a[StallAgent]
agents_pkg → compaction_a[CompactionAgent]
agents_pkg → step_guard_a[StepGuardAgent]
agents_pkg → verifier_a[VerifierAgent]
```

Остальные связи (loop → dispatch, loop → evaluator и т.д.) сохраняются без изменений.

### Изменение 1.2 — Таблица «Где что лежит»

Добавить две строки:

| Путь | Содержимое |
|---|---|
| `agent/agents/` | 9 изолированных агентов-обёрток (security, stall, compaction, step_guard, classifier, wiki_graph, verifier, planner, executor) |
| `agent/contracts/` | Typed Pydantic v2 контракты — единственный shared import между агентами |

### Изменение 1.3 — Таблица «Ключевые архитектурные решения»

Добавить строку:

| **Hub-and-Spoke Agents** | `agent/orchestrator.py` координирует 9 агентов через typed Pydantic contracts (`agent/contracts/`) | Изоляция зависимостей, тестируемость, DI для security/stall/evaluator |

---

## Файл 2: `01-execution-flow.md`

### Изменение 2.1 — Flowchart `run_agent`

Текущая диаграмма `run_agent: конвейер одной задачи` отражает монолитный `__init__.py`. Заменить на агентную структуру:

```
In([task_text]) → Prephase[run_prephase]
Prephase → PreResult[PrephaseResult]
PreResult → ClassifierAgent[ClassifierAgent.run\nроутинг + выбор модели]
ClassifierAgent → TaskType[ClassificationResult\ntask_type + model + cfg]

TaskType -->|PREJECT| PrejectShortcut[build_system_prompt\nrun_loop прямо]
TaskType -->|остальные| WikiAgent[WikiGraphAgent.read\npatterns + graph nodes]

WikiAgent → PlannerAgent[PlannerAgent.run\nprompt + addendum + contract]
PlannerAgent → ExecutionPlan[ExecutionPlan\nbase_prompt + addendum\n+ contract + route]

ExecutionPlan → Loop[run_loop ≤30 steps]
Loop → Out([token stats])
```

### Изменение 2.2 — Добавить примечание про Contract phase

Рядом с блоком PlannerAgent добавить примечание (не отдельный узел flowchart, а текстовая врезка):

**Contract phase** (опционально, `CONTRACT_ENABLED=1`): PlannerAgent внутри вызывает `negotiate_contract()` из `agent/contract_phase.py`. LLM-переговоры executor/evaluator ролей по шаблонам из `data/prompts/{task_type}/`. Результат — объект `Contract` с `plan_steps` и `success_criteria` — возвращается в `ExecutionPlan.contract` и передаётся в `run_loop` для пошаговой валидации через `StepGuardAgent`.

### Изменение 2.3 — Таблица «Ключевые файлы»

| Файл | Роль |
|---|---|
| `agent/__init__.py` | Re-export shim: `from .orchestrator import run_agent, write_wiki_fragment` |
| `agent/orchestrator.py` | Hub-and-Spoke pipeline: координирует ClassifierAgent → WikiGraphAgent → PlannerAgent → run_loop |
| `agent/contracts/__init__.py` | Typed Pydantic v2 контракты между агентами |
| `agent/agents/` | 9 изолированных агентов-обёрток |

---

## Файл 3: `04-dspy-optimization.md`

### Изменение 3.1 — Contract phase DSPy

Добавить раздел **«Contract phase: дополнительные сигнатуры»** после секции про COPRO/GEPA:

- `ContractExecutor` signature: генерирует `plan_steps` и `success_criteria` для executor-роли
- `ContractEvaluator` signature: верифицирует план с evaluator-роли
- Пример коллекции: `data/dspy_contract_examples.jsonl` (пишется только при `is_default=False`)
- Порог: ≥30 контрактных примеров → `uv run python scripts/optimize_prompts.py --target contract`
- Программы: `data/contract_executor_program.json`, `data/contract_evaluator_program.json`

### Изменение 3.2 — GEPA в основном workflow-диаграмме

В существующей диаграмме `flowchart TB` блок `Copro[COPRO...]` заменить на разветвление:

```
Optimize --> BackendSel{OPTIMIZER_<TARGET>?}
BackendSel -->|copro (default)| Copro[COPRO\nbreadth×depth\nprompt refinement]
BackendSel -->|gepa| Gepa[GEPA\nGenetic-Pareto\nReflective Evolution]
Copro --> Compiled[data/*_program.json]
Gepa --> Compiled
Gepa -.pareto frontier.-> Pareto[data/<target>_program_pareto/]
```

### Изменение 3.3 — Таблица «Ключевые файлы»

Добавить:

| `agent/optimization/` | `CoproBackend`, `GepaBackend`, `OptimizerProtocol`, `metrics.py`, `feedback.py` |
| `data/dspy_contract_examples.jsonl` | Собранные примеры contract phase |
| `data/contract_executor_program.json` | Скомпилированная executor-программа |
| `data/contract_evaluator_program.json` | Скомпилированная evaluator-программа |

---

## Файл 4: `06-evaluator.md`

### Изменение 4.1 — Новая секция «Wiki + Graph injection»

Добавить после секции «Per-task-type evaluator»:

**Wiki + Graph injection (FIX-367)**: `evaluate_completion()` получает два дополнительных InputField:
- `reference_patterns`: содержимое `data/wiki/pages/<task_type>.md` (Successful patterns + Verified refusals)
- `graph_insights`: top-K релевантных узлов из `wiki_graph.retrieve_relevant()`

Оба поля ADVISORY — при конфликте с хардкодированными INBOX/ENTITY правилами побеждают правила. При любом сбое чтения — пустая строка (fail-open).

### Изменение 4.2 — Обновить блок `EvaluateCompletion signature`

Добавить в Input:
```
  - reference_patterns  : str — wiki page content (optional, "" if disabled)
  - graph_insights      : str — top-K graph nodes (optional, "" if disabled)
  - account_evidence    : str — INBOX/entity evidence (hardcoded gate)
  - inbox_evidence      : str — inbox-specific evidence
```

### Изменение 4.3 — Конфигурация

Добавить env vars:
```bash
EVALUATOR_WIKI_ENABLED=1      # инъекция wiki страниц (по умолчанию 1)
EVALUATOR_WIKI_MAX_CHARS=3000 # лимит символов wiki-контекста
EVALUATOR_GRAPH_TOP_K=5       # кол-во узлов графа (требует WIKI_GRAPH_ENABLED=1)
```

---

## Файл 5: `07-wiki-memory.md`

### Изменение 5.1 — Убрать `load_wiki_base` из диаграммы «Инъекция в prompt»

`load_wiki_base` удалена (FIX-346/350): entity-catalog injection была избыточна, поскольку FIX-346/350 теперь требуют force-read-before-write. Диаграмма показывает только `load_wiki_patterns (task_type)`.

### Изменение 5.2 — Новая секция «Knowledge Graph»

Крупнейшее дополнение в файле. Структура:

**Граф**: `data/wiki/graph.json`
- Узлы: `insight`, `rule`, `pattern`, `antipattern` с полями `{tags, confidence, uses, last_seen}`
- Рёбра: `requires`, `conflicts_with`, `generalizes`, `precedes`

**Два пути заполнения:**
1. LLM-extractor в `run_wiki_lint`: `_llm_synthesize` возвращает `(markdown, deltas)`. Промпт просит модель приложить fenced ```json {graph_deltas: ...}``` после страницы. Fail-open: невалидный JSON → пишем только markdown. Гейт: `WIKI_GRAPH_AUTOBUILD=1`
2. Pattern-extractor + confidence feedback в `main.py` после `end_trial()`: `score=1.0` → `bump_uses` на узлы из prompt + `add_pattern_node` от `step_facts`; `score=0.0` → `degrade_confidence(epsilon)`. Гейт: `WIKI_GRAPH_FEEDBACK=1`

**Retrieval**: `retrieve_relevant_with_ids(graph, task_type, task_text, top_k)` — scoring = tag_overlap + text-token overlap + confidence × log(uses). Читается в трёх местах:
- System prompt агента (`agent/__init__.py` → orchestrator)
- DSPy addendum (`prompt_builder.py:graph_context` InputField)
- Evaluator (`evaluator.py:_load_graph_insights`)

Все три точки чтения гейчены `WIKI_GRAPH_ENABLED=1`.

**Graph feedback loop:**
```
end_trial(score=1.0) → bump_uses(injected_node_ids) + add_pattern_node
end_trial(score=0.0) → degrade_confidence(injected_node_ids, epsilon)
```
`stats["graph_injected_node_ids"]` записывается в `run_loop` и читается в `main.py`.

**Конфигурация:**
```bash
WIKI_GRAPH_ENABLED=1              # чтение в prompt/addendum/evaluator
WIKI_GRAPH_TOP_K=5                # кол-во узлов при retrieval
WIKI_GRAPH_AUTOBUILD=1            # LLM-extractor во время lint
WIKI_GRAPH_FEEDBACK=1             # confidence feedback post-trial
WIKI_GRAPH_CONFIDENCE_EPSILON=0.05 # шаг degrade
WIKI_GRAPH_MIN_CONFIDENCE=0.1     # минимум при degrade
```

**Ключевые файлы (добавить в таблицу):**

| `agent/wiki_graph.py` | `load_graph`, `save_graph`, `retrieve_relevant_with_ids`, `bump_uses`, `degrade_confidence`, `merge_updates` |
| `data/wiki/graph.json` | Персистентный граф знаний (committed + runtime-updated) |
| `scripts/purge_research_contamination.py` | Очистка contaminated узлов из графа |
| `scripts/print_graph.py` | Инспекция графа: `--all`, `--tag`, `--edges` |

---

## Что НЕ меняется

- `02-llm-routing.md` — четырёхуровневый dispatch без изменений
- `03-prompt-system.md` — `build_system_prompt`, prephase, few-shot pair — без изменений
- `05-security-stall.md` — security.py, stall.py — без изменений (только `_INJECTION_RE` переехал в security.py, но это внутренний detail)
- `08-harness-protocol.md` — proto/PCM — без изменений
- `09-observability.md` — tracer, log_compaction — без изменений
