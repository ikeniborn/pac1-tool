---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Write a brief email to "maya@example.com" with subject "Project check-in" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/82293.json

STEP FACTS:
- read: /outbox/seq.json → {"id":82293}
- write: /outbox/82293.json → WRITTEN: /outbox/82293.json

EVALUATOR:
approved: true
steps: - wrote email JSON to /outbox/82293.json
