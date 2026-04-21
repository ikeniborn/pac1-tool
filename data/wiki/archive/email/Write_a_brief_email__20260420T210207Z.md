---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Write a brief email to "alex@example.com" with subject "Quick update" and body "Thanks."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/83444.json

STEP FACTS:
- read: /outbox/seq.json → {"id":83444}
- write: /outbox/83444.json → WRITTEN: /outbox/83444.json

EVALUATOR:
approved: true
steps: - read seq.json
- write email to /outbox/83444.json
- seq auto-updated to 83445
