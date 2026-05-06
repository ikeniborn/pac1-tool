---
wiki_title: "t43 — lookup/temporal (статья за N дней)"
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
tags: [lookup, temporal, distill, t43, vault-randomization, false-positive]
---

# t43 — lookup/temporal (статья за N дней)

**Тип задачи:** lookup/temporal (рандомизируется vault между CRM и distill)  
**Win rate:** 7/25 в v1–v4 (28%). В v4 отдельно: 3/5 (60%).

## Особенность задачи

Benchmark рандомизирует vault между прогонами:
- **CRM vault** → t43 = lookup → агент находит статью → **1.00**
- **Distill vault (разрежённый)** → t43 = temporal distill → ожидается CLARIFICATION → агент возвращает OK → **0.00**
- **Distill vault (плотный)** → t43 = temporal lookup → ожидается CLARIFICATION → агент возвращает CLARIFICATION → **1.00** (случайно)

## Паттерн успехов (часто случайный)

| Версия | Успехов | Причина успехов |
|--------|---------|-----------------|
| v1 | 3/5 | t43 = lookup на CRM vault → агент находит |
| v2 | 3/5 | t43 = CLARIFICATION ожидалась → агент дал CLARIFICATION |
| v3 | 2/5 | Аналогично |
| v4 | 3/5 | Смешанно |

**Вывод**: t43 считается правильно только случайно, не из-за знаний. Агент не умеет детектировать, когда vault слишком разрежён для ответа.

## Проблема в v2 run5 и v3 run5: DENIED_SECURITY

В некоторых прогонах агент выдавал DENIED_SECURITY на стандартную задачу "найти статью". Гипотеза: накопленные antipatterns из ошибок сместили агента в сторону блокировки. Это регрессия из-за накопления.

## Рекомендации

1. Агент должен уметь детектировать разреженность vault: если в `01_capture/` нет релевантных файлов за период → возвращать CLARIFICATION, не OK.
2. Аудит antipattern накопления: антипаттерны не должны провоцировать ложное DENIED_SECURITY.
3. Разделить t43 на два субтипа по vault-типу (CRM vs distill) для более чёткой классификации.

## Связи

- [[результаты/задачи/t42-capture-lookup]] — похожая задача (N дней назад)
- [[результаты/проблемы/graph-retrieval-mixing]] — antipatterns в retrieval
- [[результаты/сессии/run-v1-v2-v3]] — история прогонов
