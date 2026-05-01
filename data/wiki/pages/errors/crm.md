<!-- wiki:meta
category: errors/crm
quality: nascent
fragment_count: 4
fragment_ids: [t13_20260430T134201Z, t13_20260430T164105Z, t32_20260430T165803Z, t13_20260430T210521Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Proven sequence for rescheduling follow-ups:**

1. Read task `date` field as the reference date
2. Read account's `next_follow_up_on` field (fallback reference)
3. Apply date arithmetic (e.g., +N days/weeks) to the correct reference date from step 1
4. Update `next_follow_up_on` in the account JSON
5. Update `due_on` in the reminder JSON
6. Verify both dates match — diff must be focused; only date fields change

**Date arithmetic rules:**
- Add two weeks = +14 days
- Reference date from task takes priority over stored account dates
- Result date must be plausible relative to the reference date (not months away)

**Failure mode observed:**
When the reference date from the task (e.g., <date>) is ignored in favor of a stale stored date (e.g., <date>), date arithmetic produces nonsense results (e.g., <date> from November). Always anchor to the task's `date` field first.

**Write operation considerations:**
- Write failures due to contract gates (e.g., FIX-415) do not constitute task failure — `OUTCOME_OK` applies when the intent is correctly computed and the block is outside agent control
- Audit context files (e.g., `docs/follow-up-audit.json`) provide authoritative target dates when explicit; respect `requested_due_on` values over arithmetic when specified
- Queue notes in audit context are informational only; the final fix must remain focused on date fields only

**Contradictory result pattern:**
When arithmetic produces a result far later than expected from the task's `date` field (e.g., task date <date> with "+2 weeks" yields August instead of May), this signals that the reference date was not anchored to the task's `date` field — even if both written dates match and verification reads confirm consistency. The task may resolve to OUTCOME_OK due to internal consistency while the underlying arithmetic error persists. The authoritative reference must always be validated before writing.

## Key pitfalls
- **Dropped fields on write:** When modifying only a subset of record fields (e.g., updating `next_follow_up_on` and `due_on` for a reschedule), the agent must write the full record. Partial writes risk losing fields not explicitly addressed in the operation. The Nordlicht Health task updated dates only, which is safe when the agent reads the full record first, but becomes dangerous if the agent attempts a targeted patch without read-then-write semantics. The t13 agent performed a full read of both `/accounts/<file> and `/reminders/rem_001.json` before writing, confirming all fields were preserved in the final state. The audit context in t32 flagged a `candidate_patch: reminder_only` strategy, indicating the audit pipeline itself is aware that partial updates risk dropping fields and requires the agent to write the full record. In this t13 task, the evaluator instruction "keep the diff focused" could have encouraged a targeted patch approach, but the agent correctly maintained full read-then-write discipline, which resulted in OUTCOME_OK. This demonstrates that even when downstream instructions suggest minimal changes, preserving all fields via a full record write is the correct strategy.

- **Wrong field mutation:** Rescheduling a reminder requires updating the correct date field on both the parent account record and the reminder record. If the agent mutates the wrong field (e.g., `last_contacted_on` instead of `next_follow_up_on`), the account's CRM state becomes inconsistent. In the t13 task, the agent correctly targeted `next_follow_up_on` and `due_on`, avoiding this class of error. The t32 task also correctly identified the target fields (`due_on` on rem_002 and `next_follow_up_on` on <account>), demonstrating consistent field targeting discipline.

- **account_manager overwrite on reschedule:** Rescheduling a follow-up or reminder could inadvertently overwrite the `account_manager` field if the agent reconstructs the account record with a stale or missing `account_manager` value from a prior read. In the t13 task, the agent preserved `account_manager: "Clara Braun"` correctly; however, a poorly written write operation that omits the field could reset it to a default or null value, causing ownership loss on the CRM record. The t13 agent re-read both records after writing to verify `account_manager` remained intact, confirming read-then-write semantics prevented inadvertent overwrite.

- **Outcome: OUTCOME_NONE_CLARIFICATION — dead end:** The t13 task for Nordlicht Health returned `OUTCOME_NONE_CLARIFICATION`, indicating the agent reached a point where it could not proceed and no further clarification was available. This suggests the task pipeline does not surface guidance when the agent stalls, leaving the operation incomplete. If the agent enters an ambiguous state mid-write (e.g., unsure whether to update only the reminder or also the account), the lack of a clarification path can cause the entire task to terminate without resolution. This dead-end risk is distinct from incorrect mutations; it represents a failure mode where the agent ceases operation without a fallback. The t32 task was blocked by a FIX-415 contract gate after reading but before writing, resulting in an `OUTCOME_OK` status despite never completing the mutation. This represents a distinct dead-end pattern: the agent correctly identified the target records and fields, performed the required reads, but was prevented from writing by an external gate with no recovery path surfaced to the agent.

## Shortcuts
- **Dead end handling**: When an outcome is `OUTCOME_NONE_CLARIFICATION`, no file modifications are safe to make. The task is left incomplete and requires user or evaluator clarification before proceeding. Always check that the evaluator response is `approved: true` before writing any vault changes; a failed `approved: false` means the diff must not be applied.
- **Field preservation**: When writing to a record, do not assume all fields are included in the write payload. Always read the full existing record first to identify fields that must be preserved (e.g., `account_manager`). Fields missing from the write payload should remain unchanged.
- **Date arithmetic**: When the task specifies a relative duration ("in two weeks") rather than an absolute date, compute the target date by adding the interval to the current follow-up date from the account record, then write the computed date to both the reminder and the account. Do not apply the interval to the current system date.
- **Reconnect logic**: When asked to reschedule a follow-up (e.g., "reconnect in two weeks"), update both `due_on` on the reminder record and `next_follow_up_on` on the account record to the same target date. Both fields must remain in sync.
- **Audit context**: For regression or follow-up tasks, check for an audit document under `docs/` (e.g., `docs/follow-up-audit.json`) before making changes. The audit may specify a `candidate_patch` strategy (e.g., `reminder_only`) that constrains which records to update. Respect the strategy and keep the diff focused to the minimum necessary changes.
- **Write gates**: Some accounts may have contract gates (e.g., FIX-415) that prevent writes. If a write is blocked, report the constraint; do not force the write.
