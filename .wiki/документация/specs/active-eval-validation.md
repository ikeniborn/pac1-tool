---
wiki_sources:
  - "[[docs/superpowers/specs/2026-05-14-active-eval-validation-design.md]]"
wiki_updated: 2026-05-14
wiki_status: developing
wiki_outgoing_links:
  - "[[agent-modules/evaluator]]"
  - "[[agent-modules/pipeline]]"
  - "[[agent-modules/orchestrator]]"
wiki_external_links: []
tags:
  - ecom1-agent
aliases:
  - "Active Eval Validation"
  - "Активная валидация рекомендаций"
---

# Active Eval Validation

Дизайн-документ (статус: Approved, 2026-05-14) описывает переход от пассивного к активному eval: `propose_optimizations.py` валидирует каждую рекомендацию, повторно запуская оригинальную задачу с инжектированной рекомендацией, и записывает файл правила/промпта/секьюрити-гейта только если score не регрессировал.

## Проблема

Текущий eval пассивен: скорит трейс пайплайна, записывает рекомендации в `eval_log.jsonl`, рекомендации применяются офлайн через `propose_optimizations.py` без проверки, действительно ли они улучшают результаты.

## Архитектура

### Параметры инжекции

Три новых опциональных параметра добавляются в `run_agent`, `run_pipeline` и `_build_static_system`:

```python
injected_session_rules: list[str] = []       # → предзаполняет session_rules
injected_prompt_addendum: str = ""            # → добавляется к guide-блоку в _build_static_system
injected_security_gates: list[dict] = []     # → мержится в security gates при запуске pipeline
```

`injected_prompt_addendum` добавляется к guide-блоку для фаз `sql_plan`, `learn`, `answer`. Фаза `resolve` использует plain-строку и не затрагивается.

`injected_security_gates` мержится в `run_pipeline` до использования результата `_get_security_gates()`:
```python
security_gates = _get_security_gates() + (injected_security_gates or [])
```

### Соответствие типов рекомендаций и инжекции

| Поле eval | Параметр инжекции | Записываемый файл |
|-----------|-------------------|-------------------|
| `rule_optimization` | `injected_session_rules` | `data/rules/sql-NNN.yaml` |
| `prompt_optimization` | `injected_prompt_addendum` | `data/prompts/optimized/YYYY-MM-DD-NN-<block>.md` |
| `security_optimization` | `injected_security_gates` | `data/security/sec-NNN.yaml` |

`PipelineEvalOutput.prompt_optimization` — `list[str]`. Каждый элемент валидируется отдельно; элементы никогда не конкатенируются в один прогон.

### Механизм re-run

`validate_recommendation()` в `propose_optimizations.py`:

1. `os.environ["EVAL_ENABLED"] = "0"` устанавливается на верху модуля до импортов agent — `pipeline._EVAL_ENABLED` = `False` для всех вызовов `run_agent()` в скрипте
2. `read_original_score(task_id)` — сканирует `logs/*/`, исключает директории с именем `"validate-"`, выбирает latest по mtime, читает `{task_id}.jsonl`, извлекает событие `task_result.score`
3. Запускает `HarnessServiceClientSync`, создаёт run с именем `f"validate-{timestamp}"`
4. Итерирует `trial_ids`, пропускает нерелевантные (без ответа, score=0), вызывает `run_agent()` с injection-параметрами, читает score из `end_trial()`

### Решение по score

```
original_score is None → записать файл (verified: false), WARNING: нет baseline
validation_score >= original_score → записать файл (verified: false), лог ACCEPTED
validation_score < original_score → НЕ записать файл, лог REJECTED
```

Порог: `>=` (без регрессии). Файлы записываются с `verified: false` — человек должен установить `verified: true` для активации.

### Дедупликация

Для заданного `task_id` — группировать все записи eval_log по `task_id`. По типу рекомендации (`rule_optimization`, `prompt_optimization`, `security_optimization`) дедуплицировать по content hash перед валидацией. Существующее `.eval_optimizations_processed` хранилище хешей продолжает отслеживать обработанные записи.

## Поведение по умолчанию

Валидация включена по умолчанию. `--dry-run` пропускает валидацию и записывает файлы безусловно (текущее поведение).

## Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `agent/evaluator.py` | Добавить `task_id: str` в `EvalInput`; записывать `task_id` в запись eval_log |
| `agent/pipeline.py` | `run_pipeline` получает `task_id: str = ""` + 3 injection-параметра; `_build_static_system` получает `injected_prompt_addendum: str = ""`; мерж security gates; `task_id` проксируется в `_run_evaluator_safe` kwargs |
| `agent/orchestrator.py` | `run_agent` получает `task_id` (уже существует) + 3 injection-параметра, передаёт в `run_pipeline` |
| `scripts/propose_optimizations.py` | `os.environ["EVAL_ENABLED"] = "0"` на верху модуля; `validate_recommendation()`, `read_original_score()`; дедупликация по content hash; гейт записи файлов на результат валидации; `--dry-run` сохранён |

## Вне области

- Eval-поток не ожидает валидации (остаётся async, пассивным)
- `eval` не применяет рекомендации автоматически — `propose_optimizations` по-прежнему требует ручного запуска
- Гейт `verified: false` по умолчанию сохранён — гейт человеческого ревью не убирается
- Параллельная валидация нескольких задач не реализована (последовательно по каждой рекомендации)
