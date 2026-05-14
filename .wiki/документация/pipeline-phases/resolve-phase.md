---
wiki_sources:
  - "[[data/prompts/resolve.md]]"
  - "[[docs/superpowers/specs/2026-05-14-api-update-carts-design.md]]"
wiki_updated: 2026-05-14
wiki_status: developing
wiki_outgoing_links:
  - "[[pipeline-phases/answer-phase]]"
  - "[[pipeline-phases/sql-plan-phase]]"
wiki_external_links: []
tags:
  - ecom1-agent
aliases:
  - "RESOLVE"
  - "Resolve Phase"
  - "Фаза разрешения идентификаторов"
---

# Фаза RESOLVE

Фаза value-resolution в пайплайне агента: идентифицирует конкретные идентификаторы в тексте задачи (бренды, модели, виды, значения атрибутов, cart_id) и генерирует discovery SQL-запросы для подтверждения их точного хранимого написания в базе данных.

## Основные характеристики

- Выходной формат: чистый JSON (первый символ обязательно `{`)
- Поле `reasoning` — краткое объяснение, какие термины найдены и почему
- Поле `candidates` — список объектов с полями `term`, `field`, `discovery_query`
- Поле `field` принимает значения: `brand`, `model`, `kind`, `attr_key`, `attr_value`, `cart_id`
- Только discovery-запросы: `SELECT DISTINCT` с `LIKE` или `DISTINCT`; запрещены JOIN, подзапросы, агрегаты
- Использует SQLite: `LIKE` (не `ILIKE`)

## Паттерны discovery-запросов

| Тип поля | Шаблон запроса |
|----------|----------------|
| `brand` | `SELECT DISTINCT brand FROM products WHERE brand LIKE '%<term>%' LIMIT 10` |
| `model` | `SELECT DISTINCT model FROM products WHERE model LIKE '%<term>%' LIMIT 10` |
| `kind` | `SELECT DISTINCT name FROM kinds WHERE name LIKE '%<term>%' LIMIT 10` |
| `attr_key` | `SELECT DISTINCT key FROM product_properties WHERE key LIKE '%<term>%' LIMIT 10` |
| `attr_value` (ключ известен) | `SELECT DISTINCT value_text FROM product_properties WHERE key = '<key>' AND value_text LIKE '%<val>%' LIMIT 10` |
| `attr_value` (ключ неизвестен) | `SELECT DISTINCT value_text FROM product_properties WHERE value_text LIKE '%<val>%' LIMIT 10` |
| `cart_id` | `SELECT DISTINCT cart_id FROM carts WHERE customer_id = '<из_AGENT_CONTEXT>' LIMIT 10` |

## Покрытие значений атрибутов (обязательно)

Для **каждого** значения атрибута, упомянутого в задаче — размеры, цветовые семейства, классы защиты, типы машин и т.д. — генерировать один кандидат `attr_value`. Включая короткие значения: однобуквенные размеры ('M', 'L', 'S', 'XL') и короткие enum-значения ('basic', 'blue', 'clamp'). Не пропускать значения из-за краткости или «очевидности».

## customer_id — особый случай

`customer_id` поступает из блока `# AGENT CONTEXT` (заполняется `/bin/id` при инициализации). Discovery-кандидат для `customer_id` **не генерировать** — значение уже подтверждено.

## История изменений

- **2026-05-14** (из [[docs/superpowers/specs/2026-05-14-api-update-carts-design.md]]): добавлен тип поля `cart_id` в поле `field` и соответствующий паттерн discovery-запроса для корзин; добавлено примечание про `customer_id` из `# AGENT CONTEXT`.
