---
task_id: Write_a_brief_email_
task_type: email
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Write a brief email to "maya@example.com" with subject "Friday status" and body "Quick note."'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/88135.json

STEP FACTS:
- read: /outbox/seq.json → {"id":88135}
- read: /outbox/README.MD → Put outgoing emails into files NUMBER.json.  ALWAYS get the next number from `seq.json`. For example, if `seq.json` is: 
- write: /outbox/88135.json → WRITTEN: /outbox/88135.json

EVALUATOR:
approved: true
steps: - wrote email to maya@example.com with subject Friday status
