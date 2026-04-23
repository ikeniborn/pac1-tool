# pac1-py — PAC-1 Benchmark Agent

Python-агент для бенчмарка PAC-1. Решает задачи с файловым хранилищем (vault) через
инструменты: tree, find, search, list, read, write, delete, mkdir, move, report_completion.

---

## Быстрый старт

```bash
# Установить зависимости
make sync          # или: uv sync

# Запустить все задачи
uv run python main.py

# Запустить конкретные задачи
make task TASKS='t01,t03,t07'
```

Ключи API нужно положить в `.secrets` (рядом с `.env`):

```
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
```

---

## Переменные окружения

Загружаются в порядке приоритета: системные переменные → `.secrets` → `.env`.
Шаблон: `.env.example`.

### Модели

| Переменная | Fallback | Описание |
|---|---|---|
| `MODEL_DEFAULT` | — | Основная модель (обязательная) |
| `MODEL_CLASSIFIER` | — | Классификатор типа задачи (обязательная) |
| `MODEL_EMAIL` | `MODEL_DEFAULT` | Модель для задач типа email |
| `MODEL_LOOKUP` | `MODEL_DEFAULT` | Модель для поиска/запросов |
| `MODEL_INBOX` | `MODEL_DEFAULT` | Модель для обработки inbox |
| `MODEL_QUEUE` | `MODEL_INBOX` | Модель для batch-обработки очереди |
| `MODEL_CAPTURE` | `MODEL_DEFAULT` | Модель для capture-задач |
| `MODEL_CRM` | `MODEL_DEFAULT` | Модель для CRM follow-up |
| `MODEL_TEMPORAL` | `MODEL_LOOKUP` | Модель для дата-арифметики |
| `MODEL_PREJECT` | `MODEL_DEFAULT` | Модель для немедленного отказа |
| `MODEL_DISTILL` | `MODEL_DEFAULT` | Модель для анализа + записи карточки/заметки |
| `MODEL_WIKI` | `MODEL_DEFAULT` | Модель для wiki-lint (до/после прогона) |
| `MODEL_EVALUATOR` | `MODEL_DEFAULT` | Критик (evaluator/critic) |
| `MODEL_PROMPT_BUILDER` | `MODEL_CLASSIFIER` | Генератор addendum (на каждом прогоне) |
| `MODEL_OPTIMIZER` | `MODEL_CLASSIFIER` | Модель для `optimize_prompts.py` |

Для нового типа, добавленного в `data/task_types.json` (см. [Реестр типов задач](#реестр-типов-задач-fix-325)),
`ModelRouter` автоматически читает `MODEL_<UPPER>` (например `MODEL_ORDER` для типа `order`).
Если переменная не задана — разрешается через `fallback_chain` из записи реестра.

### Инфраструктура

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BENCHMARK_HOST` | `https://api.bitgn.com` | API-эндпоинт бенчмарка |
| `BENCHMARK_ID` | `bitgn/pac1-dev` | ID бенчмарка |
| `BITGN_RUN_NAME` | — | Имя запуска (отображается в отчёте) |
| `TASK_TIMEOUT_S` | `300` | Таймаут на задачу (секунды) |
| `PARALLEL_TASKS` | `1` | Количество параллельных задач |
| `LOG_LEVEL` | `INFO` | `DEBUG` — полный вывод LLM-ответов и think-блоков |
| `TZ` | системный | Часовой пояс для timestamps логов |
| `ROUTER_FALLBACK` | `CLARIFY` | Стратегия при неясном типе задачи: `CLARIFY` \| `EXECUTE` |
| `ROUTER_MAX_RETRIES` | `2` | Максимум попыток классификации |

### Evaluator (критик)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `EVALUATOR_ENABLED` | `1` | `1` — включён, `0` — выключен |
| `EVAL_SKEPTICISM` | `mid` | Строгость проверки: `low` / `mid` / `high` |
| `EVAL_EFFICIENCY` | `mid` | Глубина контекста: `low` / `mid` / `high` |
| `EVAL_MAX_REJECTIONS` | `2` | Максимум отказов до принудительного одобрения |

### Prompt Builder

| Переменная | По умолчанию | Описание |
|---|---|---|
| `PROMPT_BUILDER_ENABLED` | `1` | `1` — включён, `0` — выключен |
| `PROMPT_BUILDER_MAX_TOKENS` | `500` | Бюджет токенов для addendum |

### Сбор примеров DSPy

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DSPY_COLLECT` | `1` | `1` — сохранять примеры после каждого прогона |

### Провайдеры

| Переменная | Описание |
|---|---|
| `OLLAMA_BASE_URL` | URL локального Ollama (например `http://localhost:11434/v1`) |
| `OLLAMA_MODEL` | Имя модели Ollama |

---

## DSPy — оптимизация промтов

Агент использует [DSPy](https://dspy.ai) для трёх подсистем:

| Модуль | Класс DSPy | Файл | Программа |
|---|---|---|---|
| **Classifier** | `ChainOfThought(ClassifyTask)` | `agent/classifier.py` | `data/classifier_program.json` |
| **Prompt Builder** | `Predict(PromptAddendum)` | `agent/prompt_builder.py` | `data/prompt_builder_program.json` |
| **Evaluator** | `ChainOfThought(EvaluateCompletion)` | `agent/evaluator.py` | `data/evaluator_program.json` |

Все три модуля используют `DispatchLM` — обёртку над `call_llm_raw()`
(3-tier routing: Anthropic → OpenRouter → Ollama). Глобальное состояние DSPy не затрагивается:
каждый вызов использует `dspy.context(lm=...)`.

Если скомпилированный файл отсутствует — модуль работает с промтами по умолчанию (fail-open).

### Как работает цикл данных

```
каждый прогон main.py
  ├─► data/dspy_examples.jsonl      ← builder + classifier (1 запись/задача)
  └─► data/dspy_eval_examples.jsonl ← evaluator (1 запись/задача, если EVALUATOR_ENABLED=1)

при ≥ 30 builder-записях
  └─► агент печатает: "[dspy] 30 real examples → run: optimize_prompts.py --target builder"

optimize_prompts.py
  ├─► читает dspy_examples.jsonl      → builder + classifier trainset
  │   если < 30 — добавляет dspy_synthetic.jsonl (cold-start, статичный)
  ├─► читает dspy_eval_examples.jsonl → evaluator trainset
  │   если < 20 — использует 4 hardcoded bootstrap-примера
  └─► пишет data/*.json — агент подхватывает при следующем старте
```

### Запуск оптимизатора

```bash
# Только классификатор
uv run python optimize_prompts.py --target classifier

# Только prompt builder
uv run python optimize_prompts.py --target builder

# Только evaluator
uv run python optimize_prompts.py --target evaluator

# Все три сразу
uv run python optimize_prompts.py --target all

# Ограничение по типу задачи: последние N примеров на каждый task_type
# Гарантирует представленность редких типов (crm, temporal, distill)
uv run python optimize_prompts.py --target all --max-per-type 10

# Повысить порог качества примеров (по умолчанию 0.8)
uv run python optimize_prompts.py --target builder --min-score 0.9

# Комбинация: лёгкая модель + ограничение + строгий порог
MODEL_OPTIMIZER=anthropic/claude-haiku-4.5 \
  uv run python optimize_prompts.py --target all --max-per-type 10 --min-score 0.9
```

#### Аргументы `optimize_prompts.py`

| Аргумент | По умолчанию | Описание |
|---|---|---|
| `--target` | `all` | `builder` / `evaluator` / `classifier` / `all` |
| `--min-score` | `0.8` | Минимальный score для включения builder/classifier примера |
| `--max-per-type` | без лимита | Максимум примеров на группу. Для builder/classifier — последние N на `task_type`. Для evaluator — последние N на `(task_type, approved_str)`. Гарантирует представленность всех типов; редкие типы берутся целиком |

Приоритет модели для оптимизатора: `MODEL_OPTIMIZER` → `MODEL_CLASSIFIER` → `MODEL_DEFAULT`.

COPRO делает `BREADTH × DEPTH × |trainset|` вызовов LLM — рекомендуется лёгкая модель.

#### Как выбрать `--max-per-type`

| Ситуация | Рекомендация |
|---|---|
| Первые 50–100 прогонов | без `--max-per-type` (все примеры нужны) |
| > 100 прогонов, много повторяющихся задач | `--max-per-type 10` |
| Быстрая проверка пайплайна (smoke-test) | `--max-per-type 5` + `COPRO_DEPTH=1` |

#### Параметры COPRO (через env)

| Переменная | По умолчанию | Описание |
|---|---|---|
| `COPRO_BREADTH` | `4` | Кандидатов-инструкций на итерацию |
| `COPRO_DEPTH` | `2` | Раундов уточнения |
| `COPRO_TEMPERATURE` | `0.9` | Температура при генерации кандидатов |
| `COPRO_THREADS` | `1` | Параллелизм оценки (>1 требует запаса RPM) |

### Сброс оптимизации

```bash
rm data/prompt_builder_program.json data/evaluator_program.json data/classifier_program.json
```

После этого агент использует промты из кода.

### Просмотр накопленных примеров

```bash
# Количество примеров
wc -l data/dspy_examples.jsonl data/dspy_eval_examples.jsonl

# Примеры с высоким score по типам
python3 -c "
import json
from collections import Counter
exs = [json.loads(l) for l in open('data/dspy_examples.jsonl')]
print(Counter(e['task_type'] for e in exs if e['score'] >= 0.9))
"

# Баланс yes/no в evaluator-примерах
python3 -c "
import json
from collections import Counter
exs = [json.loads(l) for l in open('data/dspy_eval_examples.jsonl')]
print(Counter(e['expected_approved_str'] for e in exs))
"
```

---

## Архитектура агента

```
main.py → run_agent()
  ├── run_prephase()                    — vault tree + AGENTS.MD
  ├── ModelRouter.resolve_after_prephase()
  │     ├── classify_task()             — regex fast-path
  │     └── classify_task_llm()        — DSPy classifier (если скомпилирован)
  │                                       → LLM fallback → regex fallback
  ├── build_system_prompt()             — модульная сборка системного промта
  ├── build_dynamic_addendum()          — DSPy Prompt Builder
  └── run_loop()                        — до 30 шагов: LLM → tool → PCM
        ├── evaluator                   — DSPy Evaluator перед submit
        ├── stall detection             — обнаружение зависания
        ├── security gates              — проверки инъекций
        └── log compaction             — сжатие лога
```

### Типы задач

| Тип | Ключевые признаки | Переменная модели |
|---|---|---|
| `preject` | calendar invite, external API, sync to CRM | `MODEL_PREJECT` |
| `queue` | work through / take care of all inbox items | `MODEL_QUEUE` |
| `inbox` | process/check/handle single inbox note | `MODEL_INBOX` |
| `email` | send/compose email to recipient | `MODEL_EMAIL` |
| `lookup` | find, count, query vault data (no write) | `MODEL_LOOKUP` |
| `capture` | save snippet/content to vault path | `MODEL_CAPTURE` |
| `crm` | reschedule follow-up, fix due date | `MODEL_CRM` |
| `temporal` | N days ago, in N days, date arithmetic | `MODEL_TEMPORAL` |
| `distill` | analyze + write summary/card | `MODEL_DISTILL` |
| `default` | всё остальное | `MODEL_DEFAULT` |

Классификация трёхуровневая: regex fast-path → DSPy compiled program → `call_llm_raw()` → regex fallback.

---

## Реестр типов задач (FIX-325)

Источник истины — `data/task_types.json`. Loader/API: `agent/task_types.py`.

Реестр питает: enum классификатора, docstring `ClassifyTask`, `cc_json_schema.task_type.enum`
(инъектится в `cc_client.py` в runtime), regex fast-path в `classify_task()`,
разрешение модели в `ModelRouter`, folder-map в `wiki.py`, `prompt_builder._NEEDS_BUILDER`.

### Структура записи

```json
{
  "order": {
    "description": "ordering goods/services from external vendors",
    "model_env": "MODEL_ORDER",
    "fallback_chain": ["default"],
    "wiki_folder": "order",
    "fast_path": null,
    "needs_builder": true,
    "status": "soft"
  }
}
```

| Поле | Назначение |
|---|---|
| `description` | идёт в docstring `ClassifyTask` и в системный промт классификатора |
| `model_env` | имя ENV-переменной (конвенция: `MODEL_<UPPER>`) |
| `fallback_chain` | упорядоченный список типов для резолва модели, если `model_env` не задан |
| `wiki_folder` | папка в `data/wiki/fragments/<folder>/` |
| `fast_path` | опционально; `{pattern, flags, confidence}` — regex минует LLM при `confidence: "high"` |
| `needs_builder` | `false` отключает DSPy Prompt Builder для этого типа |
| `status` | `hard` — учтён в compiled classifier; `soft` — только в prompt'е, нужно перекомпилировать |

### Добавление типа вручную

```bash
# 1. Вписать запись в data/task_types.json (см. структуру выше)
# 2. Опционально задать MODEL_<UPPER> в .env
echo "MODEL_ORDER=anthropic/claude-haiku-4.5" >> .env
# 3. Опционально создать папку для wiki-фрагментов
mkdir -p data/wiki/fragments/order
# 4. Для soft-типов — перекомпилировать DSPy-классификатор с новым enum
uv run python optimize_prompts.py --target classifier
# 5. Опционально — добавить bespoke-блок в _TASK_BLOCKS внутри agent/prompt.py
#    (иначе тип унаследует системный промт default-типа; warn-once в логе при старте)
```

### Open-set: накопление кандидатов и автопродвижение

Если LLM-классификатор предложил тип, которого нет в реестре, он логируется в
`data/task_type_candidates.jsonl` без дополнительных LLM-вызовов. Затем:

```bash
# Показать агрегаты (частота повторов, примеры task_text, варианты формулировок)
uv run python scripts/analyze_task_types.py

# Снизить порог для промоции (по умолчанию 5)
uv run python scripts/analyze_task_types.py --min-count 3

# Интерактивно добавить в реестр кандидатов, прошедших порог
uv run python scripts/analyze_task_types.py --promote
```

`--promote` запросит для каждого кандидата: имя типа, описание, `model_env`,
`fallback_chain`, `wiki_folder`; запишет в `data/task_types.json` со `status: "soft"`,
создаст папку wiki-фрагментов и напомнит про перекомпиляцию классификатора.
Прерывание (`Ctrl-C` / `EOF`) сохраняет уже принятые записи.

### Ветки поведения по типу

Привязанные к конкретным типам ветки (`preject` short-circuit в `agent/__init__.py`,
scope-gates в `security.py`, stall-hints в `loop.py`, per-type блоки в `prompt._TASK_BLOCKS`)
остаются в коде и ссылаются на реестр через `TASK_*` константы, реэкспортируемые
из `agent.classifier` / `agent.task_types` (PEP 562). Добавление нового типа в реестр
автоматически открывает `TASK_<UPPER>` для импорта — код-ветки можно дописать при
необходимости, иначе тип получает поведение `default`.

---

## Тесты

```bash
uv run python -m pytest tests/

# Конкретный файл
uv run pytest tests/test_security_gates.py -v
```

---

## Replay-трейсер

```bash
# Воспроизвести трейс
uv run python -m agent.tracer logs/<trace_file>.jsonl
```

---

## Прочие команды

```bash
# Пересобрать proto-стабы (после изменений pcm.proto)
make proto        # или: buf generate

# Оптимизировать промты в фоне (пока main.py накапливает примеры)
uv run python optimize_prompts.py --target classifier --max-examples 60
```
