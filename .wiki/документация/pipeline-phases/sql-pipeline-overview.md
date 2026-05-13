---
wiki_sources:
  - "[[docs/superpowers/specs/2026-05-12-structured-sql-pipeline-design.md]]"
  - "[[docs/superpowers/specs/2026-05-12-eval-driven-rules-design.md]]"
  - "[[docs/superpowers/specs/2026-05-13-schema-gate-sku-fix-design.md]]"
wiki_updated: 2026-05-13
wiki_status: developing
wiki_outgoing_links:
  - "[[sgr-pattern]]"
  - "[[schema-gate]]"
  - "[[evaluator]]"
  - "[[pipeline-py]]"
tags:
  - ecom1-agent
  - documentation
aliases:
  - "SQL Pipeline"
  - "phase pipeline"
  - "pipeline state machine"
---

# SQL Pipeline (детерминированный фазовый пайплайн)

Детерминированный pipeline — замена открытому agentic loop (`loop.py`) для catalogue lookup задач. Каждая фаза выполняет строго определённую функцию; переходы между фазами жёстко заданы кодом, не LLM.

## Основные характеристики

Пайплайн реализован в `agent/pipeline.py`. Все LLM-вызовы следуют [[sgr-pattern]] (Schema → Guide → Reasoning).

### Фазы пайплайна

| Фаза | Тип | Назначение |
|------|-----|-----------|
| **SQL_PLAN** | LLM | Планирование SQL-запросов — `SqlPlanOutput(reasoning, queries: list[str])` |
| **VALIDATE** | детерминированная | EXPLAIN каждого запроса через `/bin/sql`; синтаксические ошибки → LEARN |
| **EXECUTE** | детерминированная | Исполнение запросов, сбор результатов; пустой результат → LEARN |
| **LEARN** | LLM | Диагностика ошибки → `LearnOutput(reasoning, conclusion, rule_content)` → в-сессионные правила |
| **ANSWER** | LLM | Синтез финального ответа — `AnswerOutput(reasoning, message, outcome, grounding_refs, completed_steps)` |
| **EVALUATE** | LLM (опционально) | Оценка качества trace → `PipelineEvalOutput` → `data/eval_log.jsonl` |

### Управление циклами

- Максимум 3 цикла SQL_PLAN → VALIDATE → EXECUTE
- После 3 неудачных циклов: ANSWER с `OUTCOME_NONE_CLARIFICATION`
- Каждый LEARN добавляет не более 1 правила в `session_rules` (в-памяти, только текущий запуск)

### Инъекция правил в систем-промпт

| Секция | SQL_PLAN | LEARN | ANSWER | EVALUATE |
|--------|----------|-------|--------|----------|
| AGENTS.MD | ✓ | ✓ | ✓ | ✓ |
| pipeline_rules (verified=true) | ✓ | ✓ | — | — |
| security_gates summary | ✓ | — | — | — |
| phase guide (data/prompts/*.md) | ✓ | ✓ | ✓ | ✓ |
| session auto-rules | ✓ | ✓ | — | — |

VALIDATE и EXECUTE — детерминированные, без LLM-вызова и системного промпта.

## Prephase (до запуска пайплайна)

`prephase.py` выполняется один раз перед пайплайном:
1. Читает `/AGENTS.MD` с VM → базовый системный промпт
2. Запускает `/bin/sql .schema` → схема БД (сохраняется в `PrephaseResult.db_schema`)
3. Загружает `data/rules/*.yaml` (только `verified: true`) → инъекция как markdown-блоки

## Evaluator

Запускается **после** `vm.answer()`, если `EVAL_ENABLED=1`. Оценивает качество pipeline trace без доступа к ground-truth score (он приходит только в `EndTrialResponse`). Результат сохраняется в `data/eval_log.jsonl`.

## Rule Lifecycle

```
LEARN phase → session_rules (in-memory, текущий запуск)
    ↓
Evaluator → data/eval_log.jsonl (rule_optimization suggestions)
    ↓
scripts/propose_optimizations.py → data/rules/sql-NNN.yaml (verified: false)
    ↓
Человек: set verified: true → применяется на следующих запусках
```
