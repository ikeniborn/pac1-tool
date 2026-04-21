---
task_id: What_is_the_email_ad
task_type: lookup
outcome: OUTCOME_OK
date: 2026-04-20
task: 'What is the email address of the account manager for the German tax advisory account Helios account? Return only the email.'
---

DONE OPS:
(none)

STEP FACTS:
- search:  → accounts/acct_008.json:3, accounts/acct_008.json:4
- read: /accounts/acct_008.json → {"name": "Helios Tax Group", "account_manager": "Frederike Blom", "status": "active", "industry": "professional_services"}
- search:  → contacts/mgr_002.json:4
- read: /contacts/mgr_002.json → {   "id": "mgr_002",   "account_id": "acct_002",   "full_name": "Frederike Blom",   "role": "Account Manager",   "email"
