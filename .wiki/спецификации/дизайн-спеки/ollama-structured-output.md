---
wiki_sources:
  - docs/superpowers/specs/2026-04-28-ollama-structured-output-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, ollama, structured-output, fix, json-recovery]
---

# Ollama Structured Output Hardening

**Дата:** 2026-04-28

Анализ совместимости open-weight моделей (Ollama tier) и спек трёх фиксов для JSON recovery.

## Проблемы

| # | Проблема | Место |
|---|---|---|
| П1 | JSON recovery минимален — `_extract_json_fallback()` не обрабатывает trailing comma, unescaped quotes | `dispatch.py`, `loop.py`, `contract_phase.py` |
| П2 | `<think>`-блоки ломают DSPy field parser — think-блок попадает в первое поле | `agent/dspy_lm.py` |
| П3 | `graph_deltas` extraction хрупкий — open-weight модели ставят блок в середину, меняют кавычки | `agent/wiki.py` |

## FIX-401 — Многоуровневый JSON repair pipeline

Заменить `_extract_json_fallback()` на 5-уровневый pipeline:
1. `json.loads(text)` → ok
2. `json5.loads(text)` — trailing comma, single quotes
3. Regex первый `{…}` + `json5.loads()`
4. Скобочный баланс: дополнить `}` до закрытия всех `{` → parse
5. Structured retry: вернуть модели `{"error": "...", "raw": "..."}` (только для NextStep, ExecutorProposal, EvaluatorResponse)

Зависимость: `uv add json5`

## FIX-402 — Strip `<think>` до DSPy field parser

В `DispatchLM.forward()` после получения completion:
```python
completion = re.sub(r'<think>.*?</think>', '', completion, flags=re.DOTALL).strip()
```

## FIX-403 — Robust graph_deltas extraction

В `_llm_synthesize()` заменить текущий regex на приоритетный поиск:
1. Fenced ` ```json ` блок в любом месте ответа
2. Bare `{…}` после `graph_deltas:` в тексте
3. `json5.loads()` на найденном фрагменте
4. Fail-open при ошибке
