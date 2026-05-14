# Spec: OLLAMA_API_KEY поддержка

**Дата:** 2026-05-14  
**Статус:** Approved

## Контекст

Агент использует OpenAI-совместимый Ollama-клиент для локальных/cloud моделей. URL задаётся через `OLLAMA_BASE_URL`. При подключении к внешнему VPS или OpenAI-совместимому прокси (Together, RunPod, и др.) требуется API-ключ аутентификации. Сейчас ключ захардкожен как `"ollama"`.

## Цель

Позволить задавать API-ключ Ollama через env var, не меняя контракт `run_agent()` и не ломая локальный деплой.

## Решение

Добавить env var `OLLAMA_API_KEY`. Пустое значение → fallback `"ollama"` (поведение как сейчас).

## Изменения

### agent/llm.py

```python
# было:
ollama_client = OpenAI(base_url=_OLLAMA_URL, api_key="ollama", timeout=_HTTP_TIMEOUT)

# станет:
_OLLAMA_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")
ollama_client = OpenAI(base_url=_OLLAMA_URL, api_key=_OLLAMA_KEY, timeout=_HTTP_TIMEOUT)
```

### .env.example

Добавить строку рядом с `OLLAMA_BASE_URL` — **без значения**, только как документация:
```
OLLAMA_API_KEY=           # ключ для OpenAI-совместимого прокси (пусто = "ollama"); значение — только в .secrets
```

### .secrets.example

Добавить строку (реальное значение только здесь):
```
# OLLAMA_API_KEY=sk-...
```

## Backward compatibility

Без `OLLAMA_API_KEY` поведение идентично текущему. Никаких изменений в сигнатурах функций.

## Тестирование

1. Без `OLLAMA_API_KEY` — локальный Ollama работает как раньше.
2. С `OLLAMA_API_KEY=sk-...` + `OLLAMA_BASE_URL=https://vps/v1` — запрос уходит с заголовком `Authorization: Bearer sk-...`. Проверка: `make task TASKS='t01'`.
3. Неверный ключ → `AuthenticationError` от OpenAI SDK. `AuthenticationError` не содержит ни одного слова из `TRANSIENT_KWS`/`HARD_CONNECTION_KWS` (`llm.py:215–228`) → retry не выполняется → attempt-цикл прерывается (`break`) → plain-text retry также падает с 401 → функция возвращает `None`. Исключение не пробрасывается; pipeline обрабатывает `None` как штатный сбой.
