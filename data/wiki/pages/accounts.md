⚠️ **Do NOT Mutate Fields the Task Didn't Name**
Only write fields explicitly specified by the current task. Never infer, copy, or "correct" other fields — even if they look stale or inconsistent across reads.

---

## Read-Before-Write Pattern

Proven sequence for update tasks:

1. **Read** the target file to load current state.
2. **Diff** the current state against the task's required changes — identify only the named fields.
3. **Write** the file with only the named fields changed; all other fields pass through verbatim.
4. **Verify** the written file matches the expected post-state.

> Outcome: tasks following this sequence consistently resolve with `OUTCOME_OK`.

---

## Multi-Record Read Pattern

For tasks requiring reads across several accounts before any write:

1. **Read all** target files first, in sequence, before performing any writes.
2. **Aggregate** only the values relevant to the task (e.g., filtering by a shared field value).
3. **Act** (write / report) only after the full read pass is complete.

> Rationale: avoids partial-state decisions; ensures the action is based on a consistent snapshot.

---

## Key Risks and Pitfalls

### Stale Read / Concurrent Modification
- A field value read at time T may differ from the value at time T+1. Same-file, same-day reads have been observed returning different field values across separate tasks — confirming that intra-day divergence is a real, not merely theoretical, risk. Example pattern: the same file read in one task returned one manager value; a later same-day task read it and returned a different manager value.
- **Mitigation:** Read immediately before writing. Do not cache reads across task boundaries. If two sequential reads of the same file return different values, treat the data as volatile and do not write until the task scope is confirmed.

### Silent Field Overwrite
- Writing a record fetched for one field update may inadvertently overwrite other fields if the write payload is reconstructed from the read rather than patched.
- **Mitigation:** Treat the read payload as a base; apply only the task-named delta; write the merged object.

### Manager-Assignment Confusion on Reschedule Tasks
- Reschedule or reassignment tasks may tempt the agent to update account manager as a side effect. This breaks field-diff checks.
- **Mitigation:** Unless the manager field is explicitly named in the task, never modify it — even if it appears inconsistent with other records or diverges across reads.

### Read-Only Task Misclassified as Write
- A task that only needs to report or aggregate data does not require a write step.
- **Mitigation:** Confirm a write is in scope before issuing any write call.

### Diverging Reads Across Task Boundaries (Reinforced)
- Multiple same-day tasks reading the same file have returned different values for fields such as manager assignments, with no intervening write visible in the task log. This is direct evidence that file state can change between task executions within the same day.
- **Mitigation:** Never assume a value read in a prior task is still current. Always re-read at the start of a new task touching the same file.

---

## Task-Type Shortcuts

### Status-Update Tasks
- Only field required: `status`. Read → patch status → write. No other field should change.

### Portfolio / Manager-Coverage Tasks
- Pattern: read N records, filter by a shared field, return the matching set. No write needed unless explicitly stated.
- Read-only tasks producing a filtered result set require zero write calls — confirm no write is issued.

### Single-Field Rename Tasks
- Read → change exactly one field → write. Diff the output to confirm only one field changed before committing.

### Read-Only Lookup Tasks
- Some tasks require only one or two reads with no write. Treat absence of a write step as correct, not as an incomplete task.

---
