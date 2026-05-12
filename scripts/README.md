# scripts/propose_optimizations.py

Синтезирует записи из `data/eval_log.jsonl` в файлы-кандидаты через LLM. Три канала: правила SQL, security-гейты, патчи промптов.

## Предварительные требования

```bash
cp .env.example .env        # добавить MODEL_EVALUATOR=anthropic/claude-...
uv sync                     # установить зависимости
```

`MODEL_EVALUATOR` — модель для синтеза (та же что в `.env`).

## Запуск

**Предварительный просмотр (без записи файлов):**

```bash
EVAL_ENABLED=1 uv run python main.py   # собрать eval_log
uv run python scripts/propose_optimizations.py --dry-run
```

**Запись кандидатов:**

```bash
uv run python scripts/propose_optimizations.py
```

## Результаты

| Канал | Куда пишет | Активация |
|-------|-----------|-----------|
| `rule_optimization` | `data/rules/sql-NNN.yaml` (`verified: false`) | Поставить `verified: true` |
| `security_optimization` | `data/security/sec-NNN.yaml` (`verified: false`) | Поставить `verified: true` |
| `prompt_optimization` | `data/prompts/optimized/YYYY-MM-DD-NN-file.md` | Скопировать секцию в `data/prompts/file.md` вручную |

## Проверка и применение

```bash
# Просмотреть предложенные правила
cat data/rules/sql-NNN.yaml

# Активировать правило
# Изменить verified: false → verified: true в файле

# Повторный запуск пропускает уже обработанные записи автоматически
uv run python scripts/propose_optimizations.py
```

Хеши обработанных записей хранятся в `data/.eval_optimizations_processed`.
