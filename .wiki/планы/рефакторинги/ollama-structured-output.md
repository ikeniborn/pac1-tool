---
wiki_title: "Ollama Structured Output Hardening"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-28-ollama-structured-output.md"
wiki_updated: "2026-05-06"
tags: [refactor, ollama, json, think-blocks, graph-deltas, structured-output]
---

# Ollama Structured Output Hardening

**Источник:** `docs/superpowers/plans/2026-04-28-ollama-structured-output.md`

## Цель

Устранить три структурных дефекта, мешающих надёжной работе pipeline на Ollama open-weight моделях: хрупкий JSON recovery, проглатывание `<think>`-блоков DSPy-парсером, нестабильное извлечение graph_deltas из wiki-синтеза.

## Три дефекта

### 1. Хрупкий JSON recovery
Ollama часто добавляет preamble (`"Here is the result:"`) перед JSON объектом.  
**Фикс:** Универсальный `_extract_json_from_text()` применяется до `model_validate_json` (аналог FIX-397 для CC tier).

### 2. `<think>` блоки в DSPy парсере
Reasoning models (qwq, deepseek-r1) вставляют `<think>...</think>` → DSPy парсер ломается на JSON.  
**Фикс:** Pre-strip `<think>...</think>` блоков перед DSPy response parsing:
```python
import re
response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
```

### 3. Нестабильное извлечение graph_deltas
`_llm_synthesize` запрашивает fenced ```json {graph_deltas: ...}``` — Ollama иногда не генерирует fence.  
**Фикс:** Поиск `{graph_deltas:` без обязательного фенса; fallback-парсинг из конца ответа.

**Ключевые файлы:** `agent/dispatch.py`, `agent/wiki.py`, `agent/dspy_lm.py`
