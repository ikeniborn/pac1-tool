---
task_id: Nordlicht_Health_ask
task_type: crm
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Nordlicht Health asked to move the next follow-up to 2026-02-23. Fix the follow-up date regression and keep the diff focused. Audit context is in docs/follow-up-audit.json.'
---

DONE OPS:
- WRITTEN: /reminders/rem_001.json
- WRITTEN: /accounts/acct_001.json

STEP FACTS:
- read: /docs/follow-up-audit.json → {   "account_id": "acct_001",   "account_name": "Nordlicht Health",   "candidate_patch": "reminder_only",   "cleanup_lat
- read: /reminders/rem_001.json → {   "id": "rem_001",   "account_id": "acct_001",   "contact_id": "cont_001",   "due_on": "2026-02-05",   "title": "Follo
- write: /reminders/rem_001.json → WRITTEN: /reminders/rem_001.json
- read: /accounts/acct_001.json → {"name": "Nordlicht Health", "account_manager": "Julia Wolf", "status": "active", "industry": "healthcare"}
- write: /accounts/acct_001.json → WRITTEN: /accounts/acct_001.json
- read: /accounts/acct_001.json → {"name": "Nordlicht Health", "account_manager": "Julia Wolf", "status": "active", "industry": "healthcare"}
