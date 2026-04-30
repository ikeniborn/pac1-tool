# Wiki Big Bang Restructure — Design Spec

**Date:** 2026-04-29  
**Status:** Draft  
**Priority:** Quality-first

---

## Overview

Полная перестройка wiki-pipeline агента по принципам паттерна Karpathy (llm-wiki):
add-only синтез, provenance tracking, knowledge_aspects, quality lifecycle.
Граф (`wiki_graph.py`) не меняется. Чистый старт без rebuild-скрипта — вики
накапливается заново органически по мере новых прогонов.

---

## Принципы

1. **Add-only synthesis** — LLM никогда не перезаписывает существующий контент,
   только добавляет новые инсайты к секциям. Устраняет хрупкость FIX-N PRESERVE-директив.

2. **Provenance tracking** — каждая страница хранит список фрагментов, уже учтённых
   в синтезе (`fragment_ids`). Lint инкрементален: каждый фрагмент обрабатывается ровно раз.

3. **knowledge_aspects** — что именно извлекать, формализовано в `data/task_types.json`
   вместо inline-промптов. Каждый aspect синтезируется отдельно.

4. **Quality lifecycle** — `nascent → developing → mature` на основе `fragment_count`.
   Влияет на доверие evaluator'а и маркировку в prompt агента.

5. **Граф без изменений** — `wiki_graph.py` остаётся как есть. Единственное добавление:
   `wiki_mature` тег для нодов из mature-страниц.

---

## Новый формат страницы

```markdown
<!-- wiki:meta
category: email
quality: nascent
fragment_count: 3
fragment_ids: [t01_20260101T120000Z, t04_20260103T130000Z]
last_synthesized: 2026-04-29
aspects_covered: workflow_steps,pitfalls
-->

## Workflow steps
...

## Key pitfalls
...

## Shortcuts
...

## Contract constraints
...
```

Meta-заголовок — HTML-комментарий в начале файла, не меняет LLM-потребление страницы.

---

## Quality lifecycle

| Уровень | fragment_count | Поведение |
|---------|---------------|-----------|
| `nascent` | 0–4 | Заголовок секции в prompt'е: `Wiki: {type} Patterns [draft]` |
| `developing` | 5–14 | Нормальный инжект, без изменений |
| `mature` | 15+ | Evaluator получает увеличенный лимит символов; граф-ноды получают тег `wiki_mature` |

Quality пересчитывается автоматически при каждом lint-прогоне из `fragment_count`.

---

## Add-only синтез (aspect-by-aspect)

### Текущий подход (проблемный)

```
[existing page] + [new fragments] → LLM → перезапись всей страницы
```

FIX-N PRESERVE-директивы в промптах защищают секции, но хрупко.

### Новый подход

```
parse_page_sections(existing)  →  {aspect_id: section_content}

for each knowledge_aspect:
    existing_section = sections.get(aspect_id, "")
    relevant_fragments = filter_by_aspect(new_fragments, aspect)
    LLM(existing_section, relevant_fragments)  →  merged_section
    sections[aspect_id] = merged_section

write_page(meta_header + merged_sections)
update_meta(fragment_ids, fragment_count, quality, last_synthesized)
```

LLM видит одну секцию за раз → не может случайно удалить другую.
Промпт: "добавь новые инсайты к этой секции, ничего не удаляй из существующего".
PRESERVE-банеры выживают автоматически — они часть existing_section.

---

## Provenance tracking

```python
def _get_pending_fragments(category: str, page_meta: dict) -> list[Path]:
    all_frags = sorted((_FRAGMENTS_DIR / category).glob("*.md"))
    done_ids = set(page_meta.get("fragment_ids", []))
    return [f for f in all_frags if f.stem not in done_ids]
```

`fragment_ids` пополняется после каждого успешного synthesis.
Если lint падает на середине — следующий прогон продолжит с того же места.

---

## knowledge_aspects в `data/task_types.json`

### Структура поля

```json
"email": {
  "knowledge_aspects": [
    {"id": "workflow_steps", "prompt": "Proven step sequences leading to OUTCOME_OK"},
    {"id": "pitfalls",       "prompt": "Risks, failure patterns, and what to avoid"},
    {"id": "shortcuts",      "prompt": "Task-specific optimizations and lookup shortcuts"}
  ]
}
```

### Дефолтный набор (для типов без явных aspects)

```python
_DEFAULT_ASPECTS = [
    {"id": "workflow_steps", "prompt": "Proven step sequences"},
    {"id": "pitfalls",       "prompt": "Key risks and failure patterns"},
    {"id": "shortcuts",      "prompt": "Task-specific insights"},
]
```

`agent/task_types.py` экспортирует `knowledge_aspects(task_type: str) -> list[dict]`.

---

## Граф — минимальные изменения

`wiki_graph.py` не трогаем. Единственное дополнение в `_run_pages_lint_pass()`:

```python
if meta.get("quality") == "mature" and "wiki_mature" not in tags:
    item["tags"] = [*tags, "wiki_mature"]
```

Это позволяет retrieval-scoring и evaluator'у повышать приоритет нодов
из зрелых страниц.

---

## Карта изменений

| Файл | Изменения |
|------|-----------|
| `agent/wiki.py` | `_llm_synthesize()` → aspect-by-aspect; добавить `_read_page_meta()`, `_write_page_meta()`, `_parse_page_sections()`, `_page_quality()`; lint использует `fragment_ids` для инкрементальности |
| `agent/task_types.py` | `knowledge_aspects(task_type)` + `_DEFAULT_ASPECTS` |
| `data/task_types.json` | Поле `knowledge_aspects` для каждого типа |
| `agent/prompt.py` | `load_wiki_patterns()` добавляет `[draft]` для `nascent` |
| `agent/evaluator.py` | `EVALUATOR_WIKI_MAX_CHARS` масштабируется по quality |
| `agent/wiki.py` (доп.) | `+wiki_mature` тег в `_run_pages_lint_pass()` при quality==mature |

**Не меняется:** `agent/wiki_graph.py` (полностью), `data/wiki/graph.json`,
fragment-формат, `promote_successful_pattern()`, `promote_verified_refusal()`,
`load_wiki_base()`, security gates, DSPy pipeline.

---

## Чистый старт

Rebuild-скрипт не нужен. `_read_page_meta()` при отсутствии meta-заголовка
возвращает `{"fragment_ids": [], "quality": "nascent", "fragment_count": 0}`.
Lint первого прогона с новым кодом находит все fragments как pending (ни один
не в `fragment_ids`) и синтезирует страницу заново в новом формате, перезаписывая
старую.

Органическая пересборка: вики достигает `developing` после 5–14 прогонов,
`mature` — после 15+.

---

## Что НЕ входит в scope

- WikiLinks между страницами — формат pages остаётся plain Markdown для LLM
- Human-facing форматирование — pages оптимизированы под LLM-потребление
- `_index.md` / `_log.md` — граф уже выполняет роль индекса
- bootstrap-операция — task_types уже определены в `data/task_types.json`
- Изменение fragment-формата — `format_fragment()` остаётся как есть
