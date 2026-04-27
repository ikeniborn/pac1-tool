## Incomplete Secondary Artifact Writes

- **Condition:** Agent completes capture and card writes but omits the thread-append and changelog writes, producing only 2 of 4 expected DONE OPS.
- **Root cause:** Write steps for secondary artifacts (thread file, `agent_changelog.md`) are not executed even though the corresponding read ops succeed, likely because the agent treats the reads as sufficient confirmation of context and exits before committing updates.
- **Solution:** After every capture task, assert that DONE OPS contains an explicit write entry for every file that was read with intent to update. If any secondary write is absent, retry only the missing write steps before closing the task.

---

## Evaluator Credits Phantom Writes

- **Condition:** Evaluator marks a task `approved: true` and lists thread-append and changelog operations in its `steps` summary, but those operations are absent from both DONE OPS and STEP FACTS write entries.
- **Root cause:** Evaluator validates stated intent or the presence of read ops rather than confirmed write ops, causing false positives when secondary writes are silently skipped.
- **Solution:** Treat evaluator approval as a necessary but not sufficient signal. Cross-reference every operation credited in the evaluator `steps` list against DONE OPS. Flag any credited write that has no corresponding DONE OPS entry and surface it for manual review or automated retry.

---

## DONE OPS / STEP FACTS Write-Count Mismatch

- **Condition:** The number of write entries in STEP FACTS does not match the number of WRITTEN lines in DONE OPS for the same task execution.
- **Root cause:** DONE OPS is populated at task close while STEP FACTS records real-time tool calls; a write tool call that is invoked but fails silently can appear in STEP FACTS while being absent from DONE OPS, or vice-versa.
- **Solution:** After task completion, diff STEP FACTS write paths against DONE OPS paths. Any path present in one list but absent from the other indicates a silent failure or a premature task-close and must be reconciled before the task is marked complete.

---
