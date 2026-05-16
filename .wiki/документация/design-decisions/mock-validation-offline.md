---
wiki_sources:
  - "[[.worktrees/mock-validation/data/prompts/mock_gen.md]]"
wiki_updated: 2026-05-16
wiki_status: stub
wiki_outgoing_links:
  - "[[pipeline-phases/mock-gen-phase]]"
  - "[[pipeline-phases/test-generation-phase]]"
wiki_external_links: []
tags:
  - ecom1-agent
  - documentation
aliases:
  - "offline mock validation"
  - "mock pipeline validation"
---

# Офлайн-валидация пайплайна через синтетические моки

Архитектурное решение: вместо исполнения SQL против live ECOM-базы данных пайплайн агента валидируется через LLM-сгенерированные синтетические CSV-данные (`mock_results`) и Python-assertions (`answer_assertions`). Это позволяет проверять логику ответа агента без сетевого подключения к ECOM VM.

## Основные характеристики

| Аспект | Подход |
|--------|--------|
| Источник данных | LLM генерирует реалистичные CSV по схеме ECOM |
| Изоляция | Нет обращений к ECOM VM, нет Connect-RPC вызовов |
| Покрытие | Проверяется outcome агента и наличие ключевых идентификаторов в answer.message |
| Ограничения | Не покрывает реальное поведение SQL-запросов против живых данных |

## Обоснование выбора

Live-валидация через `validate_recommendation` требует доступа к BITGN_API_KEY, BENCHMARK_HOST и полного прохода пайплайна через ECOM VM. Для случаев, когда необходима быстрая изолированная проверка — тестирование новых prompt-фаз, CI без ECOM-доступа — офлайн-подход через mock_gen обеспечивает достаточный уровень уверенности с нулевой инфраструктурной зависимостью.

## Связь с TDD-пайплайном

В отличие от фазы [[pipeline-phases/test-generation-phase|Test Generation]], которая генерирует `test_sql` + `test_answer` для реальных SQL-результатов, фаза mock_gen генерирует сами результаты (`mock_results`). Оба подхода используют один контракт `answer`-dict: `outcome`, `message`, `grounding_refs`, `reasoning`, `completed_steps`.
