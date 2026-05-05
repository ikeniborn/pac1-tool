---
wiki_sources:
  - docs/superpowers/specs/2026-04-29-wiki-big-bang-restructure-design.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [design, wiki, knowledge-accumulation, add-only, provenance]
---

# Wiki Big Bang Restructure

**Дата:** 2026-04-29 | **Priority:** Quality-first

Полная перестройка wiki-pipeline по принципам паттерна Karpathy: add-only синтез, provenance tracking, knowledge_aspects, quality lifecycle.

## Принципы

1. **Add-only synthesis** — LLM только добавляет к секциям, не перезаписывает
2. **Provenance tracking** — `fragment_ids` в meta-header, каждый фрагмент обрабатывается ровно раз
3. **knowledge_aspects** — что извлекать, формализовано в `data/task_types.json`
4. **Quality lifecycle** — `nascent → developing → mature` на основе `fragment_count`
5. **Граф без изменений** — `wiki_graph.py` остаётся как есть

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
```

## Add-only синтез (aspect-by-aspect)

```
parse_page_sections(existing) → {aspect_id: section_content}
for each knowledge_aspect:
    existing_section = sections.get(aspect_id, "")
    relevant_fragments = filter_by_aspect(new_fragments, aspect)
    LLM(existing_section, relevant_fragments) → merged_section  # add-only
write_page(meta_header + merged_sections)
```

## knowledge_aspects в `data/task_types.json`

```json
"email": {
  "knowledge_aspects": [
    {"id": "workflow_steps", "prompt": "Proven step sequences leading to OUTCOME_OK"},
    {"id": "pitfalls",       "prompt": "Risks, failure patterns, and what to avoid"},
    {"id": "shortcuts",      "prompt": "Task-specific optimizations"}
  ]
}
```

Default набор (для типов без явных aspects): `workflow_steps`, `pitfalls`, `shortcuts`.

## Provenance tracking

```python
def _get_pending_fragments(category: str, page_meta: dict) -> list[Path]:
    done_ids = set(page_meta.get("fragment_ids", []))
    return [f for f in all_frags if f.stem not in done_ids]
```

Fail-tolerance: если lint прерывается — следующий прогон продолжит с того же места.

## Карта изменений

| Файл | Изменения |
|---|---|
| `agent/wiki.py` | aspect-by-aspect синтез, `_read_page_meta`, `_write_page_meta`, `_parse_page_sections` |
| `agent/task_types.py` | `knowledge_aspects(task_type)` + `_DEFAULT_ASPECTS` |
| `data/task_types.json` | поле `knowledge_aspects` для каждого типа |
| `agent/prompt.py` | `[draft]` для nascent pages |
| `agent/evaluator.py` | char limit масштабируется по quality |
