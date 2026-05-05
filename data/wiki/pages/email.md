<!-- wiki:meta
category: email
quality: mature
fragment_count: 18
fragment_ids: [t12_20260504T192946Z, t14_20260504T192814Z, t17_20260504T193248Z, t35_20260504T194657Z, t12_20260504T202944Z, t17_20260504T202220Z, t26_20260504T203226Z, t35_20260504T204055Z, t11_20260504T211401Z, t12_20260504T211700Z, t35_20260504T213810Z, t12_20260504T221104Z, t35_20260504T223021Z, t17_20260504T231502Z, t26_20260504T232447Z, t12_20260505T001748Z, t17_20260505T002031Z, t26_20260505T002546Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
t14, t17, t35 all succeeded as email tasks with OUTCOME_OK, each involving sending follow-up or checking-in messages to recipients. However, the step sequences for these tasks (including any contact lookup then outbox write patterns) were not captured in the provided fragment data.

t17 and t26 both succeeded as email tasks on <date>, each sending follow-up or checking-in messages (respectively to Lange Erik at GreenGrid Energy and Aperture AI Labs). However, the step sequences for these tasks (including any contact lookup then outbox write patterns) were not captured in the provided fragment data.

## Key pitfalls
- **Ambiguous recipient references** — Task t35 shows a vague recipient designation ("account Benelux compliance-heavy bank account Blue Harbor") combined with extra task context ("a separate AI data-flow review") that was not in the original brief. This pattern can lead to wrong-recipient errors when the agent interprets a non-standard identifier or adds unsolicited content to a task, potentially misrouting or misframing the communication. Task t35 on <date> did complete successfully (OUTCOME_OK) sending to this ambiguous reference, suggesting the agent may successfully dispatch to non-standard identifiers even when human interpretation would find them unclear.
- **Unresolved contact lookups leading to clarification failures** — Task t12 required sending an email to "Alex Meyer" about next steps on an expansion but returned OUTCOME_NONE_CLARIFICATION, suggesting the agent attempted the task without locating required contact details, resulting in an incomplete attempt rather than an error or wrong-recipient dispatch. This pattern of skipped contact file reads can stall task completion and may also lead to misrouting if the agent guesses or infers recipient details. Task t12 on <date> repeated this same failure, indicating the contact lookup gap persists as a consistent failure mode.

## Shortcuts
**Email Optimization Patterns**

- **Follow-up subject shortcuts**: Standard patterns include `"Subject: follow-up"` and `"Subject: Checking in"` for status queries — reuse these templates rather than regenerating subjects.
- **Body templates**: Common follow-up phrases include `"Checking in on the [topic]. Happy to answer questions and align on next steps."` and `"Following up to see if you want to continue..."` — these can be parameterized per recipient.
- **Keep diffs focused**: When task specifies "Keep the diff focused," use concise language and omit extraneous context. Single-topic emails get faster responses.
- **Batch opportunities**: Multiple emails on the same date (e.g., `<date>`) suggest calendar clustering — queue related follow-ups together to reduce context-switching.
- **Context-specific subject shortcuts**: For security-related topics, use `"Security review follow-up"` as a reusable subject pattern. For time-sensitive status checks, use `"Quick follow-up"` for brevity.
- **Pattern reuse across recipients**: When multiple recipients share context (e.g., both Blue Harbor Bank and Aperture subscriber needed security review follow-up), the same subject line can be applied — maintain consistency while parameterizing body content per recipient.
- **Day-name subject shortcuts**: Status updates tied to specific days use patterns like `"Friday status"` or `"Monday check-in"` — reuse day-name contexts in subjects for calendar-aligned updates.
- **Minimal body approach**: For simple updates, single-phrase bodies like `"Quick note."` suffice — concise delivery improves response rates for low-stakes messages.
- **Next-step follow-ups**: For scheduling-oriented messages about advancing work, use bodies like `"Checking whether now is a good time to pick up the next step."` — these frame follow-ups around progression rather than status checking.

## Successful pattern: t14 (2026-05-04)
<!-- researcher: t14:e3b0c44298fc -->

**Goal shape:** Send email to Aperture AI Labs with subject "Security review follow-up" and body "Checking in on the

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

**Key insights:**
- (none)

**Applies when:** email

## Verified refusal: t12 (2026-05-04)
<!-- refusal: t12:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Send short follow-up email to Alex Meyer about next steps on the expansion. Keep the diff focused.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?

**Applies when:** email

## Successful pattern: t17 (2026-05-04)
<!-- researcher: t17:e3b0c44298fc -->

**Goal shape:** Email reminder to Bender Dennis at Acme Logistics with subject "Checking in" and about "Following up

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

**Key insights:**
- (none)

**Applies when:** email

## Successful pattern: t35 (2026-05-04)
<!-- researcher: t35:e3b0c44298fc -->

**Goal shape:** Send email to the account Software account with a separate AI data-flow review with subject "Securit

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

**Key insights:**
- (none)

**Applies when:** email

## Successful pattern: t26 (2026-05-04)
<!-- researcher: t26:e3b0c44298fc -->

**Goal shape:** email to blue harbor bank with subject "Security review follow-up" and body "Checking in on the open

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

**Key insights:**
- (none)

**Applies when:** email

## Successful pattern: t11 (2026-05-04)
<!-- researcher: t11:e3b0c44298fc -->

**Goal shape:** Write a brief email to "<email>" with subject "Friday status" and body "Quick note."

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

**Key insights:**
- (none)

**Applies when:** email
