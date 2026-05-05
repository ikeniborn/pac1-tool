---
wiki_title: "Scripts Lifecycle Automation Implementation Plan"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-05-03-scripts-lifecycle-automation.md"
wiki_updated: "2026-05-06"
tags: [lifecycle, maintenance, preflight, postrun, scripts]
---

# Scripts Lifecycle Automation

**Источник:** `docs/superpowers/plans/2026-05-03-scripts-lifecycle-automation.md`

## Цель

Мигрировать 4 utility scripts в `agent/maintenance/`, создать `agent/preflight.py` и `agent/postrun.py` lifecycle hooks, подключить в `main.py`, заменить subprocess-based `_auto_purge_graph()` прямыми вызовами модулей.

## Структура

**Новые файлы:**
- `agent/maintenance/__init__.py`
- `agent/maintenance/candidates.py` — `log_candidates()` (из scripts/)
- `agent/maintenance/graph_purge.py` — `auto_purge_graph()` (из scripts/)
- `agent/maintenance/wiki_sync.py` — `sync_wiki_index()` (из scripts/)
- `agent/preflight.py` — `run_preflight()` — вызывается до первого trial
- `agent/postrun.py` — `run_postrun(stats)` — вызывается после всех trials

**Изменения в main.py:**
```python
from agent.preflight import run_preflight
from agent.postrun import run_postrun

# до trials loop
run_preflight()

# после trials loop  
run_postrun(all_stats)
```

## Постусловие

`_auto_purge_graph()` в `main.py` — удалить (заменено `agent/maintenance/graph_purge.py`). Все subprocess вызовы скриптов заменены прямыми Python imports.
