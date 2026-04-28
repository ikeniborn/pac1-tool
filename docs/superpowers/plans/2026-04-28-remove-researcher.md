# Remove RESEARCHER Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Удалить весь RESEARCHER-режим из кодовой базы, оставив normal mode нетронутым.

**Architecture:** Удаление трёх слоёв — (1) файлы researcher.py/reflector.py и тесты к ним, (2) ветки `researcher_mode` в loop.py/_LoopState/run_loop(), (3) блоки `researcher_pending_*` в main.py и переменные из .env.example. После удаления loop.py упрощается: три conditional-ветки превращаются в прямой normal-mode код.

**Tech Stack:** Python 3.11+, uv, pytest

---

## File Map

| Действие | Файл |
|---|---|
| Удалить | `agent/researcher.py` |
| Удалить | `agent/reflector.py` |
| Удалить | `tests/test_researcher_retry.py` |
| Удалить | `tests/regression/test_researcher_first_answer_final.py` |
| Удалить | `tests/regression/test_reflector_no_merge_on_dispatch_error.py` |
| Удалить | `tests/regression/test_drift_hint_task_type.py` |
| Удалить | `tests/regression/test_outcome_loop_guard.py` |
| Удалить | `tests/regression/test_refusal_counter_robustness.py` |
| Изменить | `agent/__init__.py` |
| Изменить | `agent/loop.py` |
| Изменить | `main.py` |
| Изменить | `.env.example` |
| Очистить данные | `data/wiki/fragments/research/`, `data/wiki/archive/research_negatives/`, `logs/researcher/`, `data/wiki/graph.json` |

---

### Task 1: Удалить тест-файлы researcher

**Files:**
- Delete: `tests/test_researcher_retry.py`
- Delete: `tests/regression/test_researcher_first_answer_final.py`
- Delete: `tests/regression/test_reflector_no_merge_on_dispatch_error.py`
- Delete: `tests/regression/test_drift_hint_task_type.py`
- Delete: `tests/regression/test_outcome_loop_guard.py`
- Delete: `tests/regression/test_refusal_counter_robustness.py`

- [ ] **Step 1: Убедиться что тесты сейчас существуют**

```bash
ls tests/test_researcher_retry.py \
   tests/regression/test_researcher_first_answer_final.py \
   tests/regression/test_reflector_no_merge_on_dispatch_error.py \
   tests/regression/test_drift_hint_task_type.py \
   tests/regression/test_outcome_loop_guard.py \
   tests/regression/test_refusal_counter_robustness.py
```

Expected: все 6 файлов существуют.

- [ ] **Step 2: Удалить тест-файлы**

```bash
rm tests/test_researcher_retry.py \
   tests/regression/test_researcher_first_answer_final.py \
   tests/regression/test_reflector_no_merge_on_dispatch_error.py \
   tests/regression/test_drift_hint_task_type.py \
   tests/regression/test_outcome_loop_guard.py \
   tests/regression/test_refusal_counter_robustness.py
```

- [ ] **Step 3: Убедиться что остальные тесты импортируются**

```bash
uv run python -m pytest tests/ --collect-only -q 2>&1 | tail -5
```

Expected: коллекция проходит без `ImportError`. Количество тестов уменьшилось (~30+ меньше).

- [ ] **Step 4: Commit**

```bash
git add -u tests/
git commit -m "test: remove researcher-specific test files"
```

---

### Task 2: Удалить agent/researcher.py и agent/reflector.py

**Files:**
- Delete: `agent/researcher.py`
- Delete: `agent/reflector.py`

- [ ] **Step 1: Проверить что файлы существуют**

```bash
ls agent/researcher.py agent/reflector.py
```

- [ ] **Step 2: Удалить файлы**

```bash
rm agent/researcher.py agent/reflector.py
```

- [ ] **Step 3: Проверить что нет прямых импортов из удалённых файлов (кроме __init__.py — он будет исправлен в Task 3)**

```bash
grep -r "from .researcher\|from agent.researcher\|from .reflector\|from agent.reflector\|import researcher\|import reflector" agent/ tests/ --include="*.py" | grep -v "__init__.py"
```

Expected: пустой вывод.

- [ ] **Step 4: Commit**

```bash
git add -u agent/
git commit -m "feat: delete agent/researcher.py and agent/reflector.py"
```

---

### Task 3: Очистить agent/__init__.py

**Files:**
- Modify: `agent/__init__.py`

Удалить:
1. Строки 23–27 — комментарий FIX-362 и `_RESEARCHER_MODE = os.getenv("RESEARCHER_MODE", "0") == "1"`
2. Строки 95–114 — блок `if _RESEARCHER_MODE: ... return run_researcher(...)`

- [ ] **Step 1: Удалить переменную _RESEARCHER_MODE (строки 23–27)**

Найти и удалить этот блок в `agent/__init__.py`:

```python
# FIX-362: researcher mode master switch. When enabled, run_agent() bypasses
# the prompt_builder / evaluator / stall / timeout pipeline and delegates to
# agent.researcher.run_researcher, which drives a bounded outer cycle with
# reflection, wiki graph retrieval, and success-gated page promotion.
_RESEARCHER_MODE = os.getenv("RESEARCHER_MODE", "0") == "1"
```

Результат: эти 5 строк удалены.

- [ ] **Step 2: Удалить if _RESEARCHER_MODE блок (строки 95–114)**

Найти и удалить этот блок в `agent/__init__.py`:

```python
    # FIX-362: Researcher mode short-circuits the full pipeline. It classifies
    # via the fast regex path (no LLM voting), picks a single model, and runs
    # an outer cycle with reflection + graph retrieval. Evaluator/stall/timeout
    # all stay off. Normal mode is unaffected by this branch.
    if _RESEARCHER_MODE:
        from .researcher import run_researcher
        task_type = classify_task(task_text)
        # FIX-368: MODEL_RESEARCHER follows MODEL_* convention.
        researcher_model = os.getenv("MODEL_RESEARCHER") or router._select_model(task_type)
        researcher_cfg = router._adapt_config(
            router.configs.get(researcher_model, {}), task_type
        )
        return run_researcher(
            harness_url=harness_url,
            task_text=task_text,
            task_id=task_id or task_text[:20].replace(" ", "_"),
            task_type=task_type,
            model=researcher_model,
            cfg=researcher_cfg,
        )
```

Результат: эти 18 строк удалены, `run_agent()` начинается сразу с `vm = PcmRuntimeClientSync(harness_url)`.

- [ ] **Step 3: Проверить что модуль импортируется**

```bash
uv run python -c "from agent import run_agent; print('OK')"
```

Expected: `OK` без ошибок.

- [ ] **Step 4: Commit**

```bash
git add agent/__init__.py
git commit -m "feat: remove _RESEARCHER_MODE entry point from agent/__init__.py"
```

---

### Task 4: Очистить _LoopState в agent/loop.py

**Files:**
- Modify: `agent/loop.py`

Удалить из `_LoopState` dataclass поля, которые использовались только researcher-режимом.

- [ ] **Step 1: Удалить поле researcher_mode и его комментарий**

Найти и удалить в `agent/loop.py`:

```python
    # FIX-362: researcher mode — disables evaluator/stall/timeout inside the inner loop.
    # Set by run_loop() when called by agent.researcher; default False preserves normal behaviour.
    researcher_mode: bool = False
```

- [ ] **Step 2: Удалить поле last_report и его комментарий**

Найти и удалить в `agent/loop.py`:

```python
    # FIX-374: last ReportTaskCompletion — exposed to researcher outer-loop evaluator gate.
    last_report: "ReportTaskCompletion | None" = None
```

Внимание: `st.last_report` устанавливается в dispatch-коде и экспортируется как `"report"` в `_st_to_result()`. Проверить что `last_report` упоминается только в этих двух местах:

```bash
grep -n "last_report" agent/loop.py
```

Expected: декларация поля, `st.last_report = ...` (одна строка установки), и `"report": st.last_report` в `_st_to_result`. Если установка существует — оставить её, просто убрать комментарий и переписать комментарий в `_st_to_result` (убрать "FIX-374: researcher").

- [ ] **Step 3: Удалить поле midcycle_aborted и его комментарий**

Найти и удалить в `agent/loop.py`:

```python
    # FIX-376c: mid-cycle breakout flag — set when researcher_breakout_check
    # asks the inner loop to abort early. Surfaced to outer loop via _st_to_result.
    midcycle_aborted: bool = False
```

- [ ] **Step 4: Удалить поля report_completion_* и их комментарий**

Найти и удалить в `agent/loop.py`:

```python
    # FIX-377: structural detection of "answer already submitted" in researcher
    # mode. Cycle 1 succeeds; cycle ≥ 2 ReportTaskCompletion is rejected by
    # harness with INVALID_ARGUMENT. Outer researcher loop short-circuits on
    # this signal so reflector never sees a contaminated trajectory.
    report_completion_attempted: bool = False
    report_completion_dispatch_error_code: str | None = None
    report_completion_succeeded: bool = False
```

- [ ] **Step 5: Убрать экспорт удалённых полей из _st_to_result()**

Найти строки в `_st_to_result()` и удалить:

```python
        # FIX-376c: surface mid-cycle abort to outer researcher loop
        "midcycle_aborted": st.midcycle_aborted,
        # FIX-377: surface ReportTaskCompletion dispatch state so researcher
        # can detect "answer already submitted" via INVALID_ARGUMENT.
        "report_completion_attempted": st.report_completion_attempted,
        "report_completion_dispatch_error_code": st.report_completion_dispatch_error_code,
        "report_completion_succeeded": st.report_completion_succeeded,
```

Также убрать FIX-374 комментарий перед `"report": st.last_report`:

```python
        # FIX-374: last ReportTaskCompletion for researcher evaluator gate
        "report": st.last_report,
```

Заменить на:

```python
        "report": st.last_report,
```

- [ ] **Step 6: Убрать установки удалённых полей в теле loop.py**

Найти строки (около 2333–2334 и 2388–2389) и удалить:

```python
            st.report_completion_attempted = True
            st.report_completion_dispatch_error_code = exc.code.name
```

и отдельно:

```python
        st.report_completion_attempted = True  # FIX-377
        st.report_completion_succeeded = True  # FIX-377
```

Убедиться что поле `st.last_report` устанавливается там же и остаётся — оно нужно normal mode.

- [ ] **Step 7: Проверить что модуль импортируется**

```bash
uv run python -c "from agent.loop import run_loop; print('OK')"
```

Expected: `OK` без ошибок.

- [ ] **Step 8: Commit**

```bash
git add agent/loop.py
git commit -m "feat: remove researcher_mode and researcher-only fields from _LoopState"
```

---

### Task 5: Очистить run_loop() и _run_step() в agent/loop.py

**Files:**
- Modify: `agent/loop.py`

Удалить параметры и условные ветки из публичного API.

- [ ] **Step 1: Удалить researcher-параметры из сигнатуры run_loop()**

Найти сигнатуру:

```python
def run_loop(vm: PcmRuntimeClientSync, model: str, _task_text: str,
             pre: PrephaseResult, cfg: dict, task_type: str = "default",
             evaluator_model: str = "", evaluator_cfg: "dict | None" = None,
             researcher_mode: bool = False, max_steps: int | None = None,
             researcher_breakout_check=None,
             contract: "Any" = None) -> dict:
```

Заменить на:

```python
def run_loop(vm: PcmRuntimeClientSync, model: str, _task_text: str,
             pre: PrephaseResult, cfg: dict, task_type: str = "default",
             evaluator_model: str = "", evaluator_cfg: "dict | None" = None,
             max_steps: int | None = None,
             contract: "Any" = None) -> dict:
```

- [ ] **Step 2: Обновить docstring run_loop() — убрать FIX-362 абзац**

Найти и удалить из docstring:

```python
    FIX-362: researcher_mode=True disables evaluator, stall hints, and timeout —
    intended to be called by agent.researcher as an inner loop inside a bounded
    outer cycle. max_steps overrides the default 30-step cap; pass small values
    (e.g. 15) when the outer orchestrator will retry.
```

- [ ] **Step 3: Удалить строку st.researcher_mode = ... в теле run_loop()**

Найти и удалить:

```python
    st.researcher_mode = bool(researcher_mode)
```

- [ ] **Step 4: Убрать комментарий про researcher из строки с loop_cap**

Найти:

```python
    # Main loop — up to `loop_cap` steps (30 default; FIX-362 overrides for researcher)
```

Заменить на:

```python
    # Main loop — up to `loop_cap` steps (30 default; override via max_steps)
```

- [ ] **Step 5: Удалить breakout-check блок из тела цикла (строки 2468–2482)**

Найти и удалить весь блок:

```python
        # FIX-376c: mid-cycle breakout checkpoint — researcher-only opt-in.
        # The outer orchestrator can abort an obviously-stuck inner cycle to
        # free step budget for the next reflector cycle.
        if (
            researcher_breakout_check is not None
            and (i + 1) % max(1, int(os.environ.get("RESEARCHER_MIDCYCLE_CHECK_EVERY", "5"))) == 0
        ):
            try:
                _decision = researcher_breakout_check(st.step_facts)
            except Exception:
                _decision = "continue"
            if _decision in ("abort_cycle", "force_report"):
                st.midcycle_aborted = True
                print(f"{CLI_YELLOW}[midcycle-breakout] {_decision} at step {i + 1}{CLI_CLR}")
                break
```

- [ ] **Step 6: Развернуть timeout gate в _run_step()**

Найти (около строки 1981):

```python
    if not st.researcher_mode and elapsed_task > TASK_TIMEOUT_S:
        print(f"{CLI_RED}[TIMEOUT] Task exceeded {TASK_TIMEOUT_S}s ({elapsed_task:.0f}s elapsed), stopping{CLI_CLR}")
```

Заменить весь блок условия. Убрать условие `not st.researcher_mode and`, оставить только:

```python
    if elapsed_task > TASK_TIMEOUT_S:
        print(f"{CLI_RED}[TIMEOUT] Task exceeded {TASK_TIMEOUT_S}s ({elapsed_task:.0f}s elapsed), stopping{CLI_CLR}")
```

Также удалить комментарий над этим блоком:

```python
    # FIX-362: researcher mode has no wall-clock deadline — outer orchestrator
    # bounds work by RESEARCHER_MAX_CYCLES × RESEARCHER_STEPS_PER_CYCLE instead.
```

Заменить на:

```python
    # Task timeout check
```

- [ ] **Step 7: Развернуть stall gate и удалить soft-stall блок**

Найти блок (около строки 2055–2076):

```python
    # FIX-362: researcher mode — skip stall hints; repetitive probing is legitimate
    # exploration when the outer orchestrator drives the experiment.
    # FIX-376e: opt-in soft-stall — produce advisory hint as a step_fact so the
    # reflector sees the signal, but do NOT trigger an LLM retry. The outer
    # researcher loop decides whether to inject mid-cycle breakout / hint forcing.
    _si = _so = _se = _sev_c = _sev_ms = _scc = _scr = 0
    _stall_fired = False
    if not st.researcher_mode:
        job, st.stall_hint_active, _stall_fired, _si, _so, _se, _sev_c, _sev_ms, _scc, _scr = _handle_stall_retry(
            job, st.log, model, max_tokens, cfg,
            st.action_fingerprints, st.steps_since_write, st.error_counts, st.step_facts,
            st.stall_hint_active,
            contract_plan_steps=st.contract.plan_steps if st.contract else None,
        )
    elif os.environ.get("RESEARCHER_SOFT_STALL", "0") == "1":
        _soft_hint = _check_stall(
            st.action_fingerprints, st.steps_since_write, st.error_counts, st.step_facts,
        )
        if _soft_hint and not st.stall_hint_active:
            from .log_compaction import _StepFact as _SF
            st.step_facts.append(_SF(kind="stall_advisory", path="", summary=_soft_hint[:160]))
            st.stall_hint_active = True
```

Заменить на:

```python
    _si = _so = _se = _sev_c = _sev_ms = _scc = _scr = 0
    _stall_fired = False
    job, st.stall_hint_active, _stall_fired, _si, _so, _se, _sev_c, _sev_ms, _scc, _scr = _handle_stall_retry(
        job, st.log, model, max_tokens, cfg,
        st.action_fingerprints, st.steps_since_write, st.error_counts, st.step_facts,
        st.stall_hint_active,
        contract_plan_steps=st.contract.plan_steps if st.contract else None,
    )
```

- [ ] **Step 8: Удалить researcher_mode условие из evaluator gate**

Найти (около строки 2178–2179):

```python
    if (_EVALUATOR_ENABLED
            and not st.researcher_mode  # FIX-362: evaluator is a skeptic-gate; off in research
            and isinstance(job.function, ReportTaskCompletion)
```

Удалить строку `and not st.researcher_mode  # FIX-362: ...`:

```python
    if (_EVALUATOR_ENABLED
            and isinstance(job.function, ReportTaskCompletion)
```

- [ ] **Step 9: Финальная проверка — нет упоминаний researcher_mode в loop.py**

```bash
grep -n "researcher_mode\|researcher_breakout\|RESEARCHER_SOFT_STALL\|RESEARCHER_MIDCYCLE" agent/loop.py
```

Expected: пустой вывод.

- [ ] **Step 10: Import check**

```bash
uv run python -c "from agent.loop import run_loop; print('OK')"
```

Expected: `OK`.

- [ ] **Step 11: Commit**

```bash
git add agent/loop.py
git commit -m "feat: remove researcher_mode branches from run_loop() and _run_step()"
```

---

### Task 6: Очистить main.py

**Files:**
- Modify: `main.py`

Удалить два блока researcher-промоушена и упростить зависимые условия.

- [ ] **Step 1: Удалить блок researcher_pending_promotion (строки 344–363)**

Найти и удалить в `main.py`:

```python
            # FIX-363a: score-gated promotion for researcher mode.
            _pending = token_stats.get("researcher_pending_promotion")
            if _pending and _score_f >= 1.0:
                try:
                    from agent.wiki import promote_successful_pattern
                    from agent import wiki_graph as _wg
                    _pp = dict(_pending)
                    _touched = _pp.pop("touched_node_ids", [])
                    promote_successful_pattern(**_pp)
                    _g = _wg.load_graph()
                    _wg.add_pattern_node(
                        _g, _pp["task_type"], _pp["task_id"],
                        _pp["traj_hash"], _pp["trajectory"], _touched,
                    )
                    _wg.save_graph(_g)
                    print(f"[researcher] promoted {_pp['task_id']} (score=1.0)")
                except Exception as _pp_exc:
                    print(f"[researcher] deferred promotion failed: {_pp_exc}")
            elif _pending:
                print(f"[researcher] promotion skipped: score={_score_f} (<1.0)")
```

- [ ] **Step 2: Удалить блок researcher_pending_refusal (строки 364–376)**

Найти и удалить в `main.py`:

```python
            # FIX-366: score-gated refusal promotion — only correct refusals
            # (benchmark score=1) become wiki guidance.
            _pending_ref = token_stats.get("researcher_pending_refusal")
            if _pending_ref and _score_f >= 1.0:
                try:
                    from agent.wiki import promote_verified_refusal
                    promote_verified_refusal(**_pending_ref)
                    print(f"[researcher] promoted refusal {_pending_ref['task_id']} "
                          f"({_pending_ref['outcome']}, score=1.0)")
                except Exception as _pr_exc:
                    print(f"[researcher] refusal promotion failed: {_pr_exc}")
            elif _pending_ref:
                print(f"[researcher] refusal promotion skipped: score={_score_f} (<1.0)")
```

- [ ] **Step 3: Упростить _is_normal (строки 378–381)**

Найти:

```python
            # FIX-399: normal-mode pattern promotion — enabled for all modes.
            # Researcher sets researcher_pending_* in token_stats; normal mode does not,
            # so we build promotion data directly from token_stats fields available
            # after every run_loop() call.
            _is_normal = not _pending and not _pending_ref
```

Заменить на:

```python
            # FIX-399: normal-mode pattern promotion.
```

А строку `if _is_normal and _score_f >= 1.0 and _nm_traj:` (около строки 390) заменить на:

```python
            if _score_f >= 1.0 and _nm_traj:
```

- [ ] **Step 4: Упростить graph feedback gate (строка 433)**

Найти:

```python
            if _gf_enabled and _injected and not _pending and not _pending_ref:
```

Заменить на:

```python
            if _gf_enabled and _injected:
```

Также убрать комментарий перед этой строкой:

```python
            # FIX-389: normal-mode confidence feedback — reinforce on success,
            # degrade on failure, but only on the nodes that were actually
            # injected into this trial's prompt. Skip if researcher already
            # handled the trial (its own bookkeeping covers the same ids).
```

Заменить на:

```python
            # FIX-389: confidence feedback — reinforce injected nodes on success, degrade on failure.
```

- [ ] **Step 5: Убедиться что нет оставшихся researcher-ссылок в main.py**

```bash
grep -n "researcher\|_pending\|_is_normal" main.py
```

Expected: пустой вывод (кроме комментариев в CHANGELOG, если они есть в файле — там не должно быть).

- [ ] **Step 6: Проверить что main.py импортируется**

```bash
uv run python -c "import main; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat: remove researcher_pending_* promotion blocks from main.py"
```

---

### Task 7: Очистить .env.example

**Files:**
- Modify: `.env.example`

Удалить весь раздел RESEARCHER (строки 98–199).

- [ ] **Step 1: Удалить RESEARCHER-раздел из .env.example**

Найти и удалить весь блок от строки 98 до 199 включительно:

```
# ─── Researcher mode (FIX-362) ──────────────────────────────────────────────
# Внешний цикл поверх run_loop. Без evaluator/stall/timeout в inner-loop.
# ВАЖНО: PARALLEL_TASKS=1 — иначе параллельные задачи не видят паттернов друг друга.
# RESEARCHER_MODE=0
...
# RESEARCHER_DRIFT_LCS_MIN=0.4
```

Также удалить связанные упоминания в шапке файла (строки 13 и 24) если они ссылаются на RESEARCHER:

Строка 13: `PARALLEL_TASKS=2                     # RESEARCHER_MODE=1 требует 1 (см. ниже)`
→ заменить на: `PARALLEL_TASKS=2`

Строка 24: `#  MODEL_RESEARCHER пусто → ModelRouter по task_type).`
→ удалить эту строку (она часть комментария про MODEL_*).

Строка 40: `# MODEL_RESEARCHER=                  # researcher mode`
→ удалить эту строку.

Строка 67: `# В RESEARCHER_MODE=1 builder-примеры не собираются (addendum строит reflector).`
→ удалить эту строку.

Строка 68: `# Evaluator-примеры собираются по RESEARCHER_EVAL_GATED=1: последний gate-call`
→ удалить эту строку (и следующую, которая продолжает это предложение).

Строка 208: `# FIX-389 — write-side в normal mode (RESEARCHER_MODE=0):`
→ заменить на: `# FIX-389 — write-side (normal mode):`

- [ ] **Step 2: Проверить что не осталось RESEARCHER_ переменных**

```bash
grep -n "RESEARCHER" .env.example
```

Expected: пустой вывод.

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "feat: remove RESEARCHER_* variables from .env.example"
```

---

### Task 8: Полная проверка после удаления кода

- [ ] **Step 1: Import check**

```bash
uv run python -c "from agent import run_agent; print('OK')"
```

Expected: `OK`.

- [ ] **Step 2: Запустить полный тест-сьют**

```bash
uv run python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: все тесты проходят (`X passed`), нет `FAILED` или `ERROR`.

- [ ] **Step 3: Убедиться что нет оставшихся researcher-ссылок в agent/ и main.py**

```bash
grep -rn "RESEARCHER_MODE\|researcher_mode\|run_researcher\|from .researcher\|from agent.researcher\|from .reflector\|from agent.reflector\|agent\.reflector\|agent\.researcher" agent/ main.py --include="*.py"
```

Expected: пустой вывод.

- [ ] **Step 4: Commit если были мелкие правки**

```bash
git add -u
git status
# Если есть изменения:
git commit -m "fix: cleanup remaining researcher references"
```

---

### Task 9: Очистить данные

- [ ] **Step 1: Удалить researcher-артефакты**

```bash
rm -rf data/wiki/fragments/research/
rm -rf data/wiki/archive/research_negatives/
rm -rf logs/researcher/
```

- [ ] **Step 2: Сбросить graph.json**

```bash
# graph.json не имеет поля source на узлах, researcher-узлы нельзя отличить.
# Архивируем и сбрасываем — normal mode перестроит граф через WIKI_GRAPH_AUTOBUILD.
mv data/wiki/graph.json data/wiki/graph.json.bak 2>/dev/null || true
python -c "import json; open('data/wiki/graph.json','w').write(json.dumps({'nodes':{},'edges':[]},indent=2))"
```

- [ ] **Step 3: Проверить что data/wiki/pages/ не тронут**

```bash
ls data/wiki/pages/
```

Expected: файлы страниц на месте — они содержат score-gated паттерны, нужные normal mode.

- [ ] **Step 4: Проверить что data/dspy_examples.jsonl не тронут**

```bash
ls -la data/dspy_examples.jsonl 2>/dev/null && echo "exists" || echo "not found (ok)"
```

- [ ] **Step 5: Final verification**

```bash
uv run python -m pytest tests/ -q 2>&1 | tail -5
uv run python -c "from agent import run_agent; print('import OK')"
```

Expected: всё зелёное.

- [ ] **Step 6: Commit**

```bash
git add data/wiki/graph.json
git add -u data/wiki/fragments/ data/wiki/archive/ logs/ 2>/dev/null || true
git commit -m "chore: reset graph.json and remove researcher data artifacts"
```

---

## Итоговая верификация

После всех задач:

```bash
# Нет ссылок на удалённые модули
grep -rn "researcher\|reflector" agent/ main.py --include="*.py" | grep -v "# FIX-3[0-9][0-9]"

# Тесты проходят
uv run python -m pytest tests/ -q

# Модуль импортируется
uv run python -c "from agent import run_agent; print('OK')"
```
