---
wiki_title: "t40 — CRM lookup (аккаунты менеджера)"
wiki_status: developing
wiki_created: 2026-05-05
wiki_updated: 2026-05-05
wiki_sources:
  - docs/results/run_analysis_2026-05-04.md
  - docs/results/run_analysis_2026-05-04_v2.md
  - docs/results/run_analysis_2026-05-04_v3.md
  - docs/results/run_analysis_2026-05-04_v4.md
wiki_domain: результаты
wiki_type: task-analysis
tags: [lookup, crm, t40, missing-refs, evaluator-rejection]
---

# t40 — CRM lookup (аккаунты менеджера)

**Тип задачи:** lookup/crm  
**Win rate:** 3/25 в v1–v4 (12%). В v4 отдельно: 3/5 (60%) — значительный рост.

## Формулировка задачи

"Какие аккаунты у менеджера X?" — менеджер рандомизируется каждый прогон. Нужно найти все аккаунты в `accounts/` привязанные к этому менеджеру.

## Паттерн ошибок (v1–v3)

- Агент не включает все требуемые grounding refs: пропускает `mgr_002.json`, `acct_010.json`, `acct_007.json`, `contacts/mgr_002.json`
- Evaluator rejection loop: evaluator требует "required_evidence" в специфическом формате, агент не понимает и застревает
- Нестабильность: успех зависит от варианта vault (какой менеджер, какой порядок файлов)

## Динамика по версиям

| Версия | Win rate | Тренд |
|--------|----------|-------|
| v1 | 1/5 (20%) | Случайный успех в run3 |
| v2 | 0/5 (0%) | Деградация |
| v3 | 2/5 (40%) | Рост (run2, run4) |
| v4 | 3/5 (60%) | Лучший результат — wiki/граф начинают помогать |

## v4: рост до 60%

К v4 граф накопил правила про lookup workflow ("list accounts/ first", "read ALL files"). В прогонах 2 и 4 агент справился. В прогоне 5 — всё равно пропустил Acme Logistics (ожидаемые компании меняются каждый прогон).

## Ключевые проблемы

1. **Evaluator grounding_refs**: required_evidence должны быть конкретными путями, а не текстовыми описаниями. Агент застревает в rejection loop.
2. **Пропуск файлов при сканировании**: при 10+ файлах в accounts/ агент пропускает 1–2 файла. Builder prompt должен усилить инструкцию "read ALL files, do not skip".
3. **Vault рандомизация**: ожидаемая компания меняется — успех частично определяется сложностью конкретного запроса.

## Рекомендации

1. Исправить contract required_evidence: конкретные пути (`accounts/acct_007.json`), не текст.
2. Усилить builder prompt: "читай ВСЕ файлы в accounts/ последовательно без пропусков".
3. Добавить в систему явное правило: при lookup CRM — всегда включать `mgr_*.json` в grounding_refs.

## Связи

- [[результаты/проблемы/evaluator-grounding-loop]] — проблема rejection loop
- [[результаты/задачи/t13-crm-reschedule]] — смежная CRM задача
- [[результаты/сессии/run-v4-all-tasks]] — v4 показала 60% на этой задаче
