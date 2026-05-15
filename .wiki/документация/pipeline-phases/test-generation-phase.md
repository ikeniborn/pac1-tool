---
wiki_sources:
  - "[[data/prompts/test_gen.md]]"
wiki_updated: 2026-05-15
wiki_status: stub
wiki_outgoing_links:
  - "[[pipeline-phases/answer-phase]]"
wiki_external_links: []
tags:
  - ecom1-agent
  - documentation
aliases:
  - "TDD phase"
  - "test generation"
  - "test_gen"
---

# Фаза генерации тестов (Test Generation Phase)

Фаза TDD-пайплайна агента, в которой LLM генерирует acceptance-тесты для задачи каталога до фазы ANSWER. Тесты запускаются в изолированном subprocess (только stdlib Python) и верифицируют корректность SQL-результатов и финального ответа агента.

## Основные характеристики

- Активируется при `TDD_ENABLED=1` (env var), выполняется до фазы ANSWER
- Принимает на вход: `TASK` (вопрос пользователя), `DB_SCHEMA`, `AGENTS_MD` (vault rules)
- Генерирует две функции-теста: `test_sql` и `test_answer`
- Все тесты детерминированы, сигнализируют об ошибке через `assert` или `raise ValueError`

## Генерируемые функции

**`test_sql(results: list[str]) -> None`**
Каждый элемент `results` — CSV-строка (первая строка = заголовки, остальные = данные).
Проверяет:
- Наличие обязательных колонок в заголовке (например, `sku`, `path`)
- Непустоту результатов, если задача предполагает наличие товаров
- Плausibility числовых значений (COUNT ≥ 0)
- Для агрегатных запросов: результаты непусты, первая строка данных содержит parseable integer — конкретное имя колонки-алиаса не проверяется

**`test_answer(sql_results: list[str], answer: dict) -> None`**
Ключи `answer`: `outcome`, `message`, `grounding_refs`, `reasoning`, `completed_steps`.
Проверяет:
- `answer['outcome']` равен ожидаемой строке outcome (например, `'OUTCOME_OK'`)
- `answer['message']` непуст
- `answer['grounding_refs']` непуст при `outcome == 'OUTCOME_OK'` и когда задача предполагает найденные товары
- `answer['message']` содержит ключевые факты из задачи (бренд, тип товара и т.п.) при OK-outcome

## Правила генерации тестов

- Одна функция на тест, без классов
- Только Python stdlib; импорты — внутри тела функции
- Пустой `results` допустим для zero-count задач — не утверждать непустоту безусловно

## Anti-patterns (запрещено)

- Никаких точных строк из текста TASK с учётом регистра: вместо `assert 'Cordless Drill Driver' in answer['message']` — проверка через `.lower()` с отдельными ключевыми словами
- Никакого хардкода конкретного алиаса колонки (`'count'`, `'total'`) в проверках заголовков SQL
- Никакой проверки конкретного числового значения для COUNT-задач — только формат `<COUNT:`

## Формат вывода

Фаза возвращает чистый JSON (первый символ `{`) с полями:
- `reasoning` — анализ: ожидаемый outcome, обязательные колонки, правила непустоты
- `sql_tests` — строка с кодом функции `test_sql`
- `answer_tests` — строка с кодом функции `test_answer`
