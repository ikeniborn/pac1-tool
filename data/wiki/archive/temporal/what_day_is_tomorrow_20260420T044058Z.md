---
task_id: what_day_is_tomorrow
task_type: temporal
outcome: OUTCOME_OK
date: 2026-04-20
task: 'what day is tomorrow? Respond with DD-MM-YYYY only'
---

DONE OPS:
(none)

STEP FACTS:
(none)

EVALUATOR:
approved: true
steps: - identified VAULT_DATE from context as 2026-04-19
- computed tomorrow as 20-04-2026
