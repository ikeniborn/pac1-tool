---
wiki_sources:
  - docs/architecture/06-evaluator.md
wiki_updated: 2026-05-05
wiki_status: stub
tags: [architecture, evaluator, dspy, verbatim-gate, wiki-injection]
---

# Evaluator

Критический gate перед `vm.answer()`: ревью предложенного исхода на соответствие задаче.

## EvaluateCompletion signature

```
Input:
  proposed_outcome    : OUTCOME_OK | OUTCOME_DENIED_SECURITY | ...
  done_operations     : ['WRITTEN: /outbox/5.json', ...]
  task_text           : оригинальный текст
  skepticism_level    : low | mid | high
  reference_patterns  : wiki page content (advisory)
  graph_insights      : top-K graph nodes (advisory)
  account_evidence    : INBOX/entity evidence (hardcoded gate)
  inbox_evidence      : inbox-specific evidence

Output (ChainOfThought):
  reasoning, approved, issues, correction_hint
```

## Verbatim gate (hard, pre-LLM)

Проверяет exact match quoted strings с trailing punctuation из task_text в done_operations. Пример: если задача содержит `"Quick note."` — агент должен записать именно с точкой. LLM-критик часто дропает punctuation → жёсткий regex-gate.

## Fail-open политика

- `EVALUATOR_ENABLED=0` → auto-approve
- Любая ошибка DSPy/LLM → auto-approve + log error
- `max_rejections` исчерпан → force approve (default EVAL_MAX_REJECTIONS=2)

## Rejection loop

```
report_completion #1 → evaluate → reject + hint → инжект в log
report_completion #2 → evaluate → reject → check rejections
  если ≥ EVAL_MAX_REJECTIONS → force approve submit
```

## Wiki + Graph injection (FIX-367)

Два advisory InputField:
- **`reference_patterns`**: `data/wiki/pages/<task_type>.md` — char limit масштабируется по quality (nascent=500, developing=2000, mature=4000)
- **`graph_insights`**: top-K из `wiki_graph.retrieve_relevant()` (требует `WIKI_GRAPH_ENABLED=1`)

Advisory: при конфликте с hardcoded INBOX/ENTITY правилами — hardcoded wins. При любом сбое → пустая строка.

## Skepticism levels

| Уровень | Поведение |
|---|---|
| `low` | approve unless obvious contradiction |
| `mid` | verify outcome vs evidence |
| `high` | assume mistake, search errors actively |

## Per-task-type evaluator

Fallback-цепочка: `evaluator_<task_type>_program.json` → `evaluator_program.json` → bare signature.

## Конфигурация

```bash
EVALUATOR_ENABLED=1
EVAL_SKEPTICISM=mid            # low|mid|high
EVAL_MAX_REJECTIONS=2
MODEL_EVALUATOR=...
EVALUATOR_WIKI_ENABLED=1
EVALUATOR_WIKI_MAX_CHARS_NASCENT=500
EVALUATOR_WIKI_MAX_CHARS_DEVELOPING=2000
EVALUATOR_WIKI_MAX_CHARS_MATURE=4000
EVALUATOR_GRAPH_TOP_K=5
```
