# Wiki Log

<!-- Append-only лог. Новые записи добавляются в конец. -->

## 2026-05-05T00:00:00

**Операция:** init
**Домен:** спецификации

**Затронуто страниц:** 23

- СОЗДАНА: `.wiki/спецификации/архитектура/execution-flow.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/llm-routing.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/prompt-system.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/dspy-optimization.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/security-stall.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/evaluator.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/wiki-memory.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/harness-protocol.md` (stub)
- СОЗДАНА: `.wiki/спецификации/архитектура/observability.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/ollama-structured-output.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/remove-researcher.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/context-management.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/wiki-graph-integration.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/wiki-big-bang-restructure.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/graph-visualization.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/multi-agent-architecture.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/scripts-lifecycle-automation.md` (stub)
- СОЗДАНА: `.wiki/спецификации/дизайн-спеки/knowledge-accumulation-redesign.md` (stub)
- СОЗДАНА: `.wiki/спецификации/анализ-прогонов/run-analysis-v4-v5.md` (developing)
- СОЗДАНА: `.wiki/спецификации/фиксы/fix-423-424-425.md` (stub)
- СОЗДАНА: `.wiki/спецификации/фиксы/fix-five-bugs-2026-05-04.md` (stub)
- ПРОПУЩЕНА: docs/superpowers/specs/2026-04-30-architecture-docs-actualization-design.md — covered by architecture pages
- ПРОПУЩЕНА: docs/run_analysis_2026-05-04.md, docs/run_analysis_2026-05-04_v2.md — covered by run-analysis-v4-v5.md

**Примечание:** init домена спецификации. Обработано 37 из ~74 файлов (specs + architecture); планы (`docs/superpowers/plans/`) пропущены (не являются дизайн-спецификациями).

---

## 2026-05-06T00:00:00

**Операция:** init
**Домен:** планы
**Источник:** `docs/superpowers/plans/` (27 файлов)

**Затронуто страниц:** 27 (создано)

### планы / фичи (14 страниц)
- СОЗДАНА: `.wiki/планы/фичи/gepa-integration.md` (developing)
- СОЗДАНА: `.wiki/планы/фичи/gepa-trainval-split.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/contract-phase.md` (developing)
- СОЗДАНА: `.wiki/планы/фичи/contract-dspy-optimization.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/contract-prompts.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/wiki-graph-gaps.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/graph-visualization.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/multi-agent-architecture.md` (developing)
- СОЗДАНА: `.wiki/планы/фичи/scripts-lifecycle-automation.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/orchestrator-contract-negotiation.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/wiki-big-bang-restructure.md` (developing)
- СОЗДАНА: `.wiki/планы/фичи/knowledge-accumulation-redesign.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/context-management.md` (stub)
- СОЗДАНА: `.wiki/планы/фичи/dispatch-reliability.md` (stub)

### планы / фиксы (8 страниц)
- СОЗДАНА: `.wiki/планы/фиксы/agent-fixes-knowledge-pipeline.md` (developing)
- СОЗДАНА: `.wiki/планы/фиксы/contract-graph-fixes.md` (stub)
- СОЗДАНА: `.wiki/планы/фиксы/contract-b3-grounding.md` (stub)
- СОЗДАНА: `.wiki/планы/фиксы/wiki-graph-contract-improvements.md` (stub)
- СОЗДАНА: `.wiki/планы/фиксы/fix-423-424-425.md` (stub)
- СОЗДАНА: `.wiki/планы/фиксы/five-bugs.md` (stub)
- СОЗДАНА: `.wiki/планы/фиксы/quality-degradation-fixes.md` (developing)
- СОЗДАНА: `.wiki/планы/фиксы/t43-followup-fixes.md` (stub)

### планы / рефакторинги (3 страницы)
- СОЗДАНА: `.wiki/планы/рефакторинги/remove-researcher.md` (stub)
- СОЗДАНА: `.wiki/планы/рефакторинги/ollama-structured-output.md` (stub)
- СОЗДАНА: `.wiki/планы/рефакторинги/architecture-docs-actualization.md` (stub)

### планы / аудиты (2 страницы)
- СОЗДАНА: `.wiki/планы/аудиты/t43-architecture-audit.md` (developing)
- СОЗДАНА: `.wiki/планы/аудиты/run5-all-tasks.md` (stub)

**Примечание:** init домена планы из 27 source files. Синтез: каждый план → wiki-страница с целью, ключевыми паттернами, файлами изменений. Добавлен домен `планы` в domain-map.json.

---

## 2026-05-06T01:00:00

**Операция:** init
**Источник:** agent/*.py (26 файлов)
**Домен:** агент

**Затронуто страниц:** 16

- СОЗДАНА: `.wiki/агент/модули/orchestrator.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/dispatch.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/classifier.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/loop.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/security.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/stall.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/evaluator.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/prompt.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/prompt-builder.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/wiki-graph.md` (developing)
- СОЗДАНА: `.wiki/агент/модули/wiki-memory.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/log-compaction.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/prephase.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/contract-phase.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/cc-client.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/task-types.md` (stub)

**Примечание:** init домена агент из agent/*.py. Покрыты все ключевые модули (orchestrator, dispatch, classifier, loop, security, stall, evaluator, prompt, prompt_builder, wiki_graph, wiki, log_compaction, prephase, contract_phase, cc_client, task_types). Пропущено: `agents/` subagents (можно добавить отдельным ingest), `dspy_lm.py`, `dspy_examples.py`, `json_extract.py`, `models.py`, `postrun.py`, `preflight.py`, `tracer.py`, `maintenance/`. Также добавлен домен `агент` в domain-map.json и исправлен структурный баг JSON (домен "планы" был вне массива domains).

---

## 2026-05-06T12:00:00

**Операция:** ingest
**Источник:** agent/agents/ (9 файлов: classifier_agent.py, executor_agent.py, planner_agent.py, compaction_agent.py, security_agent.py, stall_agent.py, step_guard_agent.py, verifier_agent.py, wiki_graph_agent.py)
**Домен:** агент

**Затронуто страниц:** 9

- СОЗДАНА: `.wiki/агент/модули/classifier-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/executor-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/planner-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/compaction-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/security-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/stall-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/step-guard-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/verifier-agent.md` (stub)
- СОЗДАНА: `.wiki/агент/модули/wiki-graph-agent.md` (stub)

**Примечание:** Покрыты все контрактные агенты мультиагентной архитектуры из agent/agents/. Каждый агент — тонкая обёртка над backing-модулем с изоляцией через agent.contracts.

---

## 2026-05-06T14:00:00

**Операция:** lint
**Домен:** агент

**Проверено страниц:** 25
**Errors:** 0 | **Warnings:** 3 | **Info:** 3

### Результаты проверок

- [FM-001/002/003/004] OK: все frontmatter поля (wiki_sources, wiki_updated, wiki_status, tags) валидны во всех 25 страницах
- [FM-005] OK: все wiki_sources ссылаются на существующие файлы (проверено 25 страниц)
- [CT-003] OK: нет broken WikiLinks — все 23 уникальных [[target]] соответствуют файлам в агент/модули/
- [ST-001/002] OK: index.md полностью соответствует реальным файлам (25 страниц)
- [CT-004] WARNING: 2 страницы без входящих WikiLinks (orphan): `classifier-agent.md`, `wiki-graph-agent.md`
  — orchestrator.md упоминает ClassifierAgent и WikiGraphAgent текстом, но не добавляет [[classifier-agent]] / [[wiki-graph-agent]] WikiLinks
- [FM-006] WARNING: 18 из 25 страниц имеют статус `stub` — большинство агент/модули/* требует наполнения
  — Особо тонкие стабы (≤30 строк): `classifier-agent.md` (29), `prompt-builder.md` (29)
- [CV-001] WARNING: 9 модулей агента не имеют wiki-страниц (intentionally excluded при init):
  `contract_models.py`, `contract_monitor.py`, `dspy_examples.py`, `dspy_lm.py`, `json_extract.py`,
  `models.py`, `postrun.py`, `preflight.py`, `tracer.py`
  — `json_extract.py` (216 строк), `dspy_examples.py` (389 строк), `dspy_lm.py` (165 строк), `postrun.py` (168 строк) — кандидаты на ingest
- [CT-005] INFO: wiki_status=developing у 7 страниц (orchestrator, dispatch, classifier, loop, security, evaluator, wiki-graph) — содержимое актуально
- [CT-002] INFO: placeholder-текст не обнаружен
- [ST-003] INFO: schema.md отсутствует в .wiki/.config/ (не критично для агент-домена)

### Рекомендации

1. Добавить [[classifier-agent]] в orchestrator.md (Связанные концепции)
2. Добавить [[wiki-graph-agent]] в orchestrator.md (Связанные концепции)
3. Поднять стабы до developing: stall.md, prompt.md, prompt-builder.md, wiki-memory.md — содержат достаточно информации
4. Рассмотреть ingest для: json_extract.py, dspy_lm.py, postrun.py, dspy_examples.py

---

## 2026-05-06T15:00:00

**Операция:** ingest
**Источник:** `agent/json_extract.py`
**Домен:** агент

**Затронуто страниц:** 1

- СОЗДАНА: `.wiki/агент/модули/json-extract.md` (developing)

**Примечание:** Модуль вынесен из loop.py. Покрыты: 7-уровневый алгоритм _extract_json_from_text, _normalize_parsed, специальные случаи FIX-146/150/207/212/265/401.

---

## 2026-05-05T00:00:00

**Операция:** lint
**Домен:** планы

**Проверено страниц:** 27
**Errors:** 1 | **Warnings:** 0 | **Info:** 23

- [ST-005] ERROR: schema.md отсутствует в .wiki/.config/
- [CT-004] INFO: 23 страницы домена планы без входящих WikiLinks (orphan)
- [CT-003] OK: все 3 WikiLinks ([[gepa-integration]], [[quality-degradation-fixes]], [[t43-followup-fixes]]) корректны
- [FM-001/002/003/004] OK: все frontmatter поля валидны во всех 27 страницах
- [FM-005] OK: все wiki_sources существуют на диске
- [CT-002/005] OK: нет устаревших стабов и placeholder-текста
- [CV-001/002] OK: все 27 source files покрыты wiki-страницами
- [ST-001/002] OK: index.md соответствует реальным файлам

---

## 2026-05-05T00:01:00

**Операция:** lint-fix
**Домен:** планы

**Выполнено по отчёту lint:**

1. СОЗДАНА: `.wiki/.config/schema.md` — устраняет [ST-005] ERROR
2. ОБНОВЛЕНА: `.wiki/планы/фичи/gepa-integration.md` — добавлен `## Связанные планы` с [[gepa-trainval-split]]
3. ОБНОВЛЕНА: `.wiki/планы/фиксы/t43-followup-fixes.md` — добавлен `## Связь` с [[t43-architecture-audit]]
4. ОБНОВЛЕНА: `.wiki/планы/фиксы/quality-degradation-fixes.md` — добавлен `## Связь` с [[run5-all-tasks]]

**Примечание:** Обратные WikiLinks добавлены туда, где они отсутствовали. Исходные ссылки (run5-all-tasks → quality-degradation-fixes, t43-architecture-audit → t43-followup-fixes) уже присутствовали в страницах-источниках.

---
