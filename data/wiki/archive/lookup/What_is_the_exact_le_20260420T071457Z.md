---
task_id: What_is_the_exact_le
task_type: lookup
outcome: OUTCOME_OK
date: 2026-04-20
task: 'What is the exact legal name of the German tax advisory account Helios account? Answer with the exact legal name only.'
---

DONE OPS:
(none)

STEP FACTS:
- search:  → 01_notes/helios-tax-group.md:1, 01_notes/helios-tax-group.md:5, 01_notes/helios-tax-group.md:17, 01_notes/helios-tax-group.md:18, 01_notes/nordlicht-health.md:18, accounts/acct_008.json:3, accounts/acct_008.json:4, opportunities/opp_008.json:4, reminders/rem_008.json:6
- read: /accounts/acct_008.json → {"name": "Helios Tax Group", "account_manager": "Marcel Bergmann", "status": "active", "industry": "professional_services"}
