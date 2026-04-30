<!-- wiki:meta
category: crm
quality: nascent
fragment_count: 1
fragment_ids: [t32_20260430T140120Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Rescheduling follow-up date with cross-file consistency**: When CanalPort Shipping requested moving the follow-up from <date> to <date>, the proven sequence was:
  1. Read audit context in `docs/follow-up-audit.json` to confirm the account and requested date
  2. Search reminders/ to locate the linked reminder file
  3. Read the reminder file (`rem_007.json`) to confirm current `due_on` value
  4. Read the account file (`<account>.json`) to confirm current `next_follow_up_on` value
  5. Write updated `due_on` to reminder file
  6. Write updated `next_follow_up_on` to account file
  7. Re-read both files to verify changes applied correctly
- **Rule**: Always read both reminder and account files before writing either one when rescheduling a follow-up — this prevents data divergence and confirms the linked relationship exists before modification.
- **Scope discipline**: The audit context (`cleanup_later: true`) confirms that only the reminder was patched in this step; the account file update is part of the same rescheduling operation, not a separate concern.

## Key pitfalls
**Risk: Dropped Fields on Write**

When updating files like `/reminders/rem_007.json` and `/accounts/<file> the agent must preserve all existing fields that are not explicitly being changed. The `WRITE` operation must be a complete file replacement, not a partial patch. For example, when changing `due_on` from `"<date>"` to `"<date>"` in rem_007.json, the entire object—including `id`, `account_id`, `contact_id`, `title`, `kind`, `status`, `priority`, and `description`—must be rewritten without omission. If the agent reconstructs the file from only the fields it knows about, untracked fields (such as future-added metadata or extended attributes) will be silently dropped on every write.

**Risk: Wrong Field Mutation**

The agent must update only the fields that are relevant to the current task, avoiding collateral updates to related but unintended fields. In the CanalPort Shipping task (t32), the audit context in `docs/follow-up-audit.json` specified `"candidate_patch": "reminder_only"`, indicating the fix should be focused on the reminder file. However, the step logs show both `reminders/rem_007.json` (the `due_on` field) and `accounts/<account>.json` (the `next_follow_up_on` field) were updated. This dual-file update was arguably correct since the follow-up date exists in both places, but the risk is that the agent might mutate unrelated fields in the account file (e.g., `account_manager`, `tier`, `notes`) when only the date was intended to change. The agent should verify it only modifies fields that are (a) explicitly specified by the task or (b) necessary to maintain referential consistency for the same logical value across files—and nothing else.

**Risk: Account Manager Overwrite on Reschedule**

When rescheduling follow-up tasks (e.g., changing `due_on` or `next_follow_up_on`), the agent must not alter the `account_manager` field or any other ownership/assignment metadata. In the current task, `<account>.json` contains `"account_manager": "Lukas Müller"`, and this field must remain untouched when the follow-up date is updated. The reschedule operation is a date change, not a reassignment. If the agent performs a full object reconstruction without explicit field exclusion, it may inadvertently overwrite `account_manager` with a default, null, or stale value. The agent should treat `account_manager` as a protected field that is never modified by follow-up reschedule operations unless the task explicitly includes a reassignment directive.

## Shortcuts
**Field Preservation — Read Full Record First**

Before modifying any CRM record, read the entire file in full. CRM payloads carry related fields and cross-references (e.g., `account_id`, `contact_id`, `next_follow_up_on`) that must stay intact. A partial write risks dropping fields.

- Read `/reminders/rem_007.json` → confirmed `due_on`, `kind`, `status`, `priority`, `description` all present
- Read `/accounts/<file> → confirmed `next_follow_up_on` exists as a linked date field
- Only then write the updated record back

**Date Arithmetic — Sync Across Related Records**

When a date changes on a reminder, the matching `next_follow_up_on` field on the parent account record must be updated too. Treat date shifts as compound updates, not isolated edits.

- Task requested follow-up moved to `<date>`
- Updated `reminders/rem_007.json` → `"due_on": "<date>"`
- Updated `accounts/<account>.json` → `"next_follow_up_on": "<date>"`
- Both records now aligned; diff remained minimal

**Reconnect Logic — Re-read After Write**

CRM operations require a verification read immediately after a write to confirm the change persisted and no corruption occurred.

- Re-read `/reminders/rem_007.json` → `due_on` confirmed as `"<date>"`
- Re-read `/accounts/<file> → `next_follow_up_on` confirmed as `"<date>"`
- Only after both reads return correct values is the task considered complete

## Successful pattern: t32 (2026-04-30)
<!-- researcher: t32:fb0bc84771a9 -->

**Goal shape:** CanalPort Shipping asked to move the next follow-up to <date>. Fix the follow-up date regression

**Final answer:** CanalPort Shipping follow-up rescheduled to <date>. Updated due_on in rem_007.json and next_follow_up_on in <account>.json. Diff focused on date fields only; all other fields preserved. Note: The e

**Trajectory:**
1. search
2. read(/reminders/rem_007.json)
3. read(/accounts/<file>)
4. write(/reminders/rem_007.json)
5. write(/accounts/<file>)
6. read(/reminders/rem_007.json)
7. read(/accounts/<file>)
8. read(/docs/follow-up-audit.json)
9. read(/accounts/<file>)

**Key insights:**
- (none)

**Applies when:** crm
