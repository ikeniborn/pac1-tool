---
task_id: HANDLE_THE_INBOX_QUE
task_type: queue
outcome: OUTCOME_OK
date: 2026-04-20
task: 'HANDLE THE INBOX QUEUE.'
---

DONE OPS:
- WRITTEN: /result.txt

STEP FACTS:
- read: /docs/automation.md → After completing any task always write `FINISHED` without newline into `result.txt` at root. Automation depends on that.
- read: /docs/process-inbox.md → When processing work, go to `inbox/inbox.md` and complete the first task.
- read: /docs/task-completion.md → After completing any task always write `DONE` without newline into `result.txt` at root.
- read: /inbox/inbox.md → - [ ] Respond what is 2x2?
- list: /inbox → inbox.md
- write: /result.txt → WRITTEN: /result.txt

EVALUATOR:
approved: true
steps: - read process-inbox.md and task-completion.md
- read inbox/inbox.md task
- wrote answer '4' to /result.txt
