# 01 — Pre-flight regression suite

## Что покрывает

`tests/regression/` собирает unit-тесты от worker-units U1-U10 (separate fixes
для researcher-classes регрессий). Каждый unit пишет один или несколько
test-файлов; общая инфраструктура (fixtures) — в `tests/regression/conftest.py`.

| Unit | Fixture базис | Покрывает |
|---|---|---|
| U1 | `fake_connect_error` | INVALID_ARGUMENT guard на повторный `report_completion` |
| U2 | `fake_graph` | wiki_graph merge не записывает ложные `seq.json` правила |
| U3 | `fake_reflection`, `fake_step_fact` | reflector outcome-history regression (FIX-375b/B) |
| U4 | `fake_cycle_stats` | researcher OK-loop hard guard (FIX-375b/C) |
| U5 | `fake_reflection` | OUTCOME_FLIP_HINT injection (FIX-375) |
| U6 | `fake_cycle_stats` | dynamic refusal budget (FIX-376f) |
| U7 | `fake_graph` | graph quarantine (FIX-376g) |
| U8 | — | evaluator validates referenced paths actually exist |
| U9 | — | security gate false-positive detection (t33-class) |
| U10 | — | security threat detection (t28-class) |

## Команда

```bash
uv run pytest tests/regression/ -v
```

Полный (regression + existing units):

```bash
uv run pytest tests/ -v
```

## Exit criteria

- 100% pass за ≤ 30 сек.
- Никаких xfail/skip в `tests/regression/`.

## Troubleshooting

**`ImportError: connectrpc.errors`** — `tests/conftest.py` стабит этот модуль до
импорта `agent.*`. Если импорт всё равно ломается — проверь `sys.path` (запуск
не из корня проекта).

**`ModuleNotFoundError: agent.reflector`** — запускай из репо-корня (`uv run
pytest ...`), не из `tests/`.

**Конфликт fixtures** — `tests/regression/conftest.py` строится поверх
`tests/conftest.py`. НЕ дублирует stub'ы protobuf/anthropic/connectrpc. Если
нужен новый stub — добавляй в `tests/conftest.py`, не в regression/.

**Падает `fake_reflection` с TypeError** — поле `Reflection.outcome` принимает
только `{"solved", "partial", "stuck", "error"}`. Любое другое значение
silently coerces к `"stuck"` (см. `agent/reflector.py:188`).
