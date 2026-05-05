---
wiki_sources:
  - docs/architecture/08-harness-protocol.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, harness, pcm, grpc, protobuf]
---

# Harness и PCM протокол

Два внешних интерфейса через gRPC-Connect over HTTP.

## Два сервиса

- **HarnessService** — control plane: `GetBenchmark`, `StartRun`, `StartTrial`, `EndTrial`, `SubmitRun`
- **PcmRuntime** — data plane: 9 vault-инструментов + `answer`

## PcmRuntime: 9 инструментов

| Tool | Request | Назначение |
|---|---|---|
| `tree` | `root`, `level` | Рекурсивное дерево vault |
| `find` | `root`, `name`, `type`, `limit` | Поиск по имени |
| `search` | `root`, `pattern`, `limit` | Full-text поиск |
| `list` | `path` | Листинг директории |
| `read` | `path`, `number`, `start_line`, `end_line` | Чтение файла |
| `write` | `path`, `content`, `start_line`, `end_line` | Create/overwrite/append |
| `delete` | `path` | Удаление |
| `mkdir` | `path` | Создание директории |
| `move` | `from_name`, `to_name` | Переименование |
| `context` | — | Метаданные: date, user |
| `answer` | `message`, `outcome`, `refs` | Финализация |

## Outcome enum

- `OUTCOME_OK` — задача выполнена
- `OUTCOME_DENIED_SECURITY` — injection / scope
- `OUTCOME_NONE_CLARIFICATION` — неоднозначная задача
- `OUTCOME_NONE_UNSUPPORTED` — внешний сервис
- `OUTCOME_ERR_INTERNAL` — внутренняя ошибка

## Pydantic layer

`agent/models.py`: `NextStep` + 10 discriminated unions `Req_Read`, `Req_Write`, ... → convert к protobuf → `vm.<tool>(req)`.

## Регенерация стабов

```bash
make proto  # или: buf generate
```

`bitgn/` — сгенерированы, ручные правки будут перезаписаны.

## Таймауты

- HTTP read: 180s
- Connect: 10s
- При 429/502/503: retry с exponential backoff
