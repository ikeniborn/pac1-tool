---
wiki_sources:
  - "agent/json_extract.py"
wiki_updated: 2026-05-06
wiki_status: developing
tags:
  - dispatch
  - json
  - parsing
  - loop
aliases:
  - "_extract_json_from_text"
  - "_normalize_parsed"
  - "7-level priority extraction"
---

# JSON Extract (agent/json_extract.py)

Модуль извлечения JSON из свободного текстового вывода LLM. Вынесен из `loop.py` для уменьшения God Object. Реализует 7-уровневый приоритетный парсинг и нормализацию в структуру `NextStep`.

## Публичный API

| Функция | Назначение |
|---------|------------|
| `_extract_json_from_text(text)` | 7-уровневое извлечение наиболее actionable JSON-объекта из текста (FIX-146) |
| `_normalize_parsed(parsed)` | Нормализация сырого словаря в валидную структуру NextStep (FIX-207) |
| `_obj_mutation_tool(obj)` | Вернуть имя mutation-инструмента или None |
| `_richness_key(obj)` | Детерминированный tie-break для кандидатов одного тира (FIX-212) |

## Алгоритм `_extract_json_from_text` — 7 уровней приоритета

1. ` ```json ``` ` fenced-блок — явный, возвращается немедленно
2. Первый объект с mutation-инструментом (`write`/`delete`/`move`/`mkdir`) — bare или wrapped  
   _Ратионал_: ответы с несколькими действиями часто заканчиваются `report_completion` ПОСЛЕ записей; исполнение `report_completion` первым пропустило бы записи
3. Первый bare-объект с любым известным `tool` (не mutation: `search`/`read`/`list`)
4. Первый полный NextStep (`current_state + function`) с non-report_completion tool
5. Первый полный NextStep с любым tool (включая `report_completion`)
6. Первый объект с ключом `function`
7. Богатейший кандидат (по `_richness_key`)
8. YAML fallback — для моделей, выдающих YAML вместо JSON

### Специальные случаи

- **FIX-265 — Multi-step plan detection**: при ≥3 полных NextStep-объектов в ответе (модель выдала план) — берётся **первый non-mutation шаг** для пошагового исполнения. Без этой проверки mutation-приоритет подхватил бы write, аргументы к которому ещё не были вычислены.
- **FIX-150 — Req_XXX prefix**: некоторые модели (minimax) эмитируют `Action: Req_Read({...})` без поля `tool` внутри JSON. Regex `_REQ_PREFIX_RE` обнаруживает префикс, инжектирует `tool` из словаря `_REQ_CLASS_TO_TOOL`.
- **FIX-401 — bracket-balance repair**: усечённый JSON на EOF — `}` добавляются до баланса скобок, затем снова пробуется парсинг.
- **json5 fallback**: при `json.JSONDecodeError` делается попытка `json5.loads` (опциональная зависимость).

## Нормализация `_normalize_parsed` (FIX-207)

Приводит сырой словарь к валидной структуре NextStep:

- Bare `{"tool": ..., ...}` без `current_state` → оборачивается в полную структуру с `current_state="continuing"`.
- `plan_remaining_steps_brief`: фильтрует пустые, обрезает до 5 элементов.
- Добавляет `task_completed: false` если отсутствует.

## Константы

- `_MUTATION_TOOLS` — `frozenset{"write", "delete", "move", "mkdir"}`
- `_REQ_CLASS_TO_TOOL` — маппинг `req_read → "read"` и т.д. (9 инструментов)

## Связанные концепции

- [[loop]] — использует весь публичный API этого модуля
- [[dispatch]] — экспортирует `CLI_YELLOW`/`CLI_CLR`, используемые для отладочных print
