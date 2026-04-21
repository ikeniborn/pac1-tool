---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Write a brief email to "alex@example.com" with subject "Lunch tomorrow" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/87979.json

STEP FACTS:
- read: /outbox/seq.json → {"id":87979}
- write: /outbox/87979.json → WRITTEN: /outbox/87979.json

EVALUATOR:
approved: true
steps: - read seq.json
- write email to alex@example.com
