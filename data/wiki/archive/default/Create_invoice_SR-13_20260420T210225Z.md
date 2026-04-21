---
task_id: Create_invoice_SR-13
task_type: default
outcome: OUTCOME_OK
date: 2026-04-20
task: "Create invoice SR-13 with 2 lines: 'OpenAI Subscription' - 20, 'Claude Subscription' - 20"
---

DONE OPS:
- WRITTEN: /my-invoices/SR-13.json

STEP FACTS:
- read: /my-invoices/README.MD → Put things into files NUMBER.json  Use JSON like this:  ```json {   "number": "SR-13",   "account_id": "acct_001",   "is
- write: /my-invoices/SR-13.json → WRITTEN: /my-invoices/SR-13.json

EVALUATOR:
approved: true
steps: - created /my-invoices/SR-13.json with 2 lines
- total computed as 40 (20+20)
