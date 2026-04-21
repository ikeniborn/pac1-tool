---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Write a brief email to "sam@example.com" with subject "Quick update" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/83566.json

STEP FACTS:
- read: /outbox/seq.json → {"id":83566}
- write: /outbox/83566.json → WRITTEN: /outbox/83566.json
- reporttaskcompletion: ? → ERROR EXCEPTION

EVALUATOR:
approved: true
steps: - read seq.json
- write /outbox/83566.json
- seq.json auto-updated to 83567
