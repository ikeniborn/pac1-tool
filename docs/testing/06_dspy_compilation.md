# 06 — DSPy compilation (опционально)

## Когда нужно

После накопления корпуса examples (~один полный прогон с `DSPY_COLLECT=1`).
Скомпилированные программы загружаются автоматически на старте; до
компиляции работает fail-open режим (хардкод system-prompt без
DSPy-оптимизации).

Не делай compile если:
- Корпус `data/dspy_examples.jsonl` пуст / < 50 examples.
- Не было изменений в `prompt_builder.py` / `evaluator.py` / signatures.
- Ты в середине development cycle и хочешь deterministic baseline.

## Команды

```bash
DSPY_COLLECT=1 uv run python main.py
uv run python scripts/optimize_prompts.py --target evaluator
uv run python scripts/optimize_prompts.py --target builder
```

`scripts/optimize_prompts.py` использует COPRO; занимает ~1 час на 43 tasks corpus.

## Verify

```bash
ls -la data/evaluator_program.json data/prompt_builder_program.json
```

Оба файла должны быть `> 0 bytes`.

В следующем `make run` лог должен начинаться так:

```
RUN_PARAMS: ... eval_program=loaded builder_program=loaded ...
```

Если видишь `[missing]` — программа не загрузилась (path mismatch или
неправильный формат). Проверь `agent/evaluator.py::_load_program` и
`agent/prompt_builder.py::_load_program`.

## Per-type evaluator

Per-task-type программы:
```bash
uv run python scripts/optimize_prompts.py --target evaluator --task-type email
```

После growing researcher corpus (FIX-367 — evaluator теперь видит wiki+graph),
рекомпилировать евалюаторы для тех types где появились новые Successful
patterns / Verified refusals.

## Rollback

Если новая compiled program ухудшила score:

```bash
git checkout HEAD~1 -- data/evaluator_program.json data/prompt_builder_program.json
```

(Programs versioned в git, rollback тривиален.)
