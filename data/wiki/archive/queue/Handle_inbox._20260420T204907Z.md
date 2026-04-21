---
task_id: Handle_inbox.
task_type: queue
outcome: OUTCOME_OK
date: 2026-04-20
task: 'Handle inbox.'
---

DONE OPS:
- WRITTEN: /outbox/seq.json
- WRITTEN: /outbox/84024.json

STEP FACTS:
- read: /inbox/README.md → Incoming messages land here.  There is no fixed schema for `inbox/`.  When asked to `process inbox`:  - handle exactly one pending `msg_*.txt` item at a time - start with the lowest filename and leave later messages untouched until that item is resolved  Before acting on inbox material, read all relevant to inbox files in: [docs](../docs).
- read: /inbox/msg_001.txt → From: Isabel Herzog <accounts-payable@nordlicht-health.biz> Subject: Invoice copy request  Hi,  Can you resend the latest invoice for Nordlicht Health? Please send it over today if possible.  Thanks, Isabel Herzog
- read: /docs/inbox-task-processing.md → # Inbox task processing  Use this note when handling incoming requests from `inbox/`.  ## General  - Treat `inbox/` as i
- search:  → contacts/mgr_001.json:4
- read: /contacts/mgr_001.json → {   "id": "mgr_001",   "account_id": "acct_001",   "full_name": "Isabel Herzog",   "role": "Account Manager",   "email":
- search:  → accounts/acct_001.json:11, accounts/acct_004.json:11, accounts/acct_007.json:11, accounts/acct_010.json:11
- stall:  → You have taken 6 steps without writing, deleting, moving, or creating anything. Read: ['/inbox/msg_0
- search:  → accounts/acct_001.json:14
- search:  → my-invoices/INV-001-01.json:3, my-invoices/INV-001-02.json:3, my-invoices/INV-001-03.json:3, my-invoices/INV-001-04.json:3, my-invoices/README.MD:8
- read: /my-invoices/INV-001-04.json → {   "number": "INV-001-04",   "account_id": "acct_001",   "issued_on": "2026-03-29",   "lines": [     {       "name": "P
- read: /outbox/seq.json → {   "id": 84024 }
- write: /outbox/84024.json → WRITTEN: /outbox/84024.json

EVALUATOR:
approved: true
steps: - processed msg_001.txt email request
- found Isabel Herzog contact
- identified Nordlicht Health account as acct_001
- found latest invoice INV-001-04 (issued 2026-03-29)
- wrote email response to /outbox/84024.json with attachment

STALL HINTS:
- You have taken 6 steps without writing, deleting, moving, or creating anything. Read: ['/inbox/msg_0
