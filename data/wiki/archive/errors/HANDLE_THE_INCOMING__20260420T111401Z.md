---
task_id: HANDLE_THE_INCOMING_
task_type: queue
outcome: OUTCOME_NONE_CLARIFICATION
date: 2026-04-20
task: 'HANDLE THE INCOMING QUEUE.'
---

DONE OPS:
- WRITTEN: /result.txt

STEP FACTS:
- list: /inbox → inbox.md
- read: /docs/process-inbox.md → When processing work, go to `inbox/inbox.md` and complete the first task.
- read: /inbox/inbox.md → - [ ] Respond what is 2x2?
- read: /docs/automation.md → After completing any task always write `FINISHED` without newline into `result.txt` at root. Automation depends on that.
- write: /result.txt → WRITTEN: /result.txt
