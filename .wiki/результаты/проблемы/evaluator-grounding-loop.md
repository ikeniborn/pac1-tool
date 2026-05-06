---
wiki_title: "Evaluator grounding_refs rejection loop"
wiki_status: stub
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04.md
wiki_domain: результаты
wiki_type: system-problem
tags: [evaluator, grounding-refs, rejection-loop, contract, system-problem]
---

# Evaluator grounding_refs rejection loop

**Статус:** не решена (упоминается в v4 как нерешённая)

## Симптом

Evaluator отвергает `report_completion` из-за `required_evidence` в `grounding_refs`. Агент не понимает ожидаемый формат и застревает в rejection loop (2+ отказа → stall hints → принудительное завершение).

## Пример (t40, v1)

Контракт создаётся с расплывчатыми `required_evidence` (текстовые описания типа "account listing from vault") вместо конкретных путей (`accounts/acct_007.json`).

Evaluator ожидает конкретные пути → агент не понимает что изменить → цикл повторяется.

## Рекомендации

1. Contract builder должен задавать `required_evidence` как конкретные пути к файлам, не текстовые описания.
2. Evaluator должен принимать текстовые аннотации в grounding_refs (или чётче объяснять формат).
3. Stall detection должен быстрее выходить из rejection loop при повторяющихся отказах evaluator.

## Связи

- [[результаты/задачи/t40-crm-lookup]] — задача, где проявляется проблема
- [[результаты/сессии/run-v1-v2-v3]] — контекст обнаружения
