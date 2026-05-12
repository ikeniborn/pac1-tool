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
| A3 | pipeline.py | `total_in_tok/total_out_tok` всегда 0 | `_call_llm_phase()` возвращает `tok_info`, caller суммирует; включает ANSWER-фазу |
| A4 | pipeline.py | `_build_system()` пересобирает статику каждый цикл | Три статические системы строятся один раз до цикла: `sql_plan`, `learn`, `answer` |
| A5 | pipeline.py | `_run_learn()` вызывается при LLM-fail SQL_PLAN | При `error_type="llm_fail"` LEARN не пишет в `session_rules` |
| A6 | llm.py | Нет Anthropic prompt caching | `system` как `list[block]` с `cache_control` на последнем статическом блоке; OpenRouter+Claude получает то же; остальные — `_system_as_str()` |
| A7 | pipeline.py | LEARN не различает типы ошибок | `error_type: str` тег: `syntax/semantic/security/empty/llm_fail`; пишется в sgr_trace |
| A8 | pipeline.py | `RulesLoader` + `load_security_gates()` — диск при каждом pipeline | Module-level lazy cache |
| A9 | pipeline.py | Evaluator in-band, блокирует возврат; запускается только при успехе | `threading.Thread(daemon=False)` запускается ВСЕГДА после финала; `join(timeout=30)` в `run_agent()` |
| A10 | pipeline.py | `session_rules` растёт неограниченно | Лимит 3, FIFO при переполнении |
| A11 | orchestrator.py | Мёртвые stats-поля: `builder_*`, `contract_*`, `eval_rejection_count` | Удалить |
| A12 | sql_security.py | `_has_where_clause()` не обрабатывает подзапросы и двойные кавычки | `sqlglot.parse_one()` + fallback к старому методу |

---

## 3. Архитектура

### 3.1 Граф вызовов после изменений

```
run_agent()                                          [orchestrator.py]
├── run_prephase() → PrephaseResult {agents_md_content, db_schema}
├── stats, eval_thread = run_pipeline(...)           ← сигнатура изменена
└── if eval_thread: eval_thread.join(timeout=30)

run_pipeline()                                       [pipeline.py]
├── _get_rules_loader()         [module-level lazy cache]
├── _get_security_gates()       [module-level lazy cache]
├── static_sql = _build_static_system("sql_plan", ...)   [1 раз]
├── static_learn = _build_static_system("learn", ...)    [1 раз]
├── static_answer = _build_static_system("answer", ...)  [1 раз]
│
└── for cycle in [0..MAX_CYCLES]:
    │   user_msg = _build_sql_user_msg(task_text, session_rules, last_error)
    ├── obj, sgr, tok = _call_llm_phase(static_sql, user_msg, SqlPlanOutput)
    │   total_in_tok  += tok.get("input", 0)
    │   total_out_tok += tok.get("output", 0)
    ├── check_sql_queries()
    ├── VALIDATE: for q in queries: vm.exec("EXPLAIN {q}")  [fail-fast]
    ├── EXECUTE:  for q in queries: vm.exec(q)
    └── [on fail] _run_learn(static_learn, error_type=...)
        ├── obj, sgr, _ = _call_llm_phase(static_learn, learn_user_msg, LearnOutput)
        │   [tok ignored — учёт через total_* только для основного цикла]
        └── if learn_out and error_type != "llm_fail":
                session_rules.append(learn_out.rule_content)
                session_rules = session_rules[-3:]   [FIFO лимит]

[ФИНАЛ — всегда, success ИЛИ fail после MAX_CYCLES]
├── if success:
│   answer_user = _build_answer_user_msg(task_text, sql_results)
│   obj, sgr, tok = _call_llm_phase(static_answer, answer_user, AnswerOutput)
│   total_in_tok  += tok.get("input", 0)
│   total_out_tok += tok.get("output", 0)
│   vm.answer(...)
├── else: vm.answer(OUTCOME_NONE_CLARIFICATION)
│
└── eval_thread = None
    if _EVAL_ENABLED and _MODEL_EVALUATOR:
        eval_thread = threading.Thread(
            target=_run_evaluator_safe,
            kwargs={"sgr_trace": sgr_trace, "cycles": cycles_used, ...},
            daemon=False,
        )
        eval_thread.start()
    return stats, eval_thread          ← tuple[dict, Thread | None]
```

### 3.2 Изменение сигнатуры `run_pipeline()`

```python
# Было:
def run_pipeline(...) -> dict:

# Стало:
def run_pipeline(...) -> tuple[dict, threading.Thread | None]:
```

Единственный caller — `run_agent()` в `orchestrator.py`. Harness видит только `run_agent() → dict` — сигнатура публичного API не меняется.

### 3.3 Новые/изменённые компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| `_build_static_system(phase, agents_md, db_schema, rules_loader, security_gates)` | pipeline.py | Заменяет `_build_system()`. Всегда возвращает `list[block]`. Фазо-зависимые блоки описаны в §4.1 |
| `_build_sql_user_msg(task, session_rules, last_error)` | pipeline.py | Динамический user_msg для SQL_PLAN: session_rules в начале, затем TASK + PREVIOUS ERROR |
| `_build_learn_user_msg(task, queries, error, error_type)` | pipeline.py | user_msg для LEARN: TASK + FAILED_QUERIES + ERROR + ERROR_TYPE |
| `_build_answer_user_msg(task, sql_results)` | pipeline.py | user_msg для ANSWER: TASK + SQL RESULTS |
| `_get_rules_loader()` | pipeline.py | Lazy init module-level `RulesLoader` |
| `_get_security_gates()` | pipeline.py | Lazy init module-level `list[dict]` |
| `_call_llm_phase(system, user_msg, output_cls, max_tokens)` | pipeline.py | Возвращает `(obj, sgr_entry, tok_info)` вместо `(obj, sgr_entry)` |
| `_run_learn(static_learn, pre, model, ..., error_type)` | pipeline.py | Принимает готовый `static_learn` вместо построения внутри; добавляет `error_type` в user_msg |
| `_system_as_str(system)` | llm.py | Flatten `list[block] → str` для OpenRouter (non-Claude) / Ollama |
| `_has_where_clause(sql)` | sql_security.py | sqlglot + regex fallback |

---

## 4. Prompt Caching

### 4.1 Структура блоков по фазам

`_build_static_system()` строит разные наборы блоков в зависимости от фазы:

```
sql_plan:
  [1] VAULT RULES (agents_md)          — если не пусто
  [2] PIPELINE RULES + SECURITY GATES  — rules_md + gates; если не пусты
  [3] DATABASE SCHEMA                  — db_schema; если не пусто
  [4] PROMPT GUIDE (load_prompt("sql_plan"))  ← cache_control: ephemeral

learn:
  [1] VAULT RULES (agents_md)          — если не пусто
  [2] PIPELINE RULES                   — rules_md только (НЕТ security_gates)
  [3] DATABASE SCHEMA                  — db_schema; если не пусто
  [4] PROMPT GUIDE (load_prompt("learn"))     ← cache_control: ephemeral

answer:
  [1] VAULT RULES (agents_md)          — если не пусто
  [2] DATABASE SCHEMA                  — db_schema; если не пусто
  [3] PROMPT GUIDE (load_prompt("answer"))    ← cache_control: ephemeral
```

`session_rules`, `last_error`, `queries` — НИКОГДА не в `system`. Всегда в `user_msg`. Это ключевое условие для стабильного кэш-префикса (Anthropic TTL 5 мин, Ollama KV-cache).

### 4.2 Python-структура блока с cache_control

```python
def _build_static_system(phase: str, agents_md: str, db_schema: str,
                          rules_loader: RulesLoader, security_gates: list[dict]) -> list[dict]:
    blocks: list[dict] = []

    if agents_md and phase in ("sql_plan", "learn", "answer"):
        blocks.append({"type": "text", "text": f"# VAULT RULES\n{agents_md}"})

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            text = f"# PIPELINE RULES\n{rules_md}"
            if phase == "sql_plan" and security_gates:
                text += f"\n\n# SECURITY GATES\n{_gates_summary(security_gates)}"
            blocks.append({"type": "text", "text": text})

    if db_schema:
        blocks.append({"type": "text", "text": f"# DATABASE SCHEMA\n{db_schema}"})

    guide = load_prompt(phase)
    blocks.append({
        "type": "text",
        "text": guide or f"# PHASE: {phase}",
        "cache_control": {"type": "ephemeral"},
    })
    return blocks
```

### 4.3 Поведение по тирам

| Тир | Передача `system` | Кэш |
|-----|-------------------|-----|
| Anthropic | `list[block]` напрямую в SDK | Explicit `cache_control`, TTL 5 мин |
| OpenRouter + Claude (is_claude_model=True) | `list[block]` — OpenRouter пробрасывает | Explicit через OpenRouter |
| OpenRouter + другие | `_system_as_str(list)` → `str` | Нет |
| Ollama | `_system_as_str(list)` → `str`; session_rules в user_msg | Implicit KV-cache на стабильном prefix |

### 4.4 Определение тира в `_call_raw_single_model()`

```python
provider = get_provider(model, cfg)
is_claude_via_or = (provider == "openrouter" and is_claude_model(model))

if provider in ("anthropic", "claude-code") or is_claude_via_or:
    _system = system          # list[block] or str — SDK и OpenRouter принимают оба
else:
    _system = _system_as_str(system)   # Ollama, non-Claude OpenRouter
```

`_call_raw_single_model()` сигнатура: `system: str | list[dict]` (расширяем тип).

---

## 5. Error Handling

### 5.1 LEARN error_type → sgr_trace

```
SQL_PLAN LLM fail   → error_type="llm_fail"   → session_rules НЕ пополняется
SECURITY blocked    → error_type="security"    → session_rules += rule
VALIDATE fail       → error_type="syntax"      → session_rules += rule
EXECUTE empty       → error_type="empty"       → session_rules += rule
EXECUTE exception   → error_type="semantic"    → session_rules += rule
```

`error_type` пишется в `sgr_trace` через LEARN-запись:

```python
# sgr_entry структура для LEARN фазы (расширение существующей)
sgr_entry = {
    "phase": "LearnOutput",
    "error_type": error_type,       # ← новое поле
    "guide_prompt": system[:300],
    "reasoning": learn_out.reasoning if learn_out else "",
    "output": parsed or raw or "",
}
```

Evaluator получает `error_type` из `sgr_trace` без изменений в `PipelineEvalOutput` или `EvalInput`.

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

`sqlglot` добавляется в `pyproject.toml`.

---

## 6. Evaluator Threading

```python
# pipeline.py — конец run_pipeline(), ВСЕГДА (success и fail)
eval_thread: threading.Thread | None = None
if _EVAL_ENABLED and _MODEL_EVALUATOR:
    eval_thread = threading.Thread(
        target=_run_evaluator_safe,
        kwargs={
            "task_text": task_text,
            "agents_md": pre.agents_md_content,
            "db_schema": pre.db_schema,
            "sgr_trace": sgr_trace,
            "cycles": cycles_used,
            "final_outcome": outcome,
            "model": _MODEL_EVALUATOR,
            "cfg": cfg,
        },
        daemon=False,
    )
    eval_thread.start()

return stats, eval_thread
```

```python
# orchestrator.py — run_agent()
stats, eval_thread = run_pipeline(vm, model, task_text, pre, cfg)
if eval_thread is not None:
    eval_thread.join(timeout=30)
    if eval_thread.is_alive():
        print("[orchestrator] evaluator timeout — log may be incomplete")
stats["model_used"] = model
# ... остальные поля
return stats   # dict, как прежде — публичный API не меняется
```

`daemon=False` — поток не убивается при завершении процесса. `join(timeout=30)` — hard cap.

---

## 7. Dead Code Removal

### prephase.py

- `PrephaseResult.log` → удалить поле
- `PrephaseResult.preserve_prefix` → удалить поле
- Тело `run_prephase()`: удалить строки с `log = [...]`, `log.append(...)`, `preserve_prefix = list(log)`
- `system_prompt_text` параметр `run_prephase()` → удалить (больше не нужен)

### orchestrator.py

- `from agent.prompt import build_system_prompt` → удалить импорт
- `system_prompt = build_system_prompt(task_type)` → удалить
- `pre = run_prephase(vm, task_text, system_prompt)` → `pre = run_prephase(vm, task_text)`
- `write_wiki_fragment()` функция → удалить
- Stats: удалить `builder_used`, `builder_in_tok`, `builder_out_tok`, `builder_addendum`, `contract_rounds_taken`, `contract_is_default`, `eval_rejection_count`

---

## 8. Зависимости

```toml
# pyproject.toml — добавить в [project.dependencies]
sqlglot = ">=25.0"
```

---

## 9. Тесты

| Что тестировать | Файл |
|----------------|------|
| `_has_where_clause()`: подзапросы, CTE, `WHERE` внутри строки | tests/test_sql_security.py |
| `_call_llm_phase()` возвращает 3-tuple `(obj, sgr, tok)` с ненулевым `tok` | tests/test_pipeline.py |
| `total_in_tok/total_out_tok` ненулевые после pipeline run (sql_plan + answer) | tests/test_pipeline.py |
| `session_rules` не превышает 3 при 4+ LEARN-вызовах | tests/test_pipeline.py |
| `_run_learn(error_type="llm_fail")` не добавляет в `session_rules` | tests/test_pipeline.py |
| `_build_static_system("learn")` НЕ содержит security_gates блок | tests/test_pipeline.py |
| `_build_static_system("sql_plan")` содержит security_gates блок | tests/test_pipeline.py |
| `_system_as_str(list[block])` возвращает корректный `str` | tests/test_llm.py |
| `sgr_trace` LEARN-записи содержат поле `error_type` | tests/test_pipeline.py |
| Evaluator thread запускается при fail-outcome (не только success) | tests/test_pipeline.py |
| `run_agent()` возвращает `dict` (публичный API не ломается) | tests/test_orchestrator.py |
| `PrephaseResult` не имеет полей `log` и `preserve_prefix` | tests/test_prephase.py |

---

## 10. Порядок реализации

1. **Dead code removal** (A1, A2, A11) — нет риска регрессий; `prephase.py` + `orchestrator.py`
2. **Token counting fix** (A3) — `_call_llm_phase()` → 3-tuple; суммирование в `run_pipeline()`
3. **error_type в LEARN** (A5, A7, A10) — `_run_learn()` + session_rules FIFO; `sgr_trace` расширение
4. **Module-level cache + static system** (A4, A8) — `_get_rules_loader()`, `_get_security_gates()`, три `_build_static_system()` до цикла; разделить `_build_user_msg` по фазам
5. **Evaluator threading** (A9) — `run_pipeline()` → tuple return; thread в финале; `join` в `run_agent()`
6. **WHERE clause fix** (A12) — `sql_security.py` + `pyproject.toml`
7. **Prompt caching** (A6) — `_call_raw_single_model()` принимает `str | list[dict]`; `_system_as_str()`; тир-логика (наибольший риск — последним)
