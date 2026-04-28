# Ollama Open-Weight Model Compatibility: Structured Output Hardening

**Date:** 2026-04-28  
**Scope:** Анализ совместимости open-weight моделей (Ollama tier) с harness-архитектурой + спек трёх целевых фиксов

---

## Контекст

Агент использует трёхуровневый LLM-роутинг (Anthropic → OpenRouter → Ollama). Ollama-tier включает облачные и локальные open-weight модели, сконфигурированные в `models.json`. Переключение модели — через env-переменные `MODEL_*`. Все компоненты pipeline уже реализованы; вопрос — насколько устойчиво они работают с open-weight моделями на уровне структурированных выводов.

---

## Анализ совместимости

| Компонент | Статус | Причина |
|-----------|--------|---------|
| Security gates (`security.py`) | ✅ | Код-уровень, от модели не зависит |
| Dispatch / Classifier fast-path | ✅ | Regex fast-path покрывает ~60% без LLM |
| Main loop tool calling (`loop.py`) | ⚠️ | JSON parse fragile; repeat_penalty уже настроен |
| DSPy classifier (`classifier.py`) | ⚠️ | COPRO-программа скомпилирована на Anthropic-стиле рассуждений |
| DSPy prompt builder (`prompt_builder.py`) | ⚠️ | Fail-open — деградация качества bullets, но не блокирует |
| DSPy evaluator (`evaluator.py`) | ⚠️ | `<think>`-блоки ломают field parser; калибровка при recompile |
| Contract negotiation (`contract_phase.py`) | ⚠️ | JSON recovery отсутствует для `ExecutorProposal`/`EvaluatorResponse` |
| Wiki synthesis graph_deltas (`wiki.py`) | ⚠️ | Fenced-блок хрупкий: позиция/кавычки/fence-маркер |

Основная проблема — не размер модели, а **структурные слабости в JSON recovery и DSPy field parsing** при open-weight completion стиле.

---

## Проблемы реализации

### П1 — JSON recovery минимален

`dispatch.py:_extract_json_fallback()` — простой `re.search(r'\{.*\}', text, re.DOTALL)`. При trailing comma, unescaped quotes, обрезанном токене — падает. Применяется к `NextStep`, `ExecutorProposal`, `EvaluatorResponse` без repair-логики.

### П2 — `<think>`-блоки ломают DSPy field parser

Модели с `ollama_think=true` вставляют `<think>…</think>` перед completion. `dspy.Predict` парсит поля из raw string — think-блок попадает в первое поле → все последующие поля сдвигаются.

### П3 — graph_deltas extraction хрупкий

`wiki.py:_llm_synthesize()` ищет ` ```json\n{...}\n``` ` только в конце ответа. Open-weight модели: (а) ставят блок в середину, (б) опускают fence-маркер, (в) используют одинарные кавычки. Fail-open → граф не обновляется.

---

## Спек изменений

### FIX-401 — Многоуровневый JSON repair pipeline

**Файлы:** `dispatch.py`, `loop.py`, `contract_phase.py`  
**Зависимость:** добавить `json5` (`uv add json5`)

Заменить `_extract_json_fallback()` на pipeline:

1. `json.loads(text)` → ok
2. `json5.loads(text)` — покрывает trailing comma, single quotes
3. Regex-извлечение первого `{…}` + `json5.loads()`
4. Скобочный баланс: дополнить `}` до закрытия всех `{` → повторить parse
5. Structured retry: вернуть модели `{"error": "...", "raw": "..."}` с инструкцией исправить (только для критических мест: `NextStep`, `ExecutorProposal`, `EvaluatorResponse`)

Применить ко всем трём Pydantic-точкам.

### FIX-402 — Strip `<think>` до DSPy field parser

**Файл:** `agent/dspy_lm.py` (класс `DispatchLM`, метод `forward`)

После получения completion, до передачи в DSPy:

```python
import re
completion = re.sub(r'<think>.*?</think>', '', completion, flags=re.DOTALL).strip()
```

Применяется только если тег присутствует — нет overhead для моделей без think.

### FIX-403 — Robust graph_deltas extraction

**Файл:** `agent/wiki.py` (функция `_llm_synthesize`)

Заменить текущий regex на приоритетный поиск:

1. Fenced ` ```json ` блок в **любом месте** ответа (не только конец)
2. Bare `{…}` после маркера `graph_deltas:` в тексте
3. `json5.loads()` на найденном фрагменте (покрывает single quotes, trailing comma)
4. Fail-open без изменений при любой ошибке

---

## Workflow реализации

Модель-тargeting через env (без изменений в коде):

```bash
# Переключить всё на target-модель
export MODEL_DEFAULT=qwen3.5:cloud
export MODEL_EVALUATOR=qwen3.5:cloud
# ... все MODEL_* vars

# Перекомпилировать DSPy-программы под новый backend
uv run python scripts/optimize_prompts.py --target builder
uv run python scripts/optimize_prompts.py --target evaluator
uv run python scripts/optimize_prompts.py --target classifier
```

Per-family программы не нужны — `DispatchLM` читает активную модель из env.

---

## Что остаётся за скопом

- Калибровка `EVALUATOR_SKEPTICISM` под конкретные модели — ручная настройка через env после реализации фиксов
- Contract negotiation quality на малых моделях — архитектурно ок, семантическое качество зависит от модели
