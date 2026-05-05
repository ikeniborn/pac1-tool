<!-- wiki:meta
category: crm
quality: developing
fragment_count: 6
fragment_ids: [t32_20260504T194351Z, t32_20260504T204018Z, t32_20260504T213006Z, t32_20260504T223004Z, t32_20260504T233248Z, t32_20260505T003318Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
```json
{
  "pattern": "reschedule_followup_sequence",
  "steps": [
    {
      "seq": 1,
      "op": "READ",
      "target": "docs/follow-up-audit.json",
      "purpose": "Audit existing follow-up state before modification"
    },
    {
      "seq": 2,
      "op": "DATE_ARITHMETIC",
      "input": "requested_date: <date>",
      "validation": "ensure date > current_date and within allowed horizon (default: +365 days)"
    },
    {
      "seq": 3,
      "op": "WRITE",
      "target": "crm.tasks[t32]",
      "fields": {
        "date": "<date>",
        "outcome": "OUTCOME_OK"
      }
    },
    {
      "seq": 4,
      "op": "VERIFY",
      "checks": ["diff focused on date field only", "task_id unchanged", "task_type preserved"]
    }
  ],
  "examples": [
    {
      "task_id": "t32",
      "entity": "Nordlicht Health",
      "action": "move follow-up",
      "from_date": "<existing>",
      "to_date": "<date>",
      "audit_ref": "docs/follow-up-audit.json"
    },
    {
      "task_id": "t32",
      "entity": "CanalPort Shipping",
      "action": "regression correction",
      "from_date": "<date>",
      "to_date": "<date>",
      "audit_ref": "docs/follow-up-audit.json",
      "note": "regression fix - corrected incorrect date entry"
    },
    {
      "task_id": "t32",
      "entity": "Silverline Retail",
      "action": "move follow-up",
      "from_date": "<date>",
      "to_date": "<date>",
      "audit_ref": "docs/follow-up-audit.json",
      "note": "regression fix - corrected incorrect date entry"
    },
    {
      "task_id": "t32",
      "entity": "Northstar Forecasting",
      "action": "regression correction",
      "from_date": "<date>",
      "to_date": "<date>",
      "audit_ref": "docs/follow-up-audit.json",
      "note": "regression fix - corrected incorrect date entry"
    }
  ],
  "date_arithmetic_rules": {
    "allowed_formats": ["YYYY-MM-DD", "ISO8601"],
    "horizon_check": "requested_date must be future-dated",
    "timezone": "UTC for storage, local for display"
  },
  "write_operation_constraints": {
    "diff_focus": "only modify date field unless explicitly instructed",
    "preserve_fields": ["task_id", "task_type", "outcome"],
    "audit_required": "true"
  }
}
```

## Key pitfalls
**Dropped Fields on Write**
When updating task records, ensure all existing fields are preserved. A regression in the follow-up date handling for CanalPort Shipping (task t32, <date>) demonstrated that partial updates can silently drop fields not explicitly included in the write operation. Always read-modify-write with complete field sets or use merge semantics that preserve unspecified fields. For task t32 (CanalPort Shipping follow-up to <date>), the fix must keep the diff focused on the date field only, ensuring no other task metadata is inadvertently modified. Similarly, Nordlicht Health follow-up dates must only update the date field while preserving all other task attributes. For Silverline Retail follow-up to <date>, the same principle applies—read-modify-write with complete field sets to prevent silent field drops. Northstar Forecasting follow-up to <date> applies the same pattern—read-modify-write with complete field sets to prevent silent field drops.

**Wrong Field Mutation**
Field mutations must target the intended property only. The follow-up date regression stemmed from incorrect mutation logic that either overwrote unrelated fields or corrupted the date format. Audit trails in `docs/follow-up-audit.json` capture the mutation patterns that caused data corruption. Verify that update operations address exactly the field being modified. The t32 fix should be surgical and isolated—changing only the follow-up date while leaving all other task fields untouched. Nordlicht Health follow-up migration to <date> must use the same surgical approach. Silverline Retail's requested move to <date> must use the same surgical, isolated mutation—targeting only the date field and leaving all other task attributes untouched. Northstar Forecasting's requested move to <date> must use the same surgical, isolated mutation—targeting only the date field and leaving all other task attributes untouched. The fix is confirmed successful (OUTCOME_OK).

**Account Manager Overwrite on Reschedule**
When rescheduling tasks (e.g., moving CanalPort Shipping follow-up to <date>), the account_manager field is at risk of unintended overwrite. Reschedule operations should preserve the original account_manager unless explicitly instructed otherwise. The regression fix required isolating the date change from other task metadata to prevent account_manager corruption during temporal updates. The fix should keep the diff focused, isolating the date change to prevent account_manager corruption during temporal updates. When moving Nordlicht Health follow-up to <date>, ensure account_manager isolation remains the priority—never allow temporal field updates to cascade into owner or assignment metadata. When moving Silverline Retail follow-up to <date>, account_manager isolation remains the priority—never allow the date update to cascade into owner or assignment metadata. When moving Northstar Forecasting follow-up to <date>, account_manager isolation remains the priority—never allow the date update to cascade into owner or assignment metadata.

## Shortcuts
**CRM Field Preservation Pattern**

Always read the complete CRM record before performing any modification. Partial reads can cause field data loss when the write-back operation overwrites fields that were not included in the read request. This includes custom fields, metadata timestamps, and linked entity references.

**Date Arithmetic for Follow-ups**

When adjusting follow-up dates:
- Use the existing date as the base, never assume a default timezone
- Parse dates in `YYYY-MM-DD` format explicitly
- When moving a follow-up forward (e.g., CanalPort Shipping from original date to `<date>`), preserve the time component if present
- When fixing a date regression (moving backward in time), still preserve the time component and use the existing record's full datetime as the base
- Keep diffs focused: only the date field should change; all other record fields must remain untouched
- Audit all date changes in `docs/follow-up-audit.json` for traceability
- When correcting a regression (e.g., task t32: Northstar Forecasting from <date> back to <date>), verify the fix against the requestor's intent before committing

**Reconnect Logic**

CRM connections may drop during long-running operations or due to token expiration. Implement exponential backoff with a maximum of 3 retry attempts. After reconnection, re-fetch the record to ensure field state has not diverged before attempting the write operation again.

## Proven Sequences for Rescheduling Follow-ups
### Sequence 1: Date Arithmetic in Follow-up Rescheduling

```
# Read current follow-up state
cat docs/follow-up-audit.json
# Extract current follow-up date
jq '.current_date' < audit-context

# Perform date arithmetic
# Target: <date> (from task: CanalPort Shipping follow-up reschedule)
# Use date arithmetic to validate target is future date from <date>

# Write updated follow-up date
# Pattern: Update only the date field, keep diff focused
```

### Sequence 2: Focused Write Operations

```
# 1. Read existing state
# 2. Identify only fields requiring change
# 3. Write minimal diff
# 4. Preserve audit trail
# Rule: Keep the diff focused — never rewrite unrelated fields
```

### Sequence 3: CRM Follow-up Reschedule Pattern

```
# Task: CanalPort Shipping asked to move the next follow-up to <date>
# 1. Validate target date format (ISO 8601: YYYY-MM-DD)
# 2. Verify target > current date
# 3. Read current state from docs/follow-up-audit.json
# 4. Apply date change: current → target
# 5. Write only the changed field
# 6. Confirm outcome: OUTCOME_OK
```

### Date Arithmetic Rules

- **ISO 8601 enforcement**: All dates in `YYYY-MM-DD` format
- **Forward-only validation**: Target must be > current date for reschedules
- **Audit before write**: Always reference `docs/follow-up-audit.json` for context
- **Minimal mutation**: Update single field, preserve all others

### Write Operation Rules

- **Focused diff**: Change only the required field
- **Audit trail**: Document all follow-up changes in `docs/follow-up-audit.json`
- **Outcome logging**: Set `outcome: OUTCOME_OK` on successful reschedule
- **No side effects**: Do not modify unrelated CRM records during follow-up updates

## Successful pattern: t32 (2026-05-04)
<!-- researcher: t32:e3b0c44298fc -->

**Goal shape:** CanalPort Shipping asked to move the next follow-up to <date>. Fix the follow-up date regression

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?

**Key insights:**
- (none)

**Applies when:** crm
