# Отчёт: дубли и изменения в data/prompts/optimized/

Дата: 2026-05-13  
Файлы: 54 патча → 3 целевых файла (answer.md, sql_plan.md, learn.md)

---

## 1. Общая статистика

| Целевой файл | Патчей | Уникальных правил | Дублей внутри optimized/ | Уже в основном файле |
|---|---|---|---|---|
| answer.md    | 27 | 4 | 22 | частично (grounding_refs) |
| sql_plan.md  | 19 | 10 | 7 | нет (DDL, schema, retry) |
| learn.md     | 12 | 6 | 5 | нет (structure, loop guard) |

---

## 2. answer.md — дубли

### Мегадубль: "grounding_refs source restriction"
Один и тот же смысл ("grounding_refs только из sku-колонки SQL") повторяется в 22 из 27 патчей с минимальными вариациями формулировок:

```
03, 05, 07, 09, 10, 11, 12, 13, 15, 17, 19, 21, 25, 27, 29, 30, 31, 33, 37, 41, 48, 53
```

Ядро: `grounding_refs` = только `sku` из SQL-строк → формат `/proc/catalog/{sku}.json` → если нет sku → empty array.

**Вывод:** оставить ОДИН консолидированный вариант. Лучший кандидат — **05** (самый полный: явный список forbidden + пример).

### Уже покрыто в answer.md (основном файле):
- "Grounding Refs: Mandatory Rules" — YES/found → ≥1 SKU, zero-count → may be empty.
- Строительство пути `/proc/catalog/{sku}.json` — упомянуто в правилах.

**Разница патчей vs основной:** патчи добавляют запрет на `path`-колонку, filesystem-пути, угадывание SKU — это **добавления**, не полные дубли.

---

## 3. sql_plan.md — дубли

### Группа: "Reasoning Field Depth" (10 патчей — дубли друг друга)
```
02, 04, 06, 14, 20, 28, 29, 03(May13), 26(May13), 49
```
Все говорят: reasoning должен быть не из одной строки, а включать: колонки, операторы, ожидаемую кардинальность. Различия только в порядке пунктов.

**Лучший кандидат:** **06** (3 пункта: column mapping, data quality, alternative justification) + **28** (добавляет in-session rules).

### Группа: "DDL/DML Prohibition" (5 патчей — дубли)
```
16, 22, 31, 40, 47
```
Все: не генерировать DROP/CREATE/ALTER/INSERT/UPDATE/DELETE. Различия: некоторые дают error JSON, некоторые OUTCOME_BLOCKED.

**Лучший кандидат:** **31** (самый полный — checklist + error JSON формат).

### Уже покрыто в sql_plan.md (основном):
- `reasoning` требование упомянуто кратко ("chain-of-thought").
- WHERE clause обязателен — есть.
- String Literals без discovery — есть.
- CONFIRMED VALUES — есть.
- Discovery isolation — есть.
- Count Questions: Fetch Sample SKUs — есть.

---

## 4. learn.md — дубли

### Группа: "Reasoning Depth/Structure" (10 патчей — дубли)
```
01(May12), 05, 32, 01(May13), 16, 19, 28, 36, 38, 52
```
Все: reasoning ≥3 предложений, quote verbatim error, name offending token, corrective action.

**Лучший кандидат:** **36** (самая структурированная: error/cause/fix трёхчастная схема + reject patterns + required shape).

### Уже покрыто в learn.md (основном):
- Common failure patterns (multi-join, wrong column, type mismatch) — есть.
- Discovery Fallback Rule — есть.

---

## 5. Уникальные правила — НОВЫЙ КОНТЕНТ для merge

### answer.md — добавить:

| Источник | Правило | Статус |
|---|---|---|
| 03-09-25 (best: 09) | COUNT/aggregate-only → grounding_refs=[] + пример с sample SKU query | **новое** (добавление к existing rule) |
| 34 | "Prior LEARN Result Carryover" — если prior цикл вернул numeric count с OUTCOME_OK, использовать этот count | **уникальное** |
| 04(May13) | OUTCOME_FAIL при нарушении grounding_refs | **новое поведение** |
| 15, 20 | OUTCOME_NEED_MORE_DATA + LEARN cycle при aggregate без sku | **новое поведение** |

### sql_plan.md — добавить:

| Источник | Правило | Статус |
|---|---|---|
| 31 (DDL checklist) | Pre-Output Query Checklist: no DDL/DML, starts with SELECT, no `;` chaining | **полностью новое** |
| 18 | Ambiguity Resolution Before Query — enumerate interpretations, AMBIGUITY flag | **полностью новое** |
| 26(May12) | Literal Value Provenance — каждый literal из task text / discovery / AGENTS.MD | **расширяет existing** |
| 27, 50 (best: 50) | Schema Pre-Flight Validation — проверка table/column перед emit | **полностью новое** |
| 25 | In-Session Rule Application Log — логировать как каждое правило влияет на query | **полностью новое** |
| 44 | Post-LEARN Retry Obligation — после LEARN reasoning должен назвать что изменилось | **полностью новое** |
| 45 | Retry Divergence (CRITICAL) — structural diff от failed query обязателен | **полностью новое** |
| 24 | SKU Projection Mandatory — COUNT-only forbidden без задачи подсчёта | **расширяет Count Questions** |
| 51 | No Placeholder Literals — нет `type='X'`, `brand='?'` в queries | **расширяет String Literals** |
| 54 | LLM-Fail Retry Obligation — после error_type=llm_fail → новый query | **новое** |
| 10(May13) | Filter Value Extraction — нет placeholder, каждый WHERE-value из task text | **расширяет String Literals** |

### learn.md — добавить:

| Источник | Правило | Статус |
|---|---|---|
| 36 | Reasoning Field Structure (MANDATORY) — error/cause/fix трёхчастная схема | **расширяет existing** |
| 08 | Conclusion Specificity — цитировать конкретный gate/rule ID (sec-001, sql-014) | **полностью новое** |
| 06(May13) | Conclusion Field Requirements — restate query + exact error + corrective change | **полностью новое** |
| 14 | Conclusion: Mechanism Not Symptom — `<failure> because <causal mechanism>` | **полностью новое** |
| 22 | Rule Content Specificity — цитировать exact SQL token/pattern в rule_content | **полностью новое** |
| 46 | Field Substance Validation — ≥20 chars + schema-specific term в каждом поле | **полностью новое** |
| 39, 42 | Loop Guard — identical/empty reasoning → OUTCOME_FAIL немедленно | **полностью новое** |
| 43 | Grounding-Aware SQL Plan — при диагнозе missing grounding → mandate sku projection | **полностью новое** |

---

## 6. Файлы к удалению (чистые дубли)

### answer.md — удалить (покрыты консолидированным правилом):
03, 07, 10, 11, 12, 13, 15, 17, 19, 21, 30, 33, 37, 41, 48  
*(05 и 09 — оставить как основа консолидированного правила)*

### sql_plan.md — удалить:
02, 04, 14, 20, 28, 29, 03(May13), 49 *(reasoning-дубли, покрыты 06+28-combined)*  
16, 22, 40, 47 *(DDL-дубли, покрыты 31)*  
32 *(schema-дубль, покрыт 50)*  
23(May13) *(retry divergence, покрыт 45)*

### learn.md — удалить:
01(May12), 05, 32, 01(May13), 16, 19, 28, 38, 52 *(reasoning-дубли, покрыты 36)*

---

## 7. Предлагаемая структура merge

### answer.md
```
[существующие секции]
+ Grounding Refs Source Restriction (консолидированная, расширенная из 05)
  └── COUNT/aggregate → [] + sample-SKU query (из 09)
  └── OUTCOME_NEED_MORE_DATA при aggregate без sku (из 15, 20)
+ Prior LEARN Result Carryover (из 34)
```

### sql_plan.md
```
[существующие секции]
+ Pre-Output Query Checklist / DDL Prohibition (из 31)
+ Reasoning Field Depth (консолидированная из 06+28)
+ Ambiguity Resolution Before Query (из 18)
+ Literal Value Provenance (из 26-May12)
+ Schema Pre-Flight Validation (из 50)
+ In-Session Rule Application Log (из 25)
+ Post-LEARN Retry Obligation + Retry Divergence (из 44+45)
+ SKU Projection Mandatory (из 24)
+ No Placeholder Literals (из 51)
+ LLM-Fail Retry Obligation (из 54)
```

### learn.md
```
[существующие секции]
+ Reasoning Field Structure MANDATORY (из 36)
+ Conclusion Field Requirements (из 06-May13 + 14 + 08)
+ Rule Content Specificity (из 22)
+ Field Substance Validation (из 46)
+ Loop Guard (из 39 + 42)
+ Grounding-Aware SQL Plan (из 43)
```

---

## 8. Что удалить из optimized/ после merge

После объединения: **39 файлов к удалению**, **15 файлов использованы**.

Используемые (источники merge):
- answer: 05, 09, 15, 20, 34
- sql_plan: 06, 24, 25, 26(May12), 27, 31, 44, 45, 51, 54, 10(May13), 18
- learn: 08, 22, 36, 39, 42, 43, 46, 06(May13), 14
