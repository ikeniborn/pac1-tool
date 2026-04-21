---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Write a brief email to "priya@example.com" with subject "Project check-in" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/86300.json

STEP FACTS:
- read: /outbox/seq.json → {"id":86300}
- read: /outbox/81304.json → {   "subject": "Dinner confirmed",   "to": "sam@example.com",   "body": "Thursday works. See you at 19:00.",   "sent": t
- write: /outbox/86300.json → WRITTEN: /outbox/86300.json

EVALUATOR:
approved: true
steps: - composed email with subject Project check-in
- body Quick note
- to priya@example.com
- wrote to /outbox/86300.json
