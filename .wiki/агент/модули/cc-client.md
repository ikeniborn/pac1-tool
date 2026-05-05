---
wiki_sources:
  - "agent/cc_client.py"
wiki_updated: 2026-05-06
wiki_status: stub
tags:
  - cc-client
  - dispatch
aliases:
  - "cc_complete"
  - "Claude Code tier"
  - "iclaude subprocess"
---

# CC Client (agent/cc_client.py)

Тир Claude Code: запускает `iclaude` CLI как stateless подпроцесс. Обходит Anthropic SDK — использует OAuth через iclaude. Mutual exclusive с Anthropic тиром: активируется только при `provider='claude-code'`, не cascades в OpenRouter/Ollama при failure.

## Основные характеристики

### Изоляция от хостового проекта

- `cwd=<tmpdir>` — нет auto-discovery CLAUDE.md
- `--no-save` — нет session history в `~/.claude/projects`
- `--strict-mcp-config` — блокирует user MCP servers
- `--mcp-config <empty>` — нет инструментов у модели (stateless LLM)
- `--print`, `--output-format json` — headless режим
- `CC_STRIP_PROJECT_ENV=1` → strip `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`

### Поведение на failure

Возвращает `None` после внутренних retries. `dispatch.py` не переходит к следующему тиру — caller (loop.py) обрабатывает None как retry шага.

### Ограничения

Нет `--seed`, нет `response_format`. JSON-only output запрашивается через system-prompt trailer. Отсюда non-determinism → majority-vote классификация на CC тире.

## Env-переменные

- `CC_ENABLED=1` — активировать тир
- `ICLAUDE_CMD` (default "iclaude") — путь к CLI
- `CC_MAX_RETRIES` (default 2) — кол-во попыток
- `CC_RETRY_DELAY_S` (default 4.0) — задержка между попытками
- `CC_STRIP_PROJECT_ENV=1` — strip API keys перед запуском subprocess

## Связанные концепции

- [[dispatch]] — cc_complete импортируется как `_cc_complete` в dispatch.py
- [[classifier]] — majority-vote режим на CC тире
