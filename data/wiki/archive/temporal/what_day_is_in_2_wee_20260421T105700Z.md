---
task_id: what_day_is_in_2_wee
task_type: temporal
outcome: OUTCOME_OK
date: 2026-04-21
task: 'what day is in 2 weeks? Respond with DD-MM-YYYY only'
---

DONE OPS:
(none)

STEP FACTS:
- read: /inbox/README.md → Incoming messages land here.  There is no fixed schema for `inbox/`.  When asked to `process inbox`:  - handle exactly one pending `msg_*.txt` item at a time - start with the lowest filename and leave later messages untouched until that item is resolved  Before acting on inbox material, read all relevant to inbox files in: [docs](../docs).
- read: /accounts/acct_001.json → {"name": "Nordlicht Health", "account_manager": "Svenja Adler", "status": "active", "industry": "healthcare"}

EVALUATOR:
approved: true
steps: - Verified vault date 2026-03-23
- Added 14 days
- Formatted as DD-MM-YYYY
