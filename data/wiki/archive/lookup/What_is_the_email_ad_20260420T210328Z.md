---
task_id: What_is_the_email_ad
task_type: lookup
outcome: OUTCOME_OK
date: 2026-04-20
task: 'What is the email address of Neumann Sebastian? Return only the email'
---

DONE OPS:
(none)

STEP FACTS:
- search:  → (no matches)
- search:  → contacts/mgr_002.json:4, contacts/mgr_003.json:4
- read: /contacts/mgr_002.json → {   "id": "mgr_002",   "account_id": "acct_002",   "full_name": "Sarah Neumann",   "role": "Account Manager",   "email":
- search:  → contacts/mgr_003.json:4
- read: /contacts/mgr_003.json → {   "id": "mgr_003",   "account_id": "acct_003",   "full_name": "Sebastian Neumann",   "role": "Account Manager",   "ema
