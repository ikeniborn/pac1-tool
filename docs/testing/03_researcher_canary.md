# 03 — Researcher canary

## Список

t04, t06, t12 — все historically score=1.0 в researcher mode на прошлом
прогоне. Если researcher.py сломан — увидишь здесь, до того как сжечь
6+ часов на full run.

## Команда

```bash
RESEARCHER_MODE=1 PARALLEL_TASKS=1 uv run python main.py --tasks t04,t06,t12
```

`PARALLEL_TASKS=1` обязателен — параллельные researcher-задачи не видят
graph-обновлений друг друга (см. CLAUDE.md, researcher mode notes).

## Exit criteria

- 3/3 = 1.00.
- 0 occurrences `INVALID_ARGUMENT` в каждом из t04/t06/t12 логов.
  Это проверка что Unit 1 (повторный `report_completion` guard) работает —
  researcher не должен получать INVALID_ARGUMENT от harness'а.

## Critical post-run check

```bash
RUN_DIR=$(ls -t logs/ | grep -v researcher | head -1)
for t in t04 t06 t12; do
  cnt=$(grep -c "INVALID_ARGUMENT" logs/$RUN_DIR/$t.log 2>/dev/null || echo 0)
  if [ "$cnt" -gt 0 ]; then
    echo "FAIL: $t had $cnt INVALID_ARGUMENT — Unit 1 not effective"
  fi
done
```

Если хотя бы одна задача имеет INVALID_ARGUMENT > 0 — Unit 1 регрессировал,
не запускай шаги 4/5 пока не починишь.

## Если score fail

- Проверь `stats["researcher_*"]` в conlosg/research summary:
  - `researcher_cycles_used` — должно быть < `RESEARCHER_MAX_CYCLES`
  - `researcher_eval_calls` — 0 если `RESEARCHER_EVAL_GATED=0` (default)
  - `researcher_pending_promotion` — должен быть set'нут на success
- Проверь `data/wiki/pages/<task_type>.md` — есть ли promoted pattern для
  этой задачи от прошлого прогона. Если был — а сейчас не используется —
  graph-retrieval сломан.
