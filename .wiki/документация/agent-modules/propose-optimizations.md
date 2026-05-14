---
wiki_type: agent-module
wiki_status: developing
wiki_sources:
  - scripts/CLAUDE.md
  - scripts/propose_optimizations.py
wiki_created: 2026-05-14
wiki_updated: 2026-05-14
tags:
  - ecom1-agent
  - optimization
  - eval
  - agent-module
---

# propose_optimizations.py

Скрипт оптимизации: читает `data/eval_log.jsonl`, синтезирует LLM-рекомендации в готовые к ревью кандидат-файлы. Три выходных канала — правила SQL, security gates, патчи промптов.

## Назначение

Замыкает петлю обратной связи: `run_pipeline` → `evaluator.py` → `eval_log.jsonl` → `propose_optimizations.py` → `data/rules/`, `data/security/`, `data/prompts/optimized/`.

Ничего не активируется автоматически. Все кандидаты пишутся с `verified: false` и требуют ручного ревью.

## Запуск

```bash
# Предпросмотр без записи файлов
uv run python scripts/propose_optimizations.py --dry-run

# Запись кандидатов в data/
uv run python scripts/propose_optimizations.py

# Тесты
uv run pytest tests/test_propose_optimizations.py -v
```

Обязательные env vars:
- `MODEL_EVALUATOR` — модель для синтеза (e.g. `anthropic/claude-haiku-4-5-20251001`)

Для harness-валидации (`--no-dry-run`): также `BITGN_API_KEY`, `BENCHMARK_HOST`, `BENCHMARK_ID`.

## Выходные каналы

| Channel key | Путь | Активация |
|-------------|------|-----------|
| `rule_optimization` | `data/rules/sql-NNN.yaml` | установить `verified: true` |
| `security_optimization` | `data/security/sec-NNN.yaml` | установить `verified: true` |
| `prompt_optimization` | `data/prompts/optimized/YYYY-MM-DD-NN-<file>.md` | вручную скопировать секцию в `data/prompts/<file>.md` |

## Pipeline обработки (per channel)

1. **Flatten** — собрать необработанные рекомендации из `eval_log.jsonl` по ключу канала.
2. **Content-hash dedup** (`_dedup_by_content_per_task`) — отбросить дубликаты внутри одного `task_id`; сразу пометить их хэши обработанными.
3. **LLM cluster** (`_cluster_recs`) — один LLM-вызов объединяет семантически эквивалентные рекомендации по всем задачам; возвращает представительные записи.
4. **Synthesize** (`_synthesize_rule` / `_synthesize_security_gate` / `_synthesize_prompt_patch`) — LLM-вызов преобразует представительную запись в структурированную форму; возвращает `None` если уже покрыто (LLM отвечает `null`).
5. **Contradiction check** (`_check_contradiction`) — отклоняет кандидата если он прямо противоречит существующему правилу/gate.
6. **Validate** — перезапуск задачи через harness с инжектированной рекомендацией; запись только при `validation_score >= original_score`.

## Validation Gate

Перед записью любого кандидата скрипт перезапускает порождающую задачу через BitGN harness с инжектированной рекомендацией (`validate_recommendation`).

- `validation_score >= original_score` → записать кандидата
- Нет baseline-скора в `logs/` → записать с предупреждением
- Задача не найдена в trial set → пропустить кандидата целиком

`read_original_score` читает из последней не-`validate-*` директории под `logs/`.

## Deduplication

Обработанные записи отслеживаются по SHA-256 хэшу `(channel|task_text|raw_rec)` в `data/.eval_optimizations_processed`.

- Последующие запуски пропускают уже обработанные хэши независимо от `--dry-run`.
- В `--dry-run` режиме скипнутые записи **не** добавляются в processed set — предпросмотр не деструктивен.

## Синтезаторы

Каждый канал вызывает `agent.llm.call_llm_raw` с инжектированным содержимым существующих правил/промптов в системный промпт — для предотвращения дубликатов.

Хелперы для инжекции: `_existing_rules_text`, `_existing_security_text`, `_existing_prompts_text` из `agent.knowledge_loader`.

**Критично: не удалять `_existing_*` хелперы** и не исключать их из промптов синтезаторов — без них LLM будет генерировать дублирующие правила.

`call_llm_raw_cluster` — модульный алиас к `call_llm_raw`, намеренно экспортированный для патчинга в тестах без влияния на синтезаторы.

`_next_num()` — сканирует целевую директорию для вычисления следующего порядкового ID.

## Добавление нового канала

1. Написать синтезатор `_synthesize_<channel>(raw_rec, existing_md, model, cfg) -> <type> | None`
2. Написать writer `_write_<channel>(...) -> Path`
3. Добавить блок в `main()` по паттерну существующих трёх каналов (flatten → dedup → cluster → synthesize → contradiction-check → validate → write)
4. Добавить dedup-хэш с уникальной строкой канала (не `"rule"`, `"security"`, `"prompt"`)

## Зависимости

- `agent.llm.call_llm_raw` — LLM-вызов
- `agent.knowledge_loader` — загрузка `_existing_*` контента
- `data/eval_log.jsonl` — источник рекомендаций (пишет `evaluator.py`)
- `data/.eval_optimizations_processed` — реестр обработанных хэшей
