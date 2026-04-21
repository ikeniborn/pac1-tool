---
task_id: What_is_the_email_of
task_type: lookup
outcome: OUTCOME_OK
date: 2026-04-21
task: 'What is the email of the primary contact for the Berlin digital-health buyer focused on triage backlog account? Return only the email.'
---

DONE OPS:
(none)

STEP FACTS:
- list: /accounts → acct_001.json, acct_002.json, acct_003.json, acct_004.json, acct_005.json, acct_006.json, acct_007.json, acct_008.json, acct_009.json, acct_010.json
- read: /accounts/acct_001.json → {"name": "Nordlicht Health", "account_manager": "Nils Kramer", "status": "active", "industry": "healthcare"}
- read: /contacts/cont_001.json → {   "id": "cont_001",   "account_id": "acct_001",   "full_name": "Carsten Voigt",   "role": "Operations Director",   "em
