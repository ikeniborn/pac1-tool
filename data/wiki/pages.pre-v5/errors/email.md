<!-- wiki:meta
category: errors/email
quality: developing
fragment_count: 7
fragment_ids: [t14_20260504T202354Z, t26_20260504T212526Z, t26_20260504T222224Z, t09_20260504T230800Z, t11_20260504T231043Z, t14_20260504T231448Z, t11_20260505T001527Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Step Sequence (t26 - email to blue harbor bank):**

1. **Contact Lookup** → Resolve "blue harbor bank" to contact entry
2. **Outbox Write** → Compose email with subject "Security review follow-up" and body "Checking in on the open security review. Happy to answer questions and align on next steps."
3. **OUTCOME_OK** ✓

---

**Step Sequence (t26 - email to aperture ai labs):**

1. **Contact Lookup** → Resolve "aperture ai labs" to contact entry
2. **Outbox Write** → Compose email with subject "Security review follow-up" and body "Checking in on the open security review. Happy to answer questions and align on next steps."
3. **OUTCOME_OK** ✓

---

**Dead end: t26**
Outcome: OUTCOME_OK
What failed:
- (see outcome above)

---

**Dead end: t09**
Outcome: OUTCOME_NONE_UNSUPPORTED
What failed:
- (see outcome above)

---

**Dead end: t11**
Outcome: OUTCOME_OK
What failed:
- (see outcome above)

---

**Dead end: t14**
Outcome: OUTCOME_OK
What failed:
- (see outcome above)

## Key pitfalls
- **Task completion does not imply goal achievement**: A task may return OUTCOME_OK (e.g., email sent successfully) yet still be a "dead end" — the atomic operation succeeded but the intended workflow chain was interrupted or failed to progress.
- **Silent failures at workflow level**: When an agent completes sub-tasks successfully without detecting that higher-level objectives remain unfulfilled, it may mark operations as complete when they are actually premature or insufficient.
- **Skipped contact file reads**: If the agent skips reading contact information (e.g., recipient details, reply-to addresses), it may send emails to incorrect or outdated recipients despite reporting OUTCOME_OK.
- **Hardcoded email addresses not cross-verified**: Even when a recipient address appears explicit (e.g., "<email>"), relying on it without verifying it is still current and valid is a failure pattern — the address may be outdated, mistyped, or reassigned to a different person, creating a wrong-recipient risk that masquerades as precise targeting.
- **Wrong-recipient risks in email tasks**: Sending to "Blue Harbor Bank" or similar generic/ambiguous recipients without verifying against an authoritative contact file can result in misdirected communications that appear successful but reach unintended parties.
- **Ambiguous company-name recipients**: Using company names like "aperture ai labs" as email recipients without resolving them to specific, verified contacts is a known failure pattern — the task completes with OUTCOME_OK but may reach an unintended party or land in a catch-all inbox rather than the intended security review stakeholder.

## Shortcuts
**Dead End: t14** — Standard email composition and dispatch completed successfully without requiring special optimizations or lookup shortcuts. This pattern indicates that routine outbound email tasks (known recipient, clear subject, direct body) can be handled with default behavior. No context caching, alias lookups, or template shortcuts were triggered. Future optimizations may focus on: recipient auto-complete from contact cache, subject line suggestions based on conversation history, or body template suggestions for common follow-up scenarios.

**Dead End: t26** — Outcome: OUTCOME_OK

What failed:
- (see outcome above)

Pattern analysis: Routine follow-up email with clear subject and direct body dispatched without optimization triggers. Consistent with t14 behavior—standard composition and dispatch completed successfully without context caching, alias lookups, or template shortcuts. Future optimizations may focus on: recipient auto-complete from contact cache, subject line suggestions based on conversation history, or body template suggestions for common follow-up scenarios.

Additional insight from t26: Even emails to established contacts (aperture ai labs, in context of an ongoing security review) do not trigger optimizations when subject and body are provided directly. The "open security review" context implies prior communication, yet this relationship context alone is insufficient to activate template or caching shortcuts. This reinforces that optimization triggers require either ambiguity in content (suggesting auto-complete) or pattern repetition (suggesting template usage)—direct instruction bypasses all shortcuts regardless of relationship history.

**Dead End: t11** — Outcome: OUTCOME_OK

What failed:
- (see outcome above)

Pattern analysis: Brief email composition to known recipient with explicit subject and body completed without optimization triggers. Consistent with t14 and t26 behavior—standard composition and dispatch completed successfully without context caching, alias lookups, or template shortcuts.

Additional insight from t11: Even minimal body content ("Brief update.") does not trigger optimizations when subject and body are provided directly. This reinforces that optimization shortcuts are not activated by brevity of content alone—all standard email fields being explicitly provided bypasses all shortcut mechanisms regardless of email length or contact familiarity.
