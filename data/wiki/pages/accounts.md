> ⚠️ **Do NOT Mutate Fields the Task Didn't Name**
> Only write fields explicitly listed in the task specification. Do not infer, carry over, or "helpfully" update unrelated fields such as `account_manager`, `industry`, or `status` during reschedule or rename operations.

---

## Proven Step Sequences

### Read-Verify-Write (Single Account Update)
Applies to any task that modifies a JSON account file.

1. **Read** the target file → capture current state.
2. **Verify** that only the task-specified fields differ from current values.
3. **Write** the mutated file with exactly those fields changed — no others.
4. **Confirm** the write succeeded (check for `WRITTEN:` acknowledgement).

*OUTCOME_OK observed when this sequence is followed without deviation.*

### Read-Only Lookup (No Write Required)
When the task only needs to inspect or report a value:

1. **Read** the target file.
2. **Extract** the requested field(s).
3. **Return** the value — do not issue a write.

*Avoid writing back unchanged content; it creates false diffs and breaks field-diff checks.*

---

## Key Risks and Pitfalls

### Silent Field Mutation
**Risk:** During a write, fields not named by the task (e.g., `account_manager`, `industry`, `status`) are carried forward with altered values from stale cache or incorrect assumptions.
**Mitigation:** Always diff intended write payload against the last-read snapshot before committing. Reject writes that touch unnamed fields.

### Write Without Prior Read
**Risk:** Writing to a file without first reading it may overwrite concurrent changes or introduce stale data.
**Mitigation:** Every write task sequence must begin with a read of the same path.

### Read-Only Task Escalated to Write
**Risk:** A lookup task inadvertently triggers a write (e.g., "update view" interpreted as file mutation).
**Mitigation:** If the task verb is `get`, `find`, `list`, `check`, or `read`, issue no write calls.

### Multi-File Fan-Out Without Isolation
**Risk:** When reading multiple account files in one task, values from one file bleed into the write payload for another.
**Mitigation:** Treat each file's read result as a strictly scoped local variable; never merge field values across files.

---

## Task-Type Specific Insights

### Reschedule / Status-Change Tasks
- Only mutate the field(s) the task names (e.g., `status`).
- `account_manager` is **never** a side-effect of a reschedule — do not touch it.
- Re-read the file immediately before writing even if a prior read exists in the same session (state may have changed).

### Bulk Read Tasks (Multiple Accounts)
- Reading several files in sequence is safe and common for reporting.
- Maintain a per-file result map; do not aggregate into a single mutable object.
- If any single read fails, surface the error rather than proceeding with partial data.

### Write Confirmation
- A successful write is confirmed by a `WRITTEN: <path>` acknowledgement.
- Absence of this token means the write did not complete — do not assume success.

---
