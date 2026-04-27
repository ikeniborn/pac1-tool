---
task_id: t32
task_type: crm
outcome: OUTCOME_OK
date: <date>
task: 'Northstar Forecasting asked to move the next follow-up to <date>. Fix the follow-up date regression and keep the diff focused. Audit context is in docs/follow-up-audit.json.'
---

DONE OPS:
- WRITTEN: /reminders/rem_010.json
- WRITTEN: /accounts/<file>

STEP FACTS:
- read: /accounts/<file> → {"name": "Northstar Forecasting", "account_manager": "Sandra Sauer", "status": "active", "industry": "professional_services"}
- search:  → reminders/rem_010.json:3
- read: /reminders/rem_010.json → {   "id": "rem_010",   "account_id": "<account>",   "contact_id": "<contact>",   "due_on": "<date>",   "title": "Follo
- write: /reminders/rem_010.json → WRITTEN: /reminders/rem_010.json
- write: /accounts/<file> → WRITTEN: /accounts/<file>

EVALUATOR:
approved: true
steps: - Read follow-up-audit.json → confirmed <account> / <date>
- Read <account>.json → next_follow_up_on was <date>
- Read rem_010.json → due_on was <date>
- Updated rem_010.json due_on → <date>
- Updated <account>.json next_follow_up_on → <date>
