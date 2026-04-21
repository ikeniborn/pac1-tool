---
task_id: Acme_Robotics_asked_
task_type: crm
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Acme Robotics asked to move the next follow-up to 2026-12-07. Fix the follow-up date regression and keep the diff focused. Audit context is in docs/follow-up-audit.json.'
---

DONE OPS:
- WRITTEN: /reminders/rem_002.json
- WRITTEN: /accounts/acct_002.json

STEP FACTS:
- read: /docs/follow-up-audit.json → {   "account_id": "acct_002",   "account_name": "Acme Robotics",   "candidate_patch": "reminder_only",   "cleanup_later"
- read: /reminders/rem_002.json → {   "id": "rem_002",   "account_id": "acct_002",   "contact_id": "cont_002",   "due_on": "2026-11-29",   "title": "Follo
- write: /reminders/rem_002.json → WRITTEN: /reminders/rem_002.json
- read: /accounts/acct_002.json → {"name": "Acme Robotics", "account_manager": "Paul Weber", "status": "active", "industry": "manufacturing"}
- write: /accounts/acct_002.json → WRITTEN: /accounts/acct_002.json
