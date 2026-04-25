# 02 — Smoke (normal mode canonical tasks)

## Список

| Task | Type | Почему именно эта |
|---|---|---|
| t01 | think | Канонический think-задачник, всегда 1.0 |
| t02 | distill | Покрывает summary/extract pipeline |
| t10 | crm | Invoice create — проверяет FIX-364 schema-mirror guard |
| t14 | email | Покрывает write-scope security gate (только outbox/) |
| t34 | lookup | Канонический read+search pipeline |

Все пятеро historically score=1.0 в normal mode на baseline `20260425_095904`.
Разные task_type → если ломается классификатор/router/security_gate — увидишь
здесь.

## Команда

```bash
uv run python main.py --tasks t01,t02,t10,t14,t34
```

## Exit criteria

- 5/5 = 1.00.
- Нет ошибок в `logs/<RUN>/*.log` уровня `ERROR` (warnings допустимы).

## Если fail

1. Найди последний baseline run:
   ```bash
   ls -t logs/ | grep -v researcher | head -3
   ```
2. Diff trajectories:
   ```bash
   diff logs/<baseline>/t01.log logs/<current>/t01.log | head -50
   ```
3. Check `RUN_PARAMS` блок в начале лога — если `eval_program=[missing]` или
   `builder_program=[missing]`, это норма (DSPy fail-open). Если изменился
   `model=` — значит `models.json` поломан.
4. Смотри последний emitted JSON command — если агент завис на одном tool
   3+ раза, FIX-103 stall-hint не сработал.

## Не пропускать

Если smoke fail'ит — `make run` гарантированно даст хуже baseline. Diagnose
ДО переходя к шагу 3.
