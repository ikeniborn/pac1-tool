# Agent Improvements Design

**Date:** 2026-05-12  
**Scope:** pipeline.py, llm.py, prephase.py, orchestrator.py, sql_security.py  
**Priority:** Надёжность / корректность → Оптимизация промпта → Prompt caching

---

## 1. Контекст

Анализ графа (492 узла, 802 ребра, 34 сообщества) выявил 12 аномалий.  
God-узлы: `run_pipeline()` (17 рёбер), `load_prompt()` (19), `check_sql_queries()` (16).

---

## 2. Аномалии и решения

| ID | Файл | Проблема | Решение |
|----|------|---------|---------|
| A1 | prephase.py | `pre.log`, `pre.preserve_prefix` — мёртвые поля из loop-архитектуры | Удалить из `PrephaseResult` и тела функции |
| A2 | orchestrator.py | `build_system_prompt()` вызывается, результат выброшен | Удалить вызов и переменную `system_prompt` |
| A3 | pipeline.py | `total_in_tok/total_out_tok` всегда 0 | `_call_llm_phase()` возвращает `tok_info`, caller суммирует |
| A4 | pipeline.py | `_build_system()` пересобирает статику каждый цикл | `_build_static_system()` — один раз до цикла |
| A5 | pipeline.py | `_run_learn()` вызывается при LLM-fail SQL_PLAN | При `error_type="llm_fail"` LEARN не пишет в `session_rules` |
| A6 | llm.py | Нет Anthropic prompt caching | `system` как `list[block]` с `cache_control` на последнем статическом блоке |
| A7 | pipeline.py | LEARN не различает типы ошибок | `error_type: str` тег: `syntax/semantic/security/empty/llm_fail` |
| A8 | pipeline.py | `RulesLoader` + `load_security_gates()` — диск при каждом pipeline | Module-level lazy cache |
| A9 | pipeline.py | Evaluator in-band, блокирует возврат | `threading.Thread(daemon=False)` + `t.join(timeout=30)` в `run_agent()` |
| A10 | pipeline.py | `session_rules` растёт неограниченно | Лимит 3, FIFO при переполнении |
| A11 | orchestrator.py | Мёртвые stats-поля: `builder_*`, `contract_*`, `eval_rejection_count` | Удалить |
| A12 | sql_security.py | `_has_where_clause()` не обрабатывает подзапросы и двойные кавычки | `sqlglot.parse_one()` + fallback к старому методу |

---

## 3. Архитектура

### 3.1 Граф вызовов после изменений

```
run_agent()
├── run_prephase() → PrephaseResult {agents_md_content, db_schema}
└── run_pipeline()
    ├── _get_rules_loader()       [module-level lazy cache]
    ├── _get_security_gates()     [module-level lazy cache]
    ├── _build_static_system("sql_plan")   [1 раз]
    ├── _build_static_system("learn")      [1 раз]
    └── for cycle in [0..MAX_CYCLES]:
        │   user_msg = _build_user_msg(task_text, session_rules, last_error)
        ├── _call_llm_phase(static_sql, user_msg) → (obj, sgr, tok)
        │   total_in_tok  += tok["input"]
        │   total_out_tok += tok["output"]
        ├── check_sql_queries()
        ├── VALIDATE: EXPLAIN per query (сериально, fail-fast)
        ├── EXECUTE: per query (сериально)
        └── [on fail] _run_learn(error_type=...)
            └── session_rules.append(rule) if error_type != "llm_fail"
                session_rules = session_rules[-3:]  [FIFO лимит]

    [ФИНАЛ — всегда, success или fail]
    ├── if success: _call_llm_phase(answer_system, answer_user)
    │              vm.answer(...)
    └── if EVAL_ENABLED:
        t = threading.Thread(target=_run_evaluator_safe, daemon=False)
        t.start()
        # join в run_agent() с timeout=30s
```

### 3.2 Новые/изменённые компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| `_build_static_system(phase)` | pipeline.py | Заменяет `_build_system()`. Всегда возвращает `list[block]`. Конвертация в `str` — в `llm.py` через `_system_as_str()` |
| `_build_user_msg(task, rules, error)` | pipeline.py | Собирает динамическую часть: session_rules + task + last_error |
| `_get_rules_loader()` | pipeline.py | Lazy init module-level `RulesLoader` |
| `_get_security_gates()` | pipeline.py | Lazy init module-level `list[dict]` |
| `_call_llm_phase()` | pipeline.py | Возвращает `(obj, sgr_entry, tok_info)` вместо `(obj, sgr_entry)` |
| `_run_learn(..., error_type)` | pipeline.py | Добавляет `error_type` в user_msg; пропускает `session_rules.append` при `llm_fail` |
| `_system_as_str(system)` | llm.py | Flatten `list[block] → str` для OpenRouter/Ollama |
| `_has_where_clause(sql)` | sql_security.py | sqlglot + fallback |

---

## 4. Prompt Caching

### 4.1 Структура блоков

```python
# _build_static_system() для Anthropic тира
system_blocks = [
    {"type": "text", "text": f"# VAULT RULES\n{agents_md}"},
    {"type": "text", "text": f"# PIPELINE RULES\n{rules_md}\n\n# SECURITY GATES\n{gates_summary}"},
    {"type": "text", "text": f"# DATABASE SCHEMA\n{db_schema}"},
    {
        "type": "text",
        "text": load_prompt(phase),
        "cache_control": {"type": "ephemeral"},  # граница кэша
    },
]
```

`session_rules` и `last_error` → в `user_msg`, не в `system`. Кэш не инвалидируется между циклами.

### 4.2 Поведение по тирам

| Тир | Передача system | Кэш |
|-----|----------------|-----|
| Anthropic | `list[block]` напрямую в SDK | Explicit `cache_control`, TTL 5 мин |
| OpenRouter + Claude | `list[block]` — OpenRouter пробрасывает | Explicit через OpenRouter |
| OpenRouter + другие | `_system_as_str(list)` → `str` | Нет |
| Ollama | `_system_as_str(list)` → `str` | Implicit KV-cache — стабильный prefix гарантирован т.к. session_rules в user_msg |

### 4.3 Определение тира в `_call_raw_single_model()`

```python
provider = get_provider(model, cfg)
is_claude_via_or = (provider == "openrouter" and is_claude_model(model))

if provider == "anthropic":
    _system = system  # list[block] or str — SDK принимает оба
elif is_claude_via_or:
    _system = system  # OpenRouter пробрасывает list[block]
else:
    _system = _system_as_str(system)  # Ollama, non-Claude OpenRouter
```

---

## 5. Error Handling

### 5.1 LEARN error_type

```
SQL_PLAN LLM fail   → error_type="llm_fail"   → session_rules НЕ пополняется
SECURITY blocked    → error_type="security"    → session_rules += rule
VALIDATE fail       → error_type="syntax"      → session_rules += rule
EXECUTE empty       → error_type="empty"       → session_rules += rule
EXECUTE exception   → error_type="semantic"    → session_rules += rule
```

`error_type` включается в `sgr_trace` запись → доступен evaluator'у для дифференцированных рекомендаций.

### 5.2 session_rules лимит

```python
if learn_out and error_type != "llm_fail":
    session_rules.append(learn_out.rule_content)
    if len(session_rules) > 3:
        session_rules = session_rules[-3:]  # FIFO: удаляем самый старый
```

### 5.3 WHERE clause detection

```python
def _has_where_clause(sql: str) -> bool:
    try:
        import sqlglot
        tree = sqlglot.parse_one(sql, dialect="sqlite")
        return bool(tree.find(sqlglot.exp.Where))
    except Exception:
        stripped = re.sub(r"'[^']*'", "", sql).upper()
        return "WHERE" in stripped.split()
```

`sqlglot` добавляется в `pyproject.toml` как зависимость.

---

## 6. Evaluator Threading

```python
# pipeline.py — конец run_pipeline(), всегда
_eval_thread: threading.Thread | None = None
if _EVAL_ENABLED and _MODEL_EVALUATOR:
    _eval_thread = threading.Thread(
        target=_run_evaluator_safe,
        kwargs={...},
        daemon=False,
    )
    _eval_thread.start()

return stats, _eval_thread  # run_pipeline возвращает thread handle
```

```python
# orchestrator.py — run_agent()
stats, eval_thread = run_pipeline(...)
if eval_thread is not None:
    eval_thread.join(timeout=30)
    if eval_thread.is_alive():
        print("[orchestrator] evaluator timeout — log may be incomplete")
```

`daemon=False` гарантирует запись в лог даже при завершении benchmark. `join(timeout=30)` — hard cap на ожидание.

---

## 7. Dead Code Removal

### prephase.py

- `PrephaseResult.log` → удалить
- `PrephaseResult.preserve_prefix` → удалить
- Тело `run_prephase()`: удалить `log = [...]`, `log.append(...)`, `preserve_prefix = list(log)`

### orchestrator.py

- `build_system_prompt()` вызов + переменная `system_prompt` → удалить
- `write_wiki_fragment()` функция → удалить
- Stats поля: `builder_used`, `builder_in_tok`, `builder_out_tok`, `builder_addendum`, `contract_rounds_taken`, `contract_is_default`, `eval_rejection_count` → удалить
- `run_pipeline()` call signature: принимает `(eval_thread)` из возврата

---

## 8. Зависимости

```toml
# pyproject.toml — добавить
sqlglot = ">=25.0"
```

---

## 9. Тесты

| Что тестировать | Файл |
|----------------|------|
| `_has_where_clause()` с подзапросами, CTE, двойными кавычками | tests/test_sql_security.py |
| `_call_llm_phase()` возвращает `tok_info` с ненулевыми значениями | tests/test_pipeline.py |
| `session_rules` не превышает 3 при 4+ learn-вызовах | tests/test_pipeline.py |
| `_run_learn(error_type="llm_fail")` не добавляет в session_rules | tests/test_pipeline.py |
| `_build_static_system()` возвращает `list` для Anthropic, `str` после `_system_as_str()` | tests/test_llm.py |
| Evaluator thread join срабатывает в `run_agent()` | tests/test_orchestrator.py |

---

## 10. Порядок реализации

1. Dead code removal (A1, A2, A11) — нет рисков регрессий
2. Token counting fix (A3) — изолированное изменение
3. `error_type` в LEARN (A7, A5, A10) — pipeline.py
4. Module-level cache (A8) + static system base (A4) — pipeline.py
5. Evaluator threading (A9) — pipeline.py + orchestrator.py
6. WHERE clause fix (A12) — sql_security.py + pyproject.toml
7. Prompt caching (A6) — llm.py + pipeline.py (наибольший риск, последним)
