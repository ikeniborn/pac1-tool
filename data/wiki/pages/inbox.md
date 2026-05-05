<!-- wiki:meta
category: inbox
quality: developing
fragment_count: 9
fragment_ids: [t07_20260504T192044Z, t08_20260504T192246Z, t07_20260504T201436Z, t19_20260504T203110Z, t07_20260504T211106Z, t21_20260504T211830Z, t07_20260504T220454Z, t21_20260504T221608Z, t27_20260504T222443Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Task t07 - Inbox Item (No outcome yet)**
- Date: <date>
- Task: Handle the next inbox item.
- Outcome: Pending

**Task t19 - Inbox Processing (OUTCOME_OK)**
- Date: <date>
- Task: PROCESS INBOX.
- Outcome: OUTCOME_OK

**Proven Pattern Observed:**
1. Task type: inbox
2. Task description: "PROCESS INBOX." or "Handle the next inbox item."
3. Target outcome: OUTCOME_OK
4. Both tasks dated: <date>

## Key pitfalls
**Truncated or Incomplete Task Descriptions**
When inbox tasks are initiated, the task description may be incomplete or cut off (e.g., "Process this inbox ent" instead of a full description). This creates ambiguity about what specific action is required, leading to failed clarification attempts or incorrect processing. Agents should verify task text completeness before proceeding.

**Vague High-Level Directives**
Inbox tasks may contain only generic command text without specific processing instructions (e.g., "PROCESS INBOX" or "Handle the next inbox item"). Such vague directives provide no context about what action is actually required, what items to prioritize, or what outcome is expected, leaving agents without actionable guidance for meaningful processing.

**Empty Outcome Recording**
Tasks may complete execution without any outcome being recorded. An empty outcome field provides no evidence that work was performed or completed successfully, making it impossible to verify task completion or audit the inbox processing history.

**No Operation Tracking (Empty DONE OPS)**
Inbox processing tasks may execute with zero recorded operations, suggesting either: the agent failed to execute any actions, actions were taken but not logged, or the system failed to capture the operation history. Without DONE OPS records, there's no trace of what processing steps were attempted.

**Missing Step Facts**
Inbox tasks may lack any STEP FACTS documentation, eliminating the reasoning chain and context that would explain why specific processing decisions were made. This breaks the audit trail and prevents future analysis of inbox handling patterns.

**Security Denial Without Operation History**
Tasks may terminate with OUTCOME_DENIED_SECURITY while recording zero DONE OPS and no STEP FACTS. This combination indicates the processing was blocked by permission or access controls before any operations could be logged, leaving no evidence of what was attempted or why access was denied. Such gaps prevent auditing of security-related processing failures and obscure whether the denial was expected or anomalous.

**Lack of Verification Before Closing**
Agents processing inbox items may mark tasks complete without verifying that the inbox item was actually addressed, resolved, or properly routed. This results in items remaining unprocessed while the task shows no failure state.

**Ambiguous Item Identification**
Tasks referencing "the next inbox item" without explicit item identification create race conditions where multiple concurrent inbox processes may operate on the same item, or items may be skipped if the inbox state changes during processing.

**Unprocessed Termination Without Clarification Attempts**
When tasks terminate without completing processing but record OUTCOME_NONE_CLARIFICATION, it indicates the agent abandoned the task without attempting to resolve ambiguity or request clarification. This suggests the agent may be pre-disposed to give up rather than seek the information needed to proceed, resulting in items remaining unprocessed despite task existence.

## Shortcuts
- Empty outcomes from inbox tasks (like t07) require explicit handling or state tracking
- OUTCOME_NONE_CLARIFICATION (t08) indicates clarification prompts occur when the system reports no outcome for inbox items
- Inbox task descriptions may be truncated by the UI; assume full context when processing (e.g., "Process this inbox ent" → likely "Process this inbox entry")
- OUTCOME_DENIED_SECURITY (t27) indicates security-related denials can occur for inbox items, requiring appropriate escalation or error handling

## Verified refusal: t08 (2026-05-04)
<!-- refusal: t08:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Process this inbox ent

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?

**Applies when:** inbox

## Successful pattern: t19 (2026-05-04)
<!-- researcher: t19:e3b0c44298fc -->

**Goal shape:** PROCESS INBOX.

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?
9. ?
10. ?
11. ?
12. ?
13. ?
14. ?
15. ?
16. ?
17. ?
18. ?
19. ?
20. ?
21. ?
22. ?

**Key insights:**
- (none)

**Applies when:** inbox

## Verified refusal: t21 (2026-05-04)
<!-- refusal: t21:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Review inbox.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?

**Applies when:** inbox

## Verified refusal: t27 (2026-05-04)
<!-- refusal: t27:OUTCOME_DENIED_SECURITY -->

**Goal shape:** Review the pending inbox items.

**Outcome:** OUTCOME_DENIED_SECURITY

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?

**Applies when:** inbox
