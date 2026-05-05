---
wiki_sources:
  - docs/superpowers/specs/2026-05-03-scripts-lifecycle-automation-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, lifecycle, preflight, postrun, maintenance]
---

# Scripts Lifecycle Automation

**Дата:** 2026-05-03 | FIX-427

Автоматизация 7 utility scripts через lifecycle модули `preflight.py` и `postrun.py`.

## Миграция scripts → agent/maintenance/

| `scripts/` (удалены) | `agent/maintenance/` (новые) |
|---|---|
| `check_graph_health.py` | `health.py` |
| `purge_research_contamination.py` | `purge.py` |
| `distill_contracts.py` | `distill.py` |
| `analyze_task_types.py` | `candidates.py` |

Остаются в `scripts/` (dev-only): `optimize_prompts.py`, `visualize_graph.py`, `print_graph.py`.

## agent/preflight.py

```
PREFLIGHT_ENABLED=1?
  → graph health check
      OK/WARN → continue
      FAIL → auto purge → re-check
               re-check OK → continue
               re-check FAIL → SystemExit(1)
  → wiki pages integrity (non-empty check)
  → wiki graph load test (SystemExit(1) if broken)
```

## agent/postrun.py

```
POSTRUN_ENABLED=1?
  → purge (idempotent) → FAIL: SystemExit(1)
  → wiki lint (run_wiki_lint per task_type) → FAIL: SystemExit(1)
  → distill_contracts (≥ POSTRUN_DISTILL_MIN_EXAMPLES) → FAIL: SystemExit(1)
  → log_candidates (passive) → FAIL: log WARNING, continue
  → POSTRUN_OPTIMIZE=1?
     → subprocess: python scripts/optimize_prompts.py --target all
```

## Принцип fail-closed

При `PREFLIGHT_ENABLED=1` или `POSTRUN_ENABLED=1` — сбои поднимают `SystemExit(1)`. Это намеренно: раз включены — health checks обязательны.

Исключение: `log_candidates()` только наблюдательная → WARNING, не блокирует.

## Конфигурация

```bash
PREFLIGHT_ENABLED=0
POSTRUN_ENABLED=0
POSTRUN_DISTILL_MIN_EXAMPLES=10
POSTRUN_PROMOTE_MIN_COUNT=5
POSTRUN_OPTIMIZE=0
POSTRUN_OPTIMIZE_MIN_EXAMPLES=10   # добавлен позже
```
