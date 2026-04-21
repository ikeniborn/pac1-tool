---
task_id: What_is_the_exact_le
task_type: lookup
outcome: OUTCOME_OK
date: 2026-04-21
task: 'What is the exact legal name of the German Acme manufacturing account account? Answer with the exact legal name only.'
---

DONE OPS:
(none)

STEP FACTS:
- list: /accounts → acct_001.json, acct_002.json, acct_003.json, acct_004.json, acct_005.json, acct_006.json, acct_007.json, acct_008.json, acct_009.json, acct_010.json
- read: /accounts/acct_001.json → {"name": "Nordlicht Health", "account_manager": "Greta Engel", "status": "active", "industry": "healthcare"}
- read: /accounts/acct_002.json → {"name": "Acme Robotics", "account_manager": "Andreas Schmid", "status": "active", "industry": "manufacturing"}
