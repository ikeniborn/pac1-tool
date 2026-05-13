---
wiki_sources:
  - "[[docs/superpowers/specs/2026-05-12-structured-sql-pipeline-design.md]]"
wiki_updated: 2026-05-13
wiki_status: developing
wiki_outgoing_links:
  - "[[sql-pipeline-overview]]"
tags:
  - ecom1-agent
  - documentation
aliases:
  - "SGR"
  - "Schema Guide Reasoning"
---

# SGR Pattern (Schema → Guide → Reasoning)

Архитектурный паттерн для каждого LLM-вызова в pipeline. Обеспечивает структурированность ввода/вывода, явное управление инструкциями и обязательную цепочку мышления.

## Основные характеристики

| Слой | Значение | Реализация |
|------|---------|------------|
| **Schema** | Типизированный ввод/вывод на каждом шаге | Pydantic `BaseModel` с typed fields для каждой фазы |
| **Guide** | Инструкции фазы загружаются из файла | `data/prompts/<phase>.md` → системный промпт |
| **Reasoning** | Обязательный CoT-field в каждом выходе | Все output-модели содержат `reasoning: str` первым полем |

```
data/prompts/<phase>.md  [Guide]
        ↓
   call_llm_raw()  →  JSON response
        ↓
Pydantic(reasoning: str, ...)  [Schema + Reasoning]
```

## Применение в pipeline

Паттерн применяется ко всем LLM-фазам: SQL_PLAN, LEARN, ANSWER, EVALUATE. Детерминированные фазы VALIDATE и EXECUTE не используют LLM — SGR к ним не применяется.

## Связанные Pydantic-модели

Определены в `agent/models.py`:

- `SqlPlanOutput` — `reasoning: str`, `queries: list[str]`
- `LearnOutput` — `reasoning: str`, `conclusion: str`, `rule_content: str`
- `AnswerOutput` — `reasoning: str`, `message: str`, `outcome: Literal[...]`, `grounding_refs: list[str]`, `completed_steps: list[str]`
- `PipelineEvalOutput` — `reasoning: str`, `score: float`, `comment: str`, `prompt_optimization: list[str]`, `rule_optimization: list[str]`

## Обоснование выбора

До введения SGR `loop.py` использовал открытый agentic loop: LLM сам решал порядок вызовов инструментов, что приводило к пропуску SQL-валидации, чтению `/proc/catalog/` файлов напрямую и отсутствию механизма обучения на ошибках. SGR устраняет эти проблемы структурными гарантиями.
