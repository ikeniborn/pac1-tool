---
task_id: email_to_blue_harbor
date: 2026-04-20
---

- read: /contacts/cont_004.json → {   "id": "cont_004",   "account_id": "acct_004",   "full_name": "Martijn Post",   "role": "QA Lead",   "email": "martij
- read: /contacts/mgr_004.json → ERROR NOT_FOUND
- read: /contacts/mgr_004.json → ERROR Code.NOT_FOUND: file not found [read] Check path '/contacts/mgr_004.json' 
