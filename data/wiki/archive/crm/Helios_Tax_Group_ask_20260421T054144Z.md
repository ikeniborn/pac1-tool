---
task_id: Helios_Tax_Group_ask
task_type: crm
outcome: OUTCOME_OK
date: 2026-04-21
task: 'Helios Tax Group asked to move the next follow-up to 2026-07-11. Fix the follow-up date regression and keep the diff focused. Audit context is in docs/follow-up-audit.json.'
---

DONE OPS:
- WRITTEN: /reminders/rem_008.json
- WRITTEN: /accounts/acct_008.json

STEP FACTS:
- read: /reminders/rem_008.json → {   "id": "rem_008",   "account_id": "acct_008",   "contact_id": "cont_008",   "due_on": "2026-07-18",   "title": "Follo
- write: /reminders/rem_008.json → WRITTEN: /reminders/rem_008.json
- read: /accounts/acct_008.json → {"name": "Helios Tax Group", "account_manager": "Carsten Voigt", "status": "active", "industry": "professional_services"}
- write: /accounts/acct_008.json → WRITTEN: /accounts/acct_008.json
