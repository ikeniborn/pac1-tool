---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Write a brief email to "sam@example.com" with subject "Friday status" and body "Brief update."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/83504.json

STEP FACTS:
- read: /outbox/seq.json → {"id":83504}
- write: /outbox/83504.json → WRITTEN: /outbox/83504.json

EVALUATOR:
approved: true
steps: - read seq.json to get id=83504
- wrote /outbox/83504.json with email payload
