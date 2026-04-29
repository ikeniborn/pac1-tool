## FIX-344: Preserve All Fields on Write

**⚠️ Banner: Always read the existing file before writing. Reschedule and audit failures are caused by the model generating a stripped-down JSON from memory and dropping fields like `contact_id`, `priority`, `region`. Preserve all fields.**

**5-Step Checklist:**

1. **Read** the existing file before writing — never generate JSON from memory.
2. **Modify** only the required fields (e.g., `due_on`, `next_follow_up_on`) — leave all other fields intact.
3. **Write** the complete file back — include every field that was in the original.
4. **Verify** the written state by reading the file again and confirming all fields are present.
5. **Cross-check** against `/docs/follow-up-audit.json` — confirm `account_id` and `requested_due_on` match the expected final state.

---

## Successful Pattern: t32 — Follow-up Date Regression Fix (crm)

**Goal shape:** Move the next follow-up date to a specific date. Fix the follow-up date regression and keep the diff focused.

**Final answer:** Follow-up regression fixed. Evidence: (1) Audit `/docs/follow-up-audit.json` confirms `account_id` and `requested_due_on`. (2) Search showed both `/accounts/<file> and `/reminders/<file>` had stale dates.

**Trajectory:**

1. `search` — locate the account file by entity name
2. `read(/accounts/<file>)` — confirm current stale date
3. `search` — locate the reminder file for same entity
4. `read(/reminders/<file>)` — confirm reminder also has stale date
5. `write(/accounts/<file>)` — update `next_follow_up_on` to target date
6. `write(/reminders/<file>)` — update `due_on` to target date (same entity, same date)
7. `read(/docs/follow-up-audit.json)` — audit expected final state
8. `read(/accounts/<file>)` — verify account write
9. `read(/reminders/<file>)` — verify reminder write

**Key insights:**

- Date regression on follow-ups always involves **two files**: the account record and the reminder record. Both must be updated together or one will show the old date.
- The audit file `/docs/follow-up-audit.json` provides `account_id` and `requested_due_on` — read it first to know what to verify against, not to drive the write.
- `candidate_patch: "reminder_only"` signals that the minimal correct fix updates the reminder too. Trust the audit file's intent.
- Always verify **both** written files end-state; a single read of one confirms only one half of the regression is fixed.

**Applies when:** crm

---

## Proven Step Sequences

| # | Steps | When used |
|---|-------|-----------|
| 1 | `search` → `read(account)` → `search` → `read(reminder)` → `write(account)` → `write(reminder)` → `read(audit)` → `read(account)` → `read(reminder)` | Follow-up date regression: entity has both account record and reminder record that must stay in sync. |

---

## Key Risks and Pitfalls

- **Stale-date regression:** Updating only one of the two files leaves the other showing the old date. Always locate and update both.
- **Stripped JSON on reschedule:** Generating a new JSON from memory drops fields like `contact_id`, `priority`, `region`. Always read the existing file before writing and preserve all fields.
- **Audit failure:** Rescheduling without verifying against the audit file can leave the system in an inconsistent state. Read the audit file post-write and confirm `account_id` and `requested_due_on` match.

---

## Task-Type Specific Insights (crm)

- **Follow-up date changes require dual writes** — both `/accounts/<file> (field: `next_follow_up_on`) and `/reminders/<file>` (field: `due_on`) must be updated to the same date.
- **Use the audit file as verification target** — it contains `account_id` and `requested_due_on`; compare final state against these fields rather than using it to drive the write operation.
- **`candidate_patch: "reminder_only"`** in the audit file indicates the reminder should also be updated. Treat it as a signal to update both files, not a reason to update only one.
- **Keep the diff focused** — change only the date fields. All other fields (contact_id, priority, region, status, etc.) must remain intact.

---

## Antipatterns

- Writing a JSON from memory instead of reading and modifying the existing file — causes field loss.
- Updating only the account record and skipping the reminder — leaves stale data in the reminder queue.
- Treating the audit file as the source of truth for what to write — it is a verification target, not a template.

---

## Successful pattern: t32 (<date>)
<!-- researcher: t32:d90db4cdda14 -->

**Goal shape:** Move the next follow-up to a specific date. Fix the follow-up date regression and keep the diff focused.

**Final answer:** Follow-up regression fixed. Both `/accounts/<file> and `/reminders/<file>` now show the target date. All other fields preserved.

**Trajectory:**
1. `read(/docs/follow-up-audit.json)` — read audit context first
2. `read(/accounts/<file>)` — confirm current stale date (e.g., <date>)
3. `search` — locate reminder file by account reference
4. `read(/reminders/<file>)` — confirm reminder also has stale date (e.g., <date>)
5. `write(/accounts/<file>)` — update `next_follow_up_on` to target date (e.g., <date>)
6. `write(/reminders/<file>)` — update `due_on` to target date (e.g., <date>)
7. `read(/accounts/<file>)` — verify account write
8. `read(/reminders/<file>)` — verify reminder write
9. `read(/docs/follow-up-audit.json)` — cross-check final state matches audit

**Key insights:**
- Audit file confirms `candidate_patch: "reminder_only"` — signals both files need updating
- All fields preserved across both writes — no field loss

**Applies when:** crm
