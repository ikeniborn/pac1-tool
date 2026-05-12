# Remove Orchestrator DRY_RUN — Design

**Date:** 2026-05-12  
**Scope:** Удаление отладочного инструмента `DRY_RUN` из оркестратора и всех связанных артефактов.

## Цель

`DRY_RUN=1` — отладочный режим, запускавший только prephase без LLM и писавший `data/dry_run_analysis.jsonl`. Prephase стабильна, инструмент не используется. Удаление уменьшает мёртвый код и упрощает prephase API.

## Изменения

### `agent/orchestrator.py`
- Удалить `_DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"`
- Удалить `_DRY_RUN_LOG = Path(...) / "data" / "dry_run_analysis.jsonl"`
- Удалить функцию `_write_dry_run(task_id, task_text, pre)`
- Удалить `if _DRY_RUN:` ветку в `run_agent()` (включая early return)
- Убрать `dry_run=_DRY_RUN` из вызова `run_prephase()`
- Удалить `import json` и `from pathlib import Path` (станут unused; `import os` оставить — нужен для `_MODEL`)

### `agent/prephase.py`
- Удалить параметр `dry_run: bool = False` из `run_prephase()`
- Удалить `if dry_run:` блок (чтение `/bin/sql` и заполнение `bin_sql_content`)
- Удалить поле `bin_sql_content: str = ""` из `PrephaseResult`
- Удалить локальную переменную `bin_sql_content = ""`
- Удалить из `return PrephaseResult(...)` аргумент `bin_sql_content=bin_sql_content`

### `tests/test_prephase.py`
- Удалить тест `test_dry_run_reads_bin_sql`
- Удалить тест `test_dry_run_bin_sql_not_in_log`
- Удалить тест `test_write_dry_run_format` (дублирован из test_orchestrator_pipeline.py)
- Убрать `"bin_sql_content"` из проверки полей `PrephaseResult` в `test_prephase_result_fields`

### `tests/test_orchestrator_pipeline.py`
- Удалить тест `test_write_dry_run_format`
- Удалить импорт `_write_dry_run` из `agent.orchestrator`

### `tests/test_pipeline.py`
- Убрать аргумент `bin_sql_content=""` из конструктора `PrephaseResult` в fixture

### `agent/CLAUDE.md`
- Удалить строку `- \`DRY_RUN=1\` — prephase only, no LLM calls, writes \`data/dry_run_analysis.jsonl\``

### `data/dry_run_analysis.jsonl`
- Удалить файл если существует

## Проверка успеха

```
uv run pytest tests/ -v  # все тесты проходят
grep -r "dry_run\|DRY_RUN\|_write_dry_run\|bin_sql_content" agent/ tests/  # ничего не найдено (кроме propose_optimizations)
```

## Вне scope

- `scripts/propose_optimizations.py --dry-run` — независимый CLI safety-флаг, не трогать
- `tests/test_propose_optimizations.py::test_dry_run_writes_nothing` — не трогать
