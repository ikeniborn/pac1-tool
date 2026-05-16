---
wiki_sources:
  - "[[.worktrees/mock-validation/data/prompts/mock_gen.md]]"
wiki_updated: 2026-05-16
wiki_status: stub
wiki_outgoing_links:
  - "[[pipeline-phases/test-generation-phase]]"
  - "[[pipeline-phases/answer-phase]]"
wiki_external_links: []
tags:
  - ecom1-agent
  - documentation
aliases:
  - "mock_gen"
  - "mock generation phase"
  - "offline validation"
---

# Фаза генерации моков (Mock Gen Phase)

Фаза офлайн-валидации пайплайна агента, в которой LLM генерирует синтетические CSV-результаты и Python-assertions для задачи, не обращаясь к реальной базе данных ECOM. Используется для проверки корректности ответа агента в изолированной среде.

## Основные характеристики

- Принимает на вход: описание задачи и схему ECOM-базы данных
- Возвращает `mock_results` (1–5 CSV-строк) и `answer_assertions` (Python-функция `test_answer`)
- Ориентирована на offline-валидацию: live-подключение к БД не требуется
- Целевая схема: `products`, `product_properties`, `inventory`, `kinds`, `carts`, `cart_items`

## Генерируемые артефакты

**`mock_results`** — список CSV-строк, по одной на ожидаемый SQL-запрос пайплайна.
- Первая строка каждой CSV — заголовок, следующие — данные
- Минимум одна строка с нетривиальным значением: реалистичный SKU (например, `LAP-001`), ненулевая цена или количество, непустой `path`

**`answer_assertions`** — функция `def test_answer(sql_results, answer): ...` с проверками:
- `answer["outcome"] == "OUTCOME_OK"`
- Наличие ключевого идентификатора задачи или числового результата в `answer["message"]` через `in`-check
- Не проверяет точные формулировки и не хардкодит дословный текст задачи

## Контракт выходного JSON

```json
{
  "reasoning": "<почему именно эти моки и assertions соответствуют задаче>",
  "mock_results": ["header,cols\nval1,val2", "..."],
  "answer_assertions": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK'\n    assert 'LAP-001' in answer['message']\n"
}
```

Поле `answer` в тест-функции — dict с ключами: `reasoning`, `message`, `outcome`, `grounding_refs`, `completed_steps`.

## Anti-patterns (запрещено)

- Не утверждать точные фразы из текста задачи
- Не хардкодить алиасы колонок, специфичные для конкретной задачи
- Не генерировать `mock_results` с пустыми ключевыми полями (SKU, path, quantity)
