# Отчёт: дубли и изменения в data/prompts/optimized/

Дата: 2026-05-13 (v2 — исправленная версия)
Файлы: 54 патча → 3 целевых файла

---

## 0. Контекст: что означает `score`

Метаданные патча: `<!-- score: 0.4 -->` — оценка пайплайна, насколько патч улучшил результат.

| Score | Значение |
|---|---|
| 0.4 | Высокий impact, баг реально повторялся |
| 0.2–0.3 | Средний, улучшает граничные случаи |
| 0.0–0.1 | Низкий — либо уже покрыто, либо редкий случай |

Топ-патчи по score (0.4): 05(May12), 10(May12), 12(May12), 43(May13), 07(May13), 08(May13), 09(May13).
Все высокоприоритетные — про `grounding_refs` в answer.md. Это **самый частый и дорогой баг**.

---

## 1. answer.md

### Что уже есть в основном файле

Строки 28–33 answer.md уже содержат:
```
- YES/found: grounding_refs MUST contain ≥1 SKU from SQL results.
- COUNT/aggregate: cite ≥1 sample SKU from underlying rows.
- Zero-count: grounding_refs MAY be empty.
- grounding_refs empty + numeric required → OUTCOME_NEED_MORE_DATA, trigger LEARN.
- Never emit OUTCOME_OK without session-sourced SKU (unless zero-count).
```

**Вывод:** правило есть, но не работало (score 0.4 у большинства патчей = баг повторялся).
Причина: основное правило не перечисляет запрещённые источники — `path` колонка, filesystem, изобретённые SKU.

### Дубли внутри optimized/

**22 патча повторяют одно правило** "grounding_refs только из sku-колонки SQL":

```
03, 05, 07, 09, 10, 11, 12, 13, 15, 17, 19, 21, 25, 27, 29, 30, 31, 33, 37, 41, 48, 53
```

Различия: порядок bullet-points, разное количество примеров, незначительные формулировки.
→ Оставить **один консолидированный** вариант.

Лучший кандидат: **05** (полный список Forbidden + derivation rule) + элементы из **09** (примеры с COUNT) + **02(May13)** (пример correct/wrong).

### Конфликты (!)

**Конфликт 1 — answer.md патч 04(May13):**
```
grounding_refs violation → emit OUTCOME_FAIL
```
Основной файл говорит `OUTCOME_NEED_MORE_DATA`. Patch 04 — **неверен**, противоречит основному поведению.
→ Patch 04 отбрасывается целиком.

**Конфликт 2 — patch 35 vs patch 15(May13):**
- 35: violation → `OUTCOME_NEED_MORE_DATA` (согласован с main)
- 15: aggregate без sku → нельзя OUTCOME_OK, нужен LEARN-цикл для sample-SKU (расширяет main)
→ 15 правильный и новый.

### Уникальные новые правила для answer.md

| Патч | Правило | Что добавляет |
|---|---|---|
| 05+09+02(May13) | Grounding Refs Source (консолидированный) | Явный список forbidden sources + примеры |
| 15 | OUTCOME_NEED_MORE_DATA при COUNT/aggregate без sample-SKU query | Уточняет failure mode |
| 34 | Prior LEARN Result Carryover — если prior цикл вернул count с OUTCOME_OK, использовать | Полностью новое |

**Итого answer.md:** 3 новых раздела, 22 патча — дубли, 1 патч (04-May13) — конфликт → отбросить.

---

## 2. sql_plan.md

### Что уже есть в основном файле

- `reasoning` — краткое "chain-of-thought: which tables/columns relevant and why" (1 строка)
- "Never copy model names verbatim... without prior discovery" (String Literals раздел)
- COUNT + sample SKU (Count Questions раздел)
- Discovery isolation
- WHERE обязателен
- Disambiguate 'X and Y' (ограниченно — только для X and Y)

**НЕТ:** DDL/DML запрет, schema validation, retry divergence, ambiguity flag, placeholder literals ban, in-session rule log, SKU projection mandatory.

### Дубли внутри optimized/

**Группа 1: Reasoning depth (10 патчей — дубли)**
```
02, 04, 06, 14, 20, 28, 29, 03(May13), 26(May13), 49
```
Все о "reasoning должен быть подробным, ≥3 пунктов".
Уникальные элементы внутри группы:
- 06: "alternative justification" (почему не другой query shape)
- 20: AMBIGUITY flag (совпадает с темой patch 18!)
- 28: "in-session rules" (как текущие правила влияют на query)
- 26(May13): "expected cardinality"

→ Консолидировать в **одну секцию** из 06 + элементы из 28, 20, 26(May13).

**Группа 2: DDL/DML prohibition (5 патчей)**
```
16, 22, 31, 40, 47
```

**Конфликт выходного формата (!):**
- 16 → `{"error": "DDL_BLOCKED"}`
- 22 → `OUTCOME_SKIP`
- 31 → `{"error": "PLAN_ABORTED_NON_SELECT", "queries": [], ...}`
- 40 → `OUTCOME_BLOCKED`
- 47 → нет явного outcome, только примеры переформулировки

OUTCOME_SKIP и OUTCOME_BLOCKED не определены в системе. Корректный формат — json с `error` полем внутри sql_plan output (см. 31).

→ Лучший кандидат: **31** (checklist + правильный формат) + примеры переформулировки из **47**.

**Группа 3: Placeholder literals (2 патча — дубли)**
```
51, 10(May13)
```
Оба: "нет placeholder literals в WHERE".
Различия:
- 51: перечисляет `type='X'`, `brand='?'`, AGENTS.MD как valid source
- 10(May13): добавляет "если нет filterable value → omit predicate entirely"

→ Один раздел, объединить оба: **51** + правило "omit predicate if no value" из **10(May13)**.

**Группа 4: Retry divergence (3 патча — перекрываются)**
```
23(May13), 44, 45, 54
```
- 44: reasoning ДОЛЖЕН назвать rule learned + как query отличается
- 45: query ДОЛЖЕН структурно отличаться от failed (CRITICAL)
- 54: при `error_type=llm_fail` → новый query (subset of 45)
- 23(May13): после LEARN → ≥1 token должен измениться (subset of 45)

→ Два раздела: **45** (structural divergence requirement) + **44** (reasoning requirement). 54 и 23(May13) поглощаются 45.

**Группа 5: Schema validation (3 патча)**
```
27, 32, 50
```
Все: проверить table/column против schema перед emit.
- 27: case-sensitive match, typos → fix pre-emit
- 32 = 50 (почти идентичны): FROM/JOIN/WHERE/ORDER BY check, self-correct
→ **50** — самый полный. 27 добавляет case-sensitivity. 32 — дубль 50.

### Пересечение патчей (ambiguity)

Patches 18 и 20 оба о ambiguity:
- 18: Ambiguity Resolution — enumerate interpretations, clarification step
- 20: AMBIGUITY flag в reasoning поле

→ Один раздел, 18 основа + AMBIGUITY флаг из 20.

### Уникальные новые правила для sql_plan.md

| Патч-источник | Раздел | Что добавляет |
|---|---|---|
| 31 + 47 | Pre-Output DDL/DML Guard | Полностью новое. Выходной формат: json с error полем |
| 06 + 28 + 20 + 26(May13) | Reasoning Field Depth (consolidated) | Расширяет 1-строчное требование до структурированного |
| 18 + 20 | Ambiguity Resolution | Расширяет "Disambiguate X and Y" до общего правила + AMBIGUITY flag |
| 26(May12) | Literal Value Provenance | Расширяет CONFIRMED VALUES: каждый literal должен быть traceable |
| 50 + 27 | Schema Pre-Flight Validation | Полностью новое |
| 25 | In-Session Rule Application Log | Полностью новое |
| 45 + 44 | Post-LEARN Retry Divergence | Полностью новое |
| 24 | SKU Projection Mandatory | Расширяет Count Questions до всех grounding-случаев |
| 51 + 10(May13) | No Placeholder Literals | Расширяет String Literals раздел |

**Итого sql_plan.md:** 9 новых/расширенных разделов. Дубли: 26 из 35 патчей.

---

## 3. learn.md

### Что уже есть в основном файле

```
- reasoning: "what assumption was wrong" (1 строка)
- conclusion: "human-readable summary of the finding (one sentence)" (1 строка)
- rule_content: "starts with Never/Always/Use" (1 строка)
```

Нет: структурных требований к полям, loop guard, validation lengths, conclusion mechanism vs symptom.

### Дубли внутри optimized/

**Группа: Reasoning structure (10 патчей — дубли)**
```
01(May12), 05, 32, 01(May13), 16, 19, 28, 36, 38, 52
```
Все: reasoning ≥3 частей (error/cause/fix или quote/hypothesis/action).
Лучший кандидат: **36** (самый структурированный с reject patterns и required shape) + **28** (добавляет error_type enum + format string).

**Группа: Conclusion requirements (3 патча — разные аспекты, НЕ дубли)**
```
08, 06(May13), 14
```
- 08: cite specific gate/rule ID (sec-001, sql-014)
- 06(May13): restate query + exact error + corrective change
- 14: mechanism not symptom ("because <causal mechanism>")

→ Три разных требования к conclusion → один раздел "Conclusion Field Requirements" из всех трёх.

**Группа: Field substance (2 патча)**
```
18(May13), 46
```
- 18: ≥2 sentences, quote exact error, reference failed SQL fragment
- 46: ≥20 chars + schema-specific term в каждом поле

→ Оба валидны, дополняют друг друга. Один раздел "Field Substance Validation".

**Группа: Loop guard (2 патча — разные условия)**
```
39, 42
```
- 39: corrected query == failed query → OUTCOME_NONE_CLARIFICATION
- 42: reasoning empty OR identical to prior LEARN → OUTCOME_FAIL

→ Разные trigger условия → один раздел "Loop Guard" из обоих.

### Уникальные новые правила для learn.md

| Патч-источник | Раздел | Что добавляет |
|---|---|---|
| 36 + 28 | Reasoning Field Structure (MANDATORY) | Структурирует 1-строчное требование |
| 08 + 06(May13) + 14 | Conclusion Field Requirements | Полностью новое — 3 разных требования |
| 22 | Rule Content Specificity | Полностью новое — cite exact SQL token |
| 18(May13) + 46 | Field Substance Validation | Полностью новое — ≥20 chars, schema term |
| 39 + 42 | Loop Guard | Полностью новое |
| 43 | Grounding-Aware SQL Plan | Полностью новое в learn.md |

**Итого learn.md:** 6 новых разделов. Дубли: 15 из 24 патчей.

---

## 4. Конфликты — требуют решения перед merge

| # | Конфликт | Патчи | Рекомендация |
|---|---|---|---|
| 1 | DDL block outcome: DDL_BLOCKED / OUTCOME_SKIP / PLAN_ABORTED_NON_SELECT / OUTCOME_BLOCKED | 16, 22, 31, 40 | Использовать формат из 31: `{"error":"PLAN_ABORTED_NON_SELECT","queries":[],...}` |
| 2 | grounding violation outcome: OUTCOME_FAIL vs OUTCOME_NEED_MORE_DATA | 04(May13) vs main + 15 | Основной файл правильный → OUTCOME_NEED_MORE_DATA. Патч 04 отбросить. |

---

## 5. Итоговый план merge

### answer.md
```
ПЕРЕЗАПИСАТЬ: секцию "Grounding Refs: Mandatory Rules"
  → расширить forbidden sources (path column, filesystem, invented, prior sessions)
  → добавить примеры correct/wrong из 02(May13)
ДОБАВИТЬ: "Grounding Refs Failure Mode" — COUNT/aggregate без sample-SKU query: обязателен LEARN
ДОБАВИТЬ: "Prior LEARN Result Carryover" (из 34)
```

### sql_plan.md
```
ДОБАВИТЬ: "Pre-Output DDL/DML Guard" (31 + 47 examples)
РАСШИРИТЬ: "reasoning" requirement → Reasoning Field Depth (06+28+20+26-May13)
РАСШИРИТЬ: "Disambiguate X and Y" → Ambiguity Resolution (18+20)
ДОБАВИТЬ: "Literal Value Provenance" (26-May12)
ДОБАВИТЬ: "Schema Pre-Flight Validation" (50+27)
ДОБАВИТЬ: "In-Session Rule Application Log" (25)
ДОБАВИТЬ: "Post-LEARN Retry Divergence" (45) + "Post-LEARN Retry Reasoning" (44)
РАСШИРИТЬ: "Count Questions" → SKU Projection Mandatory (24)
РАСШИРИТЬ: "String Literals in WHERE" → No Placeholder Literals (51+10-May13)
```

### learn.md
```
РАСШИРИТЬ: "reasoning" requirement → Reasoning Field Structure MANDATORY (36+28)
ДОБАВИТЬ: "Conclusion Field Requirements" (08+06-May13+14)
ДОБАВИТЬ: "Rule Content Specificity" (22)
ДОБАВИТЬ: "Field Substance Validation" (18-May13+46)
ДОБАВИТЬ: "Loop Guard" (39+42)
ДОБАВИТЬ: "Grounding-Aware SQL Plan" (43)
```

---

## 6. Файлы к удалению из optimized/ после merge

### answer.md — 24 файла к удалению (использовать: 05, 09, 02-May13, 15, 34)
```
03, 07, 10, 11, 12, 13, 17, 19, 21, 25, 27, 29, 30, 33, 37, 41, 48
04(May13) — КОНФЛИКТ, отбросить
07(May13), 08(May13), 09(May13), 11(May13), 13(May13), 20(May13), 21(May13), 31(May13), 35(May13)
```

### sql_plan.md — 17 файлов к удалению (использовать: 06, 25, 26-May12, 31, 47, 24, 44, 45, 50, 51)
```
02, 04, 14, 20, 22, 28, 29, 32, 40
03(May13), 10(May13), 16(May13), 23(May13), 26(May13), 49(May13), 54(May13)
18 — частично поглощается 06, частично 26-May12
```

### learn.md — 16 файлов к удалению (использовать: 22, 28, 36, 39, 42, 43, 46, 06-May13, 08, 14, 18-May13)
```
01(May12), 05, 32
01(May13), 16, 19, 38, 52
```

---

## 7. Сводная таблица

| | answer.md | sql_plan.md | learn.md | Итого |
|---|---|---|---|---|
| Всего патчей | 27 | 19 | 12 | 54 |
| Дубли (удалить) | 22 | 16 | 10 | 48 |
| Использовать | 5 | 9 | 11 | 25 |
| в т.ч. конфликтных (отбросить) | 1 | 0 | 0 | 1 |
| Новых разделов в основном файле | 2+1 перезапись | 9 | 6 | ~18 |
