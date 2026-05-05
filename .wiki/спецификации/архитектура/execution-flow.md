---
wiki_sources:
  - docs/architecture/01-execution-flow.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, orchestrator, loop, execution-flow]
---

# Поток выполнения (Execution Flow)

Конвейер от `make run` до вызова `vm.answer()`. Точки входа, prephase, главный loop и lifecycle одного шага.

## Основная схема

Жизненный цикл одного запуска:
1. `main.py` загружает `.env`, `.secrets`, `models.json`, соединяется с HarnessService
2. `GetBenchmark` → `StartRun` → `ThreadPoolExecutor(max_workers=PARALLEL_TASKS)`
3. Для каждой задачи: `StartTrial` → `run_agent()` → `EndTrial`
4. Итог: `SubmitRun(force=true)`

## run_agent: конвейер одной задачи

```
task_text
  → run_prephase  (tree + AGENTS.MD + context + few-shot pair)
  → ClassifierAgent.run()  (task_type + model + cfg)
  → [PREJECT → build_system_prompt → run_loop напрямую]
  → WikiGraphAgent.read()  (patterns + graph nodes)
  → PlannerAgent.run()  (prompt + addendum + contract опц.)
  → run_loop ≤30 шагов
  → return token stats
```

## Lifecycle одного шага в loop

```
step N
  → _compact_log (prefix + last 5)
  → dispatch LLM call
  → _extract_json_from_text (7-level priority)
  → NextStep (pydantic)
  → _check_stall → [retry LLM]
  → _run_pre_route (security)
  → tool dispatch:
      read/list/search → PCM call
      write/delete/move/mkdir → _check_write_scope → PCM call
      report_completion → evaluate_completion → [reject/approve] → vm.answer
  → _compact_tool_result → _extract_fact → log.append → tracer.emit
```

## Ключевые файлы

| Файл | Роль |
|---|---|
| `main.py` | CLI, harness connection, ThreadPoolExecutor |
| `agent/__init__.py` | Re-export shim |
| `agent/orchestrator.py` | Hub-and-Spoke pipeline |
| `agent/contracts/__init__.py` | Typed Pydantic контракты |
| `agent/prephase.py` | Discovery: tree, AGENTS.MD, context, few-shot |
| `agent/loop.py` | Главный loop ≤30 шагов |
| `agent/models.py` | NextStep, Req_Read, Req_Write и т.д. |
| `agent/json_extract.py` | 7-уровневое извлечение JSON |

## Ограничения

- ≤30 шагов на задачу → форс OUTCOME_ERR_INTERNAL
- `TASK_TIMEOUT_S` (default 180s) — принудительное прерывание
- `PARALLEL_TASKS` (default 1) — параллелизм
- ≤40K токенов в истории — обеспечивается log_compaction
