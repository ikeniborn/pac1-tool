# 04 — Failure replay

## Mapping fail-задач прошлого прогона → ответственный fix

| Task | Failure mode | Resolved by | Verify command |
|---|---|---|---|
| t11 | Refusal loop (NONE_CLARIFICATION) | U1 + U5 + U6 | score=1.0 ИЛИ early_stop ≤4 cycles |
| t19 | Refusal loop | U1 + U5 + U6 | same |
| t24 | Refusal loop | U1 + U5 + U6 | same |
| t36 | Refusal loop | U1 + U5 + U6 | same |
| t13 | Wrong date | U11 (skip researcher) — manual analysis | score=1.0 |
| t30 | Wrong calc | manual | score=1.0 |
| t41 | Wrong date | manual | score=1.0 |
| t20 | Over-write | U2 (graph не мержит ложные seq.json правила) | score=1.0 |
| t21 | Over-write | U2 | same |
| t23 | Missing ref | U8 (eval validate refs) | score=1.0 |
| t40 | Missing ref | U8 | same |
| t28 | Missed threat | U10 | score=1.0 |
| t33 | False-positive security | U9 | score=1.0 |

## Команда

```bash
uv run python main.py --tasks t11,t19,t24,t36,t23,t40,t28,t33
```

(Подмножество — task'и с deterministic fix'ами. t13/t30/t41/t20/t21 требуют
ручного анализа, не replay'ятся batch-командой.)

## Exit criteria

- ≥6/8 score=1.0.
- Для t11/t19/t24/t36 (refusal loop): допустимо score=0 если researcher
  early-stopped ≤4 циклов с `pending_refusal` (это U6/dynamic refusal budget,
  benchmark примет refusal только если оракул так считает).

## Если fail

1. Identify which unit'а fix не сработал (см. таблицу).
2. Найди соответствующий тест в `tests/regression/`:
   ```bash
   uv run pytest tests/regression/ -k <unit_keyword> -v
   ```
3. Проверь что fix actually merged в `agent/`:
   ```bash
   git log --oneline --all -- agent/researcher.py | head -10
   ```
4. Replay одной задачи с DEBUG:
   ```bash
   LOG_LEVEL=DEBUG uv run python main.py --tasks t11
   ```
   и смотри `hypothesis_for_next` поток между cycles — должны быть
   REFUSAL_RETRY → OUTCOME_FLIP_HINT → pending_refusal.

## Не пропускать

Без этого шага регрессия в одном из 8 fix'ов будет видна только через 8 часов
в шаге 5. Тут это 30 минут.
