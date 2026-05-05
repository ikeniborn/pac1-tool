---
wiki_sources:
  - docs/superpowers/specs/2026-05-04-five-bugs-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [fix, dspy, temporal, crm, evaluator, postrun]
---

# Five Bug Fixes (2026-05-04)

**Контекст:** 5-run minimax score 16% (4/25). Корень: broken DSPy feedback loop, bad temporal reasoning, CRM misclassification, evaluator rejection loop.

## Bug 1: _StepFact не сериализуется в dict

**Файл:** `agent/agents/executor_agent.py:78`

Pydantic v2 `ValidationError` на `list[_StepFact]` → DSPy examples никогда не накапливаются.

**Фикс:**
```python
_raw = stats.get("step_facts", [])
step_facts=[dataclasses.asdict(sf) if dataclasses.is_dataclass(sf) else sf for sf in _raw]
```

## Bug 2: postrun optimize падает без traceback

**Проблемы:** (1) `"python"` вместо `sys.executable`; (2) только stderr в error log; (3) `sys.exit(1)` на "no examples" в `optimize_prompts.py` → postrun abort каждый ранний run.

**Фикс:** `sys.executable`, stdout+stderr в error log, заменить `sys.exit(1)` на `log.warning()` в "below threshold" ветках.

## Bug 3: t41/t42 temporal — ESTIMATED_TODAY wrong

**Проблема:** `_TEMPORAL` prompt применяет hardcoded `gap = +5 days`. Vault рандомизирован с gaps 1–9 дней → ошибка ~80% runs.

**Фикс (`agent/prompt.py`, `_TEMPORAL` block, STEP 0):** Заменить fixed-gap на мультисигнальную триангуляцию:
1. Собрать ≥3 date anchors из vault (filename prefixes, updated_on, due_on и т.д.)
2. Для каждого anchor вычислить implied_today
3. Взять MEDIAN → ESTIMATED_TODAY
4. Проверить: ESTIMATED_TODAY ∈ [VAULT_DATE, VAULT_DATE + 14 days]

## Bug 4: t13 CRM misclassified as preject

**Проблема:** `crm` нет `fast_path` → classifier роутит "reschedule/reconnect" в `preject`.

**Фикс (`data/task_types.json`):** добавить `fast_path.pattern` для crm: regex `reschedule|reconnect|rebook` + `follow.?up|account|contact`. Также обновить `description` с anti-pattern: `"NOT preject: reschedule/reconnect without external URL/tool = crm"`.

## Bug 5: Evaluator rejection loop — required_evidence

**Проблема:** Contract evaluator LLM генерирует дескриптивные строки в `required_evidence`; `ref.lower() in e.lower()` требует exact substring → false rejection каждый раз.

**Фикс:** Part 1 — добавить в contract prompts инструкцию `required_evidence: bare vault paths only`. Part 2 — улучшить rejection message в `agent/evaluator.py`: `"Before re-submitting, add these paths to grounding_refs: {missing}. Re-read them if needed."`
