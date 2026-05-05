---
wiki_sources:
  - docs/superpowers/specs/2026-04-28-context-management-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, context-window, compaction, wiki, negatives]
---

# Context Management Redesign

**Дата:** 2026-04-28 | FIX-409 (token-aware compaction), FIX-410 (dead ends injection)

Две независимые проблемы: within-task context loss и between-run knowledge loss.

## Проблема 1: Token-Aware Compaction

**Было**: `_compact_log(max_tool_pairs=5)` вызывается безусловно перед каждым LLM-вызовом — дропает контекст независимо от реального fill уровня.

**Стало — lazy compaction**:

```python
def _estimate_tokens(log: list) -> int:
    return sum(len(str(m.get("content", ""))) for m in log) // 3
```

Динамический выбор pairs на основе fill уровня:
- < 70% ctx_window → no compaction
- 70–85% → 6 pairs (soft)
- 85–95% → 4 pairs (medium)
- 95%+ → 3 pairs (aggressive)

**READ facts в digest** — только metadata: `READ: /contacts/alice.md: (read, 1847 chars)`. Agent re-reads если нужно, deduplication READ по пути.

**`models.json`**: новое поле `ctx_window` для каждой модели (anthropic=200000, ollama=16384, etc.)

```bash
CTX_COMPACT_THRESHOLD_PCT=0.70  # default
```

## Проблема 2: Wiki/Graph Knowledge Between Runs

**Было**: только `score=1.0` обновляет pages; ошибки пишутся во fragments/errors/ но никогда не читаются обратно.

**Стало — Dead Ends Injection**:

`format_fragment()` при `score < 1.0` добавляет:
```markdown
## Dead end: <task_id>
Outcome: <OUTCOME_*>
What failed: <list of errored step_facts>
```

`load_wiki_patterns(task_type, include_negatives=True)` читает последние 5 error fragments:
```
## KNOWN DEAD ENDS (email)
- t12: searched contact by name — not found; correct path: /contacts/
```

Лимит: `WIKI_NEGATIVES_MAX_CHARS=800`. Инжектируется в тот же `preserve_prefix` слот что и wiki patterns.

```bash
WIKI_NEGATIVES_ENABLED=1
WIKI_NEGATIVES_MAX_CHARS=800
```
