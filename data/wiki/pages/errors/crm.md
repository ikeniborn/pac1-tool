<!-- wiki:meta
category: errors/crm
quality: developing
fragment_count: 5
fragment_ids: [t13_20260504T105418Z, t13_20260504T114756Z, t13_20260504T120343Z, t13_20260504T121541Z, t13_20260504T123311Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
When rescheduling CRM follow-ups:

- Always calculate the new date explicitly rather than relying on natural language ("two weeks" should resolve to a specific date)
- Verify the system supports write operations on the target entity before attempting updates
- Sequence: (1) parse relative date → (2) validate entity exists → (3) execute write → (4) confirm outcome
- If OUTCOME_NONE_UNSUPPORTED occurs, the operation itself may be unsupported — check task_type capabilities before scheduling the operation
- For "keep the diff focused", only write the changed fields, not the full record
- If OUTCOME_NONE_CLARIFICATION occurs mid-sequence, halt and surface the ambiguity to the user rather than guessing — clarification should be requested before any write operation is attempted
- When rescheduling requires interpreting relative dates like "two weeks", confirm the calculated date aligns with user intent if there is any ambiguity in the original phrasing
- Successful execution of the full sequence (relative date arithmetic → entity validation → write operation) produces OUTCOME_OK with the calculated date recorded (e.g., "two weeks" resolving to <date>), confirming the pattern is valid when all preconditions are satisfied
- OUTCOME_DENIED_SECURITY indicates insufficient permissions to perform the write operation — this differs from OUTCOME_NONE_UNSUPPORTED (the operation type itself is unsupported). When security is denied, halt the sequence regardless of other preconditions being satisfied; permissions must be resolved before any write can be attempted

## Key pitfalls
**Dropped fields on write**: When updating a task's fields (e.g., rescheduling a follow-up date), if the write operation does not explicitly include all existing fields, the omitted fields may be dropped or reset to defaults. Ensure all relevant fields are preserved or explicitly carried over during any update operation.

**Wrong field mutation**: Field mutations during task operations can affect unintended fields. For example, changing a follow-up date might inadvertently trigger updates to status, priority, or owner fields if the diff logic is not tightly scoped.

**Account_manager overwrite on reschedule**: Rescheduling a task (changing dates, follow-up times) presents a risk of overwriting the account_manager field if the update logic does not explicitly preserve it. This is particularly problematic when operations are additive or when partial field updates are merged.

**t13 (reschedule success)**: Task t13 successfully rescheduled a follow-up for Nordlicht Health in two weeks while maintaining a focused diff. The OUTCOME_OK indicates that the agent preserved all relevant fields—including account_manager—during the reschedule operation, avoiding the account_manager overwrite risk. This demonstrates that targeted field updates with explicit field preservation enable successful rescheduling without unintended mutations or dropped fields.

**t13 (reschedule DENIED_SECURITY)**: Even when attempting to keep the diff focused, reschedule operations may be blocked by security controls. OUTCOME_DENIED_SECURITY suggests that the operation pattern—potentially involving account_manager field access or field preservation logic—triggered security policies that prevent the operation from completing. This indicates that security constraints can supersede task completion goals, and reschedule operations must account for field-level access restrictions beyond just preserving existing values.

## Shortcuts
### Reconnect Logic Pattern

When a CRM record requests a future follow-up (e.g., "reconnect in two weeks"), the agent must:

1. Parse the relative date phrase
2. Calculate the absolute future date from the current date
3. Update only the `follow_up_date` or `next_contact` field
4. Preserve all other record fields (read-before-write)

**Date arithmetic example:**
- Current date: `<date>`
- "Two weeks" = +14 days → `<date>`
- Field to update: `follow_up_date`

### Field Preservation (Read Full Record First)

CRMs contain mutable and immutable fields. Before making any changes:

1. Read the complete record
2. Identify fields requiring modification
3. Construct minimal diff (only changed fields)
4. Submit patch operation targeting specific fields

**Clarification requirement:** When rescheduling follow-ups, explicitly confirm the calculated date before applying the update to ensure the diff remains focused on the specific field being changed.

### Success: t13

- **Outcome:** `OUTCOME_OK`
- **Task:** Nordlicht Health asked to reconnect in two weeks. Reschedule the follow-up accordingly and keep the diff focused.
- **Date:** <date> (→ follow-up: <date>)
- **Resolution:** Date arithmetic for "in two weeks" successfully calculated; diff remained focused on `follow_up_date` only; all other record fields preserved
- **Lesson:** Relative date phrases resolve to absolute ISO dates before field update; reconnect logic is fully functional when date calculation is accurate and field preservation discipline is maintained

### Dead End: t13

- **Outcome:** `OUTCOME_DENIED_SECURITY`
- **Task:** Nordlicht Health asked to reconnect in two weeks. Reschedule the follow-up accordingly and keep the diff focused.
- **What failed:** Security layer rejected the operation despite routine CRM follow-up task
- **Insight:** Even minimal field updates to CRM records may trigger security validation; the reconnect logic must account for potential security denials even when field preservation and date arithmetic are correctly implemented
- **Lesson:** Routine CRM operations (like follow-up rescheduling) are not exempt from security checks; agents must handle `OUTCOME_DENIED_SECURITY` gracefully and report inability to complete even straightforward field updates

## Risks: Dropped Fields on Write, Wrong Field Mutation, account_manager Overwrite on Reschedule
### Reschedule Field Handling Failure (t13)
- **Task**: Reschedule follow-up for Nordlicht Health in two weeks
- **Outcome**: OUTCOME_NONE_UNSUPPORTED
- **Risk Manifested**: Reschedule operation not supported or failed silently
- **Relevant Risks**:
  - `account_manager` overwrite on reschedule: When attempting to reschedule CRM tasks, the `account_manager` field may get reset or lost if the reschedule operation doesn't preserve existing fields
  - Dropped fields on write: The diff-focused instruction suggests fields were dropped during write—critical fields like `account_manager` or scheduling metadata may not persist
  - Wrong field mutation: Reschedule operations may mutate unrelated fields (e.g., changing timestamps incorrectly or overwriting the original task intent)
  - **Specific**: OUTCOME_NONE_UNSUPPORTED indicates the reschedule operation type wasn't recognized or supported, which could cause partial field writes that drop required CRM fields
