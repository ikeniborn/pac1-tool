---
wiki_sources:
  - "[[docs/superpowers/specs/2026-05-14-api-update-carts-design.md]]"
wiki_updated: 2026-05-14
wiki_status: developing
wiki_outgoing_links:
  - "[[pipeline-phases/sql-plan-phase]]"
  - "[[pipeline-phases/resolve-phase]]"
  - "[[pipeline-phases/answer-phase]]"
  - "[[agent-modules/prephase]]"
  - "[[agent-modules/pipeline]]"
wiki_external_links:
  - "https://github.com/bitgn/sample-agents/blob/main/proto/bitgn/vm/ecom/ecom.proto"
  - "https://github.com/bitgn/sample-agents/blob/main/ecom-py/agent.py"
tags:
  - ecom1-agent
aliases:
  - "API Update Carts"
  - "Shopping Carts Support"
  - "Поддержка корзин"
---

# API Update + Shopping Carts Support

Дизайн-документ (статус: Approved, 2026-05-14) описывает синхронизацию с upstream ecom API и добавление поддержки домена shopping carts.

## Контекст

Upstream `bitgn/sample-agents` ecom API изменился:
1. RPC `Context` deprecated → заменён exec-утилитами `/bin/date` и `/bin/id`
2. Ряд полей `WriteResponse`, `StatResponse`, `ExecResponse` deprecated (паттерн action-handler удалён)
3. Новые runtime-утилиты: `/bin/date`, `/bin/id`, `/bin/checkout`
4. Новая world entity: shopping carts (покупатели могут задавать вопросы о своих корзинах)

Обязательная init-последовательность агента:
```python
must = [
    Req_Tree(level=2, root="/"),
    Req_Read(path="/AGENTS.MD"),
    Req_Exec(path="/bin/date"),
    Req_Exec(path="/bin/id"),
]
```

## Ограничения

- `ecom_pb2.py` — не регенерировать (buf не установлен; deprecated поля — только метаданные, wire format не меняется)
- `ecom_connect.py` — метод `context()` сохранить (deprecated, не используется, безвреден)
- Архитектура пайплайна не меняется (SQL-based lookup pipeline)
- `/bin/checkout` — только exec, не SQL-операция

## Компоненты изменений

### agent/prephase.py — обязательные init-вызовы

Новые поля `PrephaseResult`:
```python
agent_id: str = ""      # stdout из /bin/id
current_date: str = ""  # stdout из /bin/date
```

В начало `run_prephase()` добавляются best-effort вызовы (try/except; при ошибке → пустая строка):
```python
date_result = vm.exec(ExecRequest(path="/bin/date"))
current_date = getattr(date_result, "stdout", "").strip()

id_result = vm.exec(ExecRequest(path="/bin/id"))
agent_id = getattr(id_result, "stdout", "").strip()
```

`_SCHEMA_TABLES` расширен:
```python
_SCHEMA_TABLES = ["products", "product_properties", "inventory", "kinds", "carts", "cart_items"]
```
Если `carts`/`cart_items` отсутствуют на сервере — `PRAGMA table_info(carts)` вернёт пустоту, `_build_schema_digest` тихо пропустит.

### agent/pipeline.py — блок AGENT CONTEXT

`_build_static_system()` получает два новых параметра: `agent_id: str = ""`, `current_date: str = ""`.

Для фаз `sql_plan` и `learn` инжектируется блок перед VAULT RULES:
```python
if (agent_id or current_date) and phase in ("sql_plan", "learn"):
    ctx_lines = []
    if current_date:
        ctx_lines.append(f"date: {current_date}")
    if agent_id:
        ctx_lines.append(f"id: {agent_id}")
    blocks.insert(0, {"type": "text", "text": "# AGENT CONTEXT\n" + "\n".join(ctx_lines)})
```

Все три вызова `_build_static_system()` в `run_pipeline()` передают `agent_id=pre.agent_id, current_date=pre.current_date`.

### Промпты (data/prompts/)

| Файл | Изменение |
|------|-----------|
| `sql_plan.md` | Добавлены разделы "Cart and Basket Queries" и "/bin/checkout" |
| `answer.md` | Добавлен раздел "Cart Answers" в Grounding Refs |
| `resolve.md` | Добавлен тип `cart_id` в `field`, паттерн discovery-запроса для корзин |

### agent/schema_gate.py

Проверка: если таблица отсутствует в `schema_digest` — пропускать column validation для этой таблицы (неизвестная таблица = не нарушение схемы; колонки будут проверены на этапе EXPLAIN).

## Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `proto/bitgn/vm/ecom/ecom.proto` | Аннотации deprecated (только документация) |
| `agent/prephase.py` | `/bin/date` + `/bin/id` init; новые поля PrephaseResult; `_SCHEMA_TABLES` расширен |
| `agent/pipeline.py` | Блок AGENT CONTEXT в `_build_static_system()`; обновлены вызывающие |
| `data/prompts/sql_plan.md` | Cart query patterns + /bin/checkout guidance |
| `data/prompts/answer.md` | Cart grounding_refs guidance |
| `data/prompts/resolve.md` | Cart discoverable terms |
| `agent/schema_gate.py` | Проверка/исправление обработки неизвестных таблиц |

## Вне области

- Регенерация pb2 (buf недоступен; deprecated поля не влияют на wire format)
- Фаза checkout в пайплайне (отложено до появления реальных типов задач)
- Предположения о схеме cart сверх `carts`/`cart_items` (реальная схема обнаруживается через AGENTS.MD + .schema в runtime)
