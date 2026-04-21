---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Write a brief email to "priya@example.com" with subject "Friday status" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/88344.json

STEP FACTS:
- read: /outbox/seq.json → {"id":88344}
- write: /outbox/88344.json → WRITTEN: /outbox/88344.json

EVALUATOR:
approved: true
steps: - wrote email to priya@example.com with subject Friday status
