---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Write a brief email to "maya@example.com" with subject "Quick update" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/88894.json

STEP FACTS:
- read: /outbox/seq.json → {"id":88894}
- write: /outbox/88894.json → WRITTEN: /outbox/88894.json

EVALUATOR:
approved: true
steps: - read seq.json to get id=88894
- wrote email to /outbox/88894.json
- seq.json auto-updated to 88895
