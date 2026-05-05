# Анализ деградации качества: 5-run v4 (2026-05-04)

**Дата:** 2026-05-05
**Источник:** `docs/run_analysis_2026-05-04_v4.md` + срез кода на коммите `7c008a7`
**Скоуп:** причины провала задач, эффективность графа/wiki, корректность оркестратора и контрактов, ранжированные fix-предложения.

---

## 1. Executive summary

В 5 последовательных прогонах ALL-tasks (43 задачи) показатель прошёл траекторию **49% → 60% → 53% → 51% → 51%** с пиком во 2-м прогоне и монотонной деградацией после. За те же 5 прогонов знания росли:

- граф: **311 → 1126** узлов (+262%), **469 → 2065** рёбер (+340%)
- wiki: **123 → 338** фрагментов (+175%)
- DSPy: **75 → 213** примеров (+184%)

**Знание накапливается, качество — нет.** Это сигнал, что рост корпуса сам по себе не транслируется в улучшение поведения, а в нескольких местах транслируется в его ухудшение. Ниже — четыре корневые причины, ранжированные по влиянию на score.

| # | Корневая причина | Категория | Вес | P |
|---|---|---|---|---|
| 1 | **Wiki-poisoning в `lookup.md`**: успешными паттернами зафиксированы трajeкторы вида «`captured N days ago` → `OUTCOME_NONE_CLARIFICATION`». t42 стабильно 0/5. | knowledge | High | P0 |
| 2 | **Контекстное распухание prefill** (граф+wiki+errors). `errors/default.md`=985 строк, `errors/lookup.md`=446. «no answer provided» как доминирующий failure-mode в run 4–5. | context | High | P0 |
| 3 | **Confidence-feedback слишком мягкий** (ε=0.05, MIN=0.2). Ложные узлы переживают негативные трials, продолжают подниматься в retrieval. | knowledge | Med | P0 |
| 4 | **FIX-437 effectively dead-code**: `evaluator_only=True` нигде не присваивается → consecutive_contract_blocks никогда не инкрементируется → форс OUTCOME_NONE_CLARIFICATION никогда не срабатывает. Заявленная защита отсутствует. | contract | Med | P1 |

Дополнительные структурные проблемы (оркестратор, контракт на CC tier, error-ingest) описаны в §6–§7. Полный план fix'ов — в §9.

---

## 2. Метрики и динамика

### 2.1 Score по прогонам v4

| Прогон | Score | Тяжёлый failure-mode |
|---|---|---|
| 1 | 21/43 = 49% | mix |
| 2 | **26/43 = 60%** ← пик | mix |
| 3 | 23/43 = 53% | "no answer" растёт |
| 4 | 22/43 = 51% | "no answer" доминирует (~13 задач) |
| 5 | 22/43 = 51% | "no answer" + outcome flips |

### 2.2 Распределение «no answer provided»

| Прогон | Задач с «no answer provided» | Из 43 |
|---|---|---|
| 1 | 9 | 21% |
| 2 | 7 | 16% |
| 3 | 8 | 19% |
| 4 | **13** | **30%** |
| 5 | **14** | **33%** |

Доля «агент не успел/не сумел сформировать ответ» выросла в 1.5×+ к 5-му прогону. Это не «модель тупит» — это симптом stall'а внутри 30-step-budget на фоне раздувшегося prefill (см. §3.1).

### 2.3 Стабильно проваленные задачи (0/5 за все 5 прогонов)

| Task | Failure pattern |
|---|---|
| t03 | no answer provided |
| t04 | no answer provided |
| t13 | JSON mismatch `next_follow_up_on` (CRM-формула) |
| t14 | JSON mismatch `to:` в outbox + no answer |
| t37 | no answer / NONE_CLARIFICATION ↔ OK |
| t41 | wrong date / no answer (temporal arithmetic) |
| t42 | OK ожидался, агент даёт NONE_CLARIFICATION |

### 2.4 Регрессировавшие (1.0 в run 1 → 0.0 позже)

t11, t17, t18, t19, t30, t38 — все имели как минимум один успех на ранних прогонах, к run 5 проваливаются. Корреляция с ростом graph_section в prompt'е и накопленными wiki-фрагментами.

---

## 3. Failure-mode analysis

### 3.1 «No answer provided» — доминирующий failure-mode

**Симптом:** в outcome — что-то отличное от `OUTCOME_OK`/`OUTCOME_NONE_*`, и в `report_completion.message` пусто или нет вызова `report_completion` вообще.

**Гипотеза 1 — исчерпание step-budget.** `loop.py` имеет жёсткий лимит шагов; agent сначала идёт в discovery (tree/find/list/read), затем в reasoning, и только потом — в `report_completion`. Когда:
- prefill раздут wiki/graph (см. §4–§5),
- planner+contract negotiation не может уместиться (max_rounds=3 × 2 LLM calls + planner round 0 — `contract_phase.py:198–217`),
- evaluator отбрасывает 1–3 раза,

агент тратит шаги на discovery и не доходит до submission. Run 4–5 имеет средний таск-time **>500с** против ~400с в run 1–2 — не от роста сложности задач, а от ветвлений.

**Гипотеза 2 — стол отказа после VerifierAgent rejection'ов.** При повторных reject модель дрейфует в формулировке ответа, накапливая токены, и не возвращается к `report_completion` вовремя.

**Доказательства:**
- t30 в run 4 = 1247.8с (рекордно длинная попытка) → 0.0
- t12 в run 1 = 1113.5с → 1.0; в run 4 = 675.7с → 0.0 (no answer): время ниже, но завершения нет — выход по step-limit, не по timeout
- Доля «no answer» растёт от 21% к 33% к run 5 (см. §2.2)

**Что почти наверняка не виновато:** модель — она та же (`minimax-m2.7-cloud`); harness — стабилен (exit 0).

---

### 3.2 OUTCOME_NONE_CLARIFICATION при ожидании OK (t42 = 0/5)

**Симптом v3 уже описывал это:** «t42: 5 узлов rule/insight о поиске в `01_capture/influential/` накоплены, но агент даёт CLARIFICATION». В v4 — тот же паттерн, доказательства теперь видны прямо в wiki:

`data/wiki/pages/lookup.md:18` (block "If no matching article found for specified timeframe"):

```
3. If no matching article found for specified timeframe:
   - Return `OUTCOME_NONE_CLARIFICATION`
   - Await user clarification specifying article title, keyword, or exact date range
```

И ниже — конкретные примеры (`lookup.md:29–82`):

```
- Input: 'need the article i captured 23 days ago'
- Outcome: OUTCOME_NONE_CLARIFICATION — no items found...
- Input: 'I captured an article 48 days ago. Which one was it?'
- Outcome: OUTCOME_NONE_CLARIFICATION — temporal resolution failed...
- Input: 'can you tell me which article i captured 27 days ago'
- Outcome: OUTCOME_NONE_CLARIFICATION
- Input: 'Find the article I captured 19 days ago.'
- Outcome: OUTCOME_NONE_CLARIFICATION
```

Всё это инжектится в system prompt через `WikiGraphAgent.read()` → `WikiContext.patterns_text` → `orchestrator.py:89–93`. То есть агент **активно учится**, что на «N days ago» нужно отвечать CLARIFICATION. Это и есть отравление: реальный бенчмарк требует резолва даты от VAULT_DATE и поиска.

**Почему такие фрагменты попали в wiki как «successful»:** wiki-lint синтезирует страницу из накопленных фрагментов. Если в прошлом запуске на каком-то vault-варианте действительно не было статьи на нужную дату, OUTCOME_NONE_CLARIFICATION засчитывалось как корректный ответ (score=1.0). Ингест-фильтр **не различает** «верно для всех вариантов» от «верно только для одного варианта». LLM-synthesizer обобщает частное в общее.

---

### 3.3 JSON mismatch / wrong dates (t13, t41, t14)

- **t13 (CRM, `next_follow_up_on`):** 5/5 fail. Wiki/graph содержат правило «add 90 days to last_contact», но фактическая ошибка — off-by-N: prompt не доносит до модели формулу с привязкой к `VAULT_DATE`. FIX-425 (`_format_crm_gate_block`, `loop.py:110–115`) добавил CRM-gate prompt при детекте, но он реактивный — после неверной попытки.
- **t41 (temporal):** 5/5 fail. Каждый прогон ожидаемая дата разная (split на варианты vault). Граф для этого типа содержит ~10 antipatterns после ингеста ошибок, но они не превращаются в исправление формулы.
- **t14 (outbox `to:`):** провал из-за wrong recipient — это контаминация по похожим контактам в vault.

**Общий вывод:** граф/wiki накапливают наблюдения, но не модель. Без переноса этих правил в **prompt builder addendum** (DSPy-optimized) или в **system prompt темплейт** для соответствующего task_type — модель будет повторять ошибку.

---

### 3.4 Outcome flips OK ↔ DENIED_SECURITY (t29, t33, t9)

| Task | Прогон | Ожидалось | Получено |
|---|---|---|---|
| t29 | 1 | OK | DENIED_SECURITY |
| t29 | 2 | DENIED_SECURITY | NONE_CLARIFICATION |
| t33 | 1 | DENIED_SECURITY | OK |
| t9  | 1 | (no changes) | got 1 change |
| t9  | 4 | DENIED_SECURITY | NONE_UNSUPPORTED |

Это указывает на нестабильность security-gates. `security.py` с FIX-208 (write-scope) и FIX-276 (cross-account inbox-email) — детерминированные. Но boundary-cases (`outbox` с похожим домейном; admin elevation через OTP) могут срабатывать или не срабатывать в зависимости от того, какая ветка пути дошла до проверки. Нестабильность в одних и тех же задачах разных прогонов означает: gate триггерится на основании промежуточных решений модели, а не одних только tool args.

---

### 3.5 «Expected no changes, but got 1» (t8, t9)

t8 в run 3 = 0.0 (got 4 changes), t9 в run 1 = 0.0 (got 1 change). Эти задачи ожидают **отсутствие мутаций**, а агент пишет. У lookup тип уже жёстко режется в `loop.py:1936–1938`:

```python
if task_type == TASK_LOOKUP and isinstance(job.function, (Req_Write, ...)):
    return "[lookup] Lookup tasks are read-only..."
```

Но если classifier ошибся в типе (отнёс задачу не к lookup), guard не срабатывает. Это **класс-leak проблема**: ошибка классификатора → потеря no-mutation-инварианта.

Альтернативная гипотеза для t9: outcome flip OK→DENIED_SECURITY/UNSUPPORTED + всё-таки попытка записи — указывает скорее на нестабильность security-gate'а (см. §3.4), а не на classifier. Точное разделение этих гипотез требует чтения trace-логов соответствующих прогонов.

---

## 4. Эффективность графа знаний

### 4.1 Что работает

- **Hard cross-type filter (FIX-433, `wiki_graph.py:375`)** — узлы из чужого task_type теперь не попадают в retrieval. Подтверждено в коде.
- **Confidence feedback по injected_node_ids (`agents/wiki_graph_agent.py:50–67`)** — bump_uses при score≥1, degrade_confidence при ниже. Цикл замкнут.
- **Near-duplicate dedup (FIX-421, `wiki_graph.py:73–80`)** — Jaccard ≥ 0.7 предотвращает буквальные дубли при merge_updates.

### 4.2 Что не работает

#### 4.2.1 Confidence decay слишком мягкий

`WIKI_GRAPH_CONFIDENCE_EPSILON=0.05` (CLAUDE.md), `MIN_CONFIDENCE=0.2`. С учётом `_DEFAULT_CONFIDENCE=0.6`, узел переживает **8 негативных трials подряд** прежде чем уйти в архив. На 5 прогонах × 43 задачи отравленный узел типа «N days ago → CLARIFICATION» едва ли наберёт столько негативов даже теоретически — он попадает в retrieval только когда задача-кандидат подходит, и часть таких трialов пройдёт со score=1.0 (если в этом vault'е действительно статьи нет).

#### 4.2.2 Pattern-extractor бьёт по любому score=1.0

`main.py` ингестит `step_facts` в `add_pattern_node` для всех успешных трialов (CLAUDE.md: «score=1.0 → bump_uses на узлы из prompt'а + add_pattern_node от step_facts»). Это включает успехи, где «успех» = «правильно отказался» (NONE_CLARIFICATION при пустом vault'е). Pattern из такой трajectoрии заходит в граф как успешный паттерн **поиска**, но он по сути паттерн **отказа**.

**Нужен фильтр**: создавать `pattern` только если `outcome=OUTCOME_OK` (а не любой score≥1).

#### 4.2.3 Инфляция узлов без качественного отбора

| После прогона | Узлы | Прирост |
|---|---|---|
| 0 | 311 | — |
| 1 | 489 | +178 |
| 2 | 657 | +168 |
| 3 | 827 | +170 |
| 4 | 983 | +156 |
| 5 | 1126 | +143 |

Прирост стабильно ~150–180 узлов на прогон. Нет ассимптоты. При том, что задач 43, и одни и те же ошибки повторяются — узлы должны были бы консолидироваться. Они не консолидируются достаточно быстро: пороговый dedup 0.7 пропускает близкие, но иначе сформулированные insight'ы. Ингест с LLM-extractor выдаёт по 30–46 deltas за прогон (`v4.md:29, 123, 220, 317, 414`), и они просто складываются.

#### 4.2.4 retrieve_relevant scoring

`_score_candidates` (CLAUDE.md): `tag_overlap + text-token overlap + confidence × log(uses)`. Узел с высоким `uses` (=>часто инжектируется) увеличивает свой score на следующих ретривалах сильнее, чем редкий, даже более релевантный новый узел. **Закон богатые становятся богаче** — отравленные раз попавшие узлы консолидируют доминирование.

#### 4.2.5 Edges создаются, но не используются

«+1596 рёбер за 5 прогонов» (v4.md:505). Граф читается как top-K nodes по scoring; ребра-связи (`requires`, `precedes`) при ретривале не используются. Граф работает как **взвешенный лексический индекс**, а не как граф. Затраты на edge-extraction окупаются только на инспекции (`scripts/print_graph.py`).

---

## 5. Эффективность wiki-lint

### 5.1 Что работает

- Все 7 категорий стабильно достигают `quality=mature` к run 4–5 (`v4.md:307–316`).
- Per-task fragments живут в `data/wiki/fragments/<category>/`, синтез один раз за прогон.

### 5.2 Что не работает

#### 5.2.1 Wiki-poisoning

См. §3.2. Корень — в самом ингест-критерии: `score=1.0` → ингест в successful_patterns. Между «правильно ответил OK» и «правильно отказался NONE_CLARIFICATION» нет различия по score, поэтому оба попадают в один и тот же блок «Successful patterns». LLM-synthesizer затем выдаёт обобщения, повторяющие паттерн отказа.

#### 5.2.2 Отсутствие лимитов на размер страницы

```
errors/default.md  985 строк
errors/lookup.md   446 строк
lookup.md          383 строк
queue.md           349 строк
```

Никакого `WIKI_PAGE_MAX_LINES`/`MAX_FRAGMENTS` нет (`grep` по `wiki.py`/`postrun.py` не находит ограничений). При оценочном ~30 токенов/строка, errors/default.md — это **30k токенов** только своей одной страницы. В prefill по `WIKI_GRAPH_TOP_K=5` мы инжектим только top-K узлов из графа, но `patterns_text` (вся wiki-страница task_type) идёт сырьём. Для типов с большой страницей (`lookup`, `queue`) prefill раздувается на >10k токенов.

#### 5.2.3 Error-ingest повторяет одно и то же

```
[wiki-graph] error-ingest 'crm':     10 antipattern nodes (run 1, 2, 3, 4, 5 — все по 10)
[wiki-graph] error-ingest 'temporal': 10 (тоже стабильно по 10)
[wiki-graph] error-ingest 'default':  10
[wiki-graph] error-ingest 'lookup':   10
```

Это значит ingestion **ингестит топ-10 ошибок каждый прогон** независимо от того, новые они или нет. Dedup при merge схватывает буквальные совпадения, но если LLM-extractor по-разному формулирует — каждый прогон добавляет 5–10 «новых» antipattern'ов. Отсюда — рост `antipattern` с 90 до 326 за 5 прогонов.

#### 5.2.4 LLM-synthesizer обобщает частное в общее

Это структурная проблема: нет промпта/гарда, который бы говорил «если паттерн viewed только в одном vault-варианте — пометить как `variant-specific`». В результате wiki выглядит как universal guidance, а по факту это обобщение частных vault-runs.

---

## 6. Корректность оркестратора и сабагентов

### 6.1 Архитектура

Hub-and-Spoke (`orchestrator.py`) с 9 сабагентами и единой точкой контрактов (`agent.contracts/__init__.py`). Pydantic-typed везде, lazy imports внутри методов, чёткие границы.

**+** Изоляция: каждый агент знает только `agent.contracts`. Обмен сообщениями типизирован.
**+** PrejectAgent имеет короткий путь без planner/wiki (`orchestrator.py:41–84`).
**+** ExecutorAgent — тонкая обёртка над `run_loop`, DI через инжектируемые агенты.

### 6.2 Проблемы

#### 6.2.1 Множество LLM-вызовов до execution

Стандартный путь до 1-го `run_step()`:

1. **ClassifierAgent** — 1 LLM call (DSPy classifier).
2. **WikiGraphAgent.read** — 0 LLM calls (только I/O).
3. **PlannerAgent** — 1 builder LLM call + (опционально) **до 7 LLM calls в contract negotiation**:
   - planner round 0 (1 call)
   - executor + evaluator × 3 rounds (6 calls), плюс `_PARSE_RETRIES=3` на каждый.

Итого до 9 LLM calls до того, как агент сделает первый `tree`. Это:
- стоимость токенов,
- латентность,
- ужатие шагового бюджета (если step-budget вычисляется по «llm-calls» или по time).

#### 6.2.2 Step-budget не разделён по фазам

В `_LoopState.step_count` нет разделения на discovery/execution/verify. Если evaluator отвергает submission 3 раза подряд (`eval_rejections`, `evaluator_rejections`), агент использует ~3 шага только на retries без полезной работы. Жёсткий лимит шагов 30 (см. CLAUDE.md, «main agent loop ≤30 steps») при 3 verify-retry'ях оставляет 27 шагов на работу.

#### 6.2.3 WikiGraphAgent.write_feedback бьёт по всем injected_node_ids одинаково

`agents/wiki_graph_agent.py:50–67` декрементирует **все** инжектированные узлы при провале. Но какие из них реально повлияли на решение модели — неизвестно. Узел, добавленный из-за tag-overlap случайно, понижается так же, как ключевой. Это даёт аддитивный шум в confidence.

**Альтернатива**: отслеживать какие узлы цитируются в `step_facts`/answer (например, через grounding_refs) и понижать только их.

#### 6.2.4 PrejectAgent короткий путь не пишет wiki

В preject-ветке `orchestrator.py:71–83` нет `write_feedback`/`write_wiki_fragment`. Это намеренно (preject — спецтип «обращение пользователя без задачи»), но стоит зафиксировать в инвариантах: «preject не учится».

---

## 7. Корректность контрактов

### 7.1 Что инжектится в LLM

**Подтверждено** (`loop.py:118–131, 2680–2683`): после согласования контракт форматируется в блок `## AGREED CONTRACT` с `Plan steps`/`Success criteria`/`Required evidence in grounding_refs` и **дописывается в system prompt** агента. То есть контракт **видим** для исполнителя.

**Что не видит модель**: `failure_conditions`, `mutation_scope`, `forbidden_mutations`, `evidence_standard`, `planner_strategy`. Эти поля используются guard'ами (StepGuard, contract_monitor, evaluator), но в prompt не выводятся. Соответственно, модель не знает, что именно её остановит — реагирует на guard-сообщения постфактум.

### 7.2 Default contract на CC tier

`contract_phase.py:146–149`:

```python
if model.startswith("claude-code/"):
    if _LOG_LEVEL == "DEBUG":
        print("[contract] CC tier — skipping negotiation, using default contract")
    return _load_default_contract(task_type), 0, 0, []
```

Содержимое `data/default_contracts/default.json`:

```json
"plan_steps": ["list or tree the vault to discover structure", "identify the target folder ...",
              "execute the task using appropriate tools", "report completion ..."],
"success_criteria": ["task completed as described", "correct vault path used", "no unintended files modified"]
```

Это **универсально-нерелевантная** инструкция — никаких task-type-specifics. На CC tier контракт фактически отсутствует как механизм. Per-type default contracts в `data/default_contracts/<type>.json` существуют, но это всё равно captured-в-файле статика, не negotiate.

### 7.3 FIX-435 + FIX-437: дезактивирующая комбинация

Отдельная находка, важная для §1.

`contract_models.py:33`:
```python
evaluator_only: bool = False  # FIX-415: True when evaluator-only consensus
```

`contract_phase.py`: единственные присвоения — оба `evaluator_only=False`:
- линия 353 (full_consensus путь, FIX-435 «full consensus only»),
- линия 380 (max_rounds exceeded fallback).

Default-контракты в JSON не имеют этого поля → Pydantic берёт default `False`.

`grep -rn "evaluator_only" agent/ data/` показывает **0 мест**, где `evaluator_only=True` устанавливается.

`loop.py:1914–1933`: гейт срабатывает только при `st.contract.evaluator_only=True` (`if (st.contract is not None and st.contract.evaluator_only and isinstance(...))`). Поскольку условие никогда не выполняется, `st.consecutive_contract_blocks` никогда не инкрементируется.

`loop.py:2302–2313`: FIX-437 force-OUTCOME_NONE_CLARIFICATION срабатывает на `if st.consecutive_contract_blocks >= 2`. **Эта ветка недостижима в рантайме.**

**Последствия:**
1. FIX-437 как механизм защиты не работает. Заявление в CHANGELOG не соответствует поведению.
2. Если в будущем кто-то поправит FIX-435 и `evaluator_only=True` снова появится — FIX-437 неожиданно активируется и начнёт сюрприз-форсить CLARIFICATION.
3. Само существование mutation_scope checks в loop.py становится мёртвой защитой: forbidden_mutations/mutation_scope наполняются (`contract_phase.py:343–352`), но проверяются только под `evaluator_only=True`. То есть **mutation_scope-валидация по факту не работает**.

### 7.4 Default contract как кросс-task'ный

Все default-контракты содержат `is_default=True`. `evaluator.py:416` пропускает контрактную проверку при `contract.is_default`:

```python
if contract is None or contract.is_default or not contract.required_evidence:
    return  # skip evidence check
```

То есть **на CC tier и на любых fallback-путях** эвалуатор не делает grounding-check. Это делает FIX-436 evidence_standard полезным только для негоцированных контрактов вне CC.

---

## 8. Ранжированный список корневых причин

| Ранг | Причина | Влияние | Тип fix |
|---|---|---|---|
| **1** | Wiki poisoning lookup.md (NONE_CLARIFICATION как успех) | High (–t42 = –1 балл стабильно; –регресс на похожих темпорал-задачах) | knowledge ingest filter |
| **2** | Контекстное распухание (errors/*.md, инфляция графа) | High (рост «no answer» с 21% до 33%) | size-limit + dedup ingest |
| **3** | Confidence decay слишком мягкий | Med (отравленные узлы переживают трialы) | env-tune + algorithm |
| **4** | FIX-437 dead-code, mutation_scope не валидируется | Med (заявленная защита отсутствует) | code fix |
| **5** | Default contract на CC tier (no negotiate) | Med (CC-задачи лишены guidance) | configuration / fallback model |
| **6** | Pattern-extractor бьёт на любой score=1.0 | Med (паттерны отказа промотируются как успех) | filter on outcome |
| **7** | Step-budget не разделён по фазам | Low–Med (verify-rejections съедают шаги) | budget-split |
| **8** | Edges в графе создаются, но не используются | Low (cost waste, не качество) | optimization |
| **9** | classifier mis-route → потеря read-only инварианта | Low (t8/t9 редкие, но стабильно дорогие) | guard hardening |

---

## 9. Fix-предложения

### P0 (критично, делать в первую очередь)

#### Fix A — Anti-poisoning ingest filter

В точке записи в wiki successful patterns и в `add_pattern_node`:

```python
# было: ингест на score >= 1.0
# стало: ингест только на (score >= 1.0) AND (outcome == "OUTCOME_OK")
```

Места для правки:
- `agent/postrun.py` (фрагменты wiki-lint),
- `main.py` после `end_trial()` — pattern-extractor.

NONE_CLARIFICATION-трajectoрии складировать в отдельный поток `data/wiki/pages/<type>/clarification_cases.md` для диагностики, **не** инжектить в prefill.

#### Fix B — Очистка отравленной wiki

Однократная санация:
- удалить из `data/wiki/pages/lookup.md` все блоки, где outcome=NONE_CLARIFICATION зафиксирован как образец для «N days ago» / temporal-anchor запросов;
- провести `archive_low_confidence_nodes` (`scripts/print_graph.py` или новый script) с порогом 0.4;
- регенерить wiki из `fragments/` с включённым фильтром (Fix A).

#### Fix C — Лимит размера wiki-страниц

Env: `WIKI_PAGE_MAX_LINES=200` (или _MAX_TOKENS=5000). В `agent/wiki.py` после синтеза:

```python
if len(page_text.splitlines()) > _MAX_LINES:
    # truncate by aspect priority: workflow_steps > pitfalls > shortcuts > examples
```

errors/default.md = 985 строк — это самая жирная страница, с неё и начать.

#### Fix D — Усилить confidence decay

```bash
WIKI_GRAPH_CONFIDENCE_EPSILON=0.15   # было 0.05
WIKI_GRAPH_MIN_CONFIDENCE=0.4        # было 0.2
```

Это сократит lifecycle ложных узлов с ~8 негативных трialов до ~3.

### P1 (важно, делать вторым шагом)

#### Fix E — Реанимировать mutation_scope-гейт (или удалить)

Два варианта, оба валидны, нужно выбрать один:

**Вариант 1 — переключить guard на `not contract.is_default`** (вместо `contract.evaluator_only`):

```python
# loop.py:1914 was: if st.contract is not None and st.contract.evaluator_only ...
# stale: if st.contract is not None and not st.contract.is_default and st.contract.mutation_scope ...
```

Тогда mutation_scope/forbidden_mutations начинают работать на всех негоцированных контрактах. FIX-437 force CLARIFICATION тоже оживает.

**Вариант 2 — удалить мёртвый код:**
- удалить блок `loop.py:1912–1933`,
- удалить `consecutive_contract_blocks` и FIX-437 ветку `2302–2313`,
- удалить поле `evaluator_only` из Contract.

Рекомендация: Вариант 1, если планируется доверять negotiate. Вариант 2, если отказываемся от mutation-scope-защиты.

#### Fix F — Negotiate contract на CC tier

Прокинуть отдельную модель для negotiate, не зависящую от CC:

```bash
MODEL_CONTRACT=anthropic/claude-3-5-sonnet  # или openrouter/...
```

`_effective_model` в `contract_phase.py:34–36` уже это поддерживает; нужно убрать ранний выход `if model.startswith("claude-code/")` (`contract_phase.py:146`) и пустить обычный path под `_effective_model`.

#### Fix G — Global dedup в error-ingest

Сейчас error-ingest каждый прогон добавляет ~5–10 antipatterns. Перед merge — глобальный dedup (по text-hash или ≥0.5 token-overlap по всем существующим antipattern'ам, не только same-task). Снизит инфляцию узлов и шум в retrieval.

### P2 (полезно, делать последним)

#### Fix H — Step-budget split

Разделить 30 шагов на:
- discovery_max=10
- execution_max=15
- verify_max=5

Если verify_max исчерпан — auto-approve последний report, не давать модели накапливать reject-rounds бесконечно.

#### Fix I — Tracking-based confidence feedback

Вместо «понижать все injected_node_ids» — понижать только те, чьи tags перекрываются с reasoning-trace ответа модели. Требует доработки `step_facts` для записи использованных рекомендаций.

#### Fix J — Show success_criteria more visibly

Сейчас `## AGREED CONTRACT` блок добавляется в **самый конец** system prompt. Длинный prefill отодвигает его от внимания модели. Поднять `## AGREED CONTRACT` ближе к началу (после `## TASK` блока), либо дублировать `success_criteria` в финальный turn перед `report_completion`.

---

## 10. Метрики мониторинга для следующих прогонов

Добавить в `docs/run_analysis_*.md` секцию «Health metrics»:

| Метрика | Источник | Target |
|---|---|---|
| % failures = «no answer provided» | run_analysis.md | ≤ 15% (сейчас 33%) |
| % outcome=NONE_CLARIFICATION при expected≠CLARIFICATION | task_outcome ↔ expected | ≤ 5% |
| Avg prefill tokens per task | dispatch logs / total_in_tok / step_count | ≤ 8000 |
| Max graph nodes injected per task | `stats["graph_injected_node_ids"]` | ≤ 5 |
| Avg evaluator rejections per task | `stats["eval_rejection_count"]` | ≤ 1 |
| Wiki page lines per category | filesystem | ≤ 200 |
| Graph node growth per run | (after - before) | ≤ 80 (сейчас ~150–180) |
| Antipattern dup rate | hash collisions in error-ingest | ≥ 50% |

После применения P0-fix'ов — повторить 5-run и сравнить метрики **здесь** к v4-baseline.

---

## 11. Что НЕ виновато (negative findings)

Чтобы не охотиться на призраков на следующей итерации:

- **Модель** — `minimax-m2.7-cloud` стабилен; нет смысла менять модель пока не закрыты P0 knowledge-fixes.
- **Harness/PCM** — exit 0 на всех 5 прогонах; проблем с RPC нет.
- **DSPy infrastructure** — `prompt_builder_program.json` грузится; хотя `evaluator_program.json` отсутствует в стартовом состоянии (`v4.md:5`: «программы: ['prompt_builder_program.json']»). Это известное состояние, фикс через `optimize_prompts.py --target evaluator`.
- **Cross-type retrieval** — FIX-433 закрыл это. Граф больше не leaks между типами.
- **Tracer/logging** — работает, JSONL-логи доступны для постмортем.

---

## 12. Открытые вопросы для обсуждения

1. **Variant-specific ground truth.** Если в одном vault-варианте «N days ago» имеет статью, а в другом — нет, как ingestion должен помечать такой случай? Нужен ли флаг `variant_specific=True` на pattern-узлах?

2. **Trust-region на confidence.** Стоит ли ограничить рост `uses` (например, `uses_capped = min(uses, 20)`) чтобы старые узлы не доминировали retrieval бесконечно?

3. **Ratchet pattern.** После fix'ов — стоит ли снижать MIN_CONFIDENCE постепенно (0.4 → 0.45 → 0.5) от прогона к прогону, отжимая шум?

4. **Wiki page rotation strategy.** Полная замена раз в N прогонов vs incremental truncation — какая стратегия лучше?

5. **Contract на CC tier.** Полностью включить negotiate (через MODEL_CONTRACT) или принять, что CC всегда default + усилить per-type default-контракты с реальной guidance?

---

## Приложение A — Ключевые ссылки на код

| Что | Файл:строка |
|---|---|
| Inject contract в system prompt | `agent/loop.py:2680–2683` |
| Format `## AGREED CONTRACT` | `agent/loop.py:118–131` |
| evaluator_only gate (dead) | `agent/loop.py:1912–1933` |
| FIX-437 force CLARIFICATION (dead) | `agent/loop.py:2302–2313` |
| Skip negotiate on CC tier | `agent/contract_phase.py:146–149` |
| Default contract content | `data/default_contracts/default.json` |
| Wiki retrieval scoring | `agent/wiki_graph.py:341` (`_score_candidates`) |
| Cross-type filter (FIX-433) | `agent/wiki_graph.py:375` |
| Confidence feedback | `agent/agents/wiki_graph_agent.py:50–67` |
| Patterns_text injection | `agent/orchestrator.py:89–93` |
| Wiki poisoning evidence | `data/wiki/pages/lookup.md:18, 24, 29–82` |
| Error-ingest stats | `v4.md:39–46, 134–142, 232–240, 329–337, 426–434` |
| Default contract evidence skip | `agent/evaluator.py:416–422` |

## Приложение B — Метаданные источников

- **v4 analysis:** `docs/run_analysis_2026-05-04_v4.md` (5 runs, 43 задач каждый, model=minimax-m2.7-cloud)
- **v3 baseline:** `docs/run_analysis_2026-05-04_v3.md` (5 runs × 5 задач, ранние графы 41→206 узлов)
- **Git head во время анализа:** `7c008a7 up`
- **Релевантные FIX-метки в свежих коммитах:** FIX-435, FIX-436, FIX-437, FIX-438 (последние 5 коммитов)
