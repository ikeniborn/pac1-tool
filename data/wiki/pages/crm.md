## CRM Workflow Wiki

---

## Proven Step Sequences

### Reschedule a Follow-Up (Relative Date)

**Task type:** CRM — reschedule follow-up by relative offset
**Source:** t13 (OUTCOME_OK)

1. Search contacts/accounts for the named account → obtain `acct_id`
2. Compute target date: `today + N days` (e.g. "two weeks" = +14 days)
3. Read `/reminders/rem_XXX.json` to confirm current `due_on`
4. Write `/reminders/rem_XXX.json` with updated `due_on` — **once only**
5. Write `/accounts/acct_XXX.json` with updated `next_follow_up_on`

**Verify:** Both files reflect the new date. Diff is limited to the two date fields only.

> **Note:** t13 wrote `rem_001.json` four times before writing the account file — a retry-loop anti-pattern. Write once; do not re-write to "confirm."

---

### Fix a Follow-Up Date Regression (Audit-Guided)

**Task type:** CRM — correct a date regression with audit context
**Source:** t32 (OUTCOME_OK)

1. Read the audit file (e.g. `/docs/follow-up-audit.json`) — extract `candidate_patch`, `account_id`, and target date
2. Read `/reminders/rem_XXX.json` to confirm the stale `due_on`
3. If `candidate_patch == "reminder_only"`, write **only** `/reminders/rem_XXX.json`; do not touch the account file
4. Update `due_on` to the explicit target date from the audit; preserve all other fields

**Verify:** Single-file write. No account-level changes unless audit specifies otherwise.

---

### Look Up an Account by Descriptive Attributes (Read-Only)

**Task type:** CRM — account lookup, no writes
**Source:** t34 (OUTCOME_OK)

1. Run a broad search across `accounts/` to get candidate file list
2. Read each candidate account file; match on industry, region, and qualitative flags (e.g. "weak internal sponsorship")
3. Return the exact `name` field value from the matching JSON

**Verify:** No writes needed. Answer is taken verbatim from the `name` field — do not paraphrase.

---

### Handle Inbox — Invoice Re-send Reply

**Task type:** CRM — inbox handling, outbound email composition
**Source:** t18 (OUTCOME_OK)

1. Identify the inbox item requiring action (e.g. request to resend an invoice)
2. Resolve the relevant account ID and locate the invoice file under `/my-invoices/INV-XXX-XX.json`
3. Read the invoice JSON to extract line items, amounts, and issued date needed for the reply
4. Compose the outbound email payload (fields: `to`, `subject`, `body`)
5. Write the message file to `/outbox/<msg_id>.json`
6. Write/update `/outbox/seq.json` to register the message in the outbox sequence

**Verify:** Both `/outbox/seq.json` and the individual message file are written. Do not attempt to read back `/outbox/<msg_id>.json` to confirm — the vault root may be unmounted in the execution environment, causing a spurious path-not-found error on re-read even after a successful write.

---

## Key Risks and Pitfalls

| Risk | Detail |
|---|---|
| **Over-writing on reschedule** | t13 wrote `rem_001.json` four times before writing the account file — indicates retry loops. Write once; do not re-write blindly to "verify." |
| **Ignoring audit scope** | t32 audit specified `candidate_patch=reminder_only`. Touching the account file would have been an out-of-scope change. Always read the audit before deciding which files to patch. |
| **Stall on read-only tasks** | t34 triggered a stall warning after 6 steps with no writes. For lookup-only tasks, proceed to answer immediately after identifying the match — do not keep reading unrelated files. |
| **"Two weeks" ambiguity** | t13 computed +14 days for "two weeks." This is the expected interpretation; always document the exact day-count used when a relative offset is not an obvious multiple of 7. |
| **Verbatim vs. inferred answer** | For exact-name queries (t34), copy the `name` field literally from JSON. Do not normalise, abbreviate, or infer. |
| **Vault unmount causes false read-back failure** | t18 evaluator flagged a path-not-found on `/outbox/84273.json` immediately after a confirmed write. This is an environment issue (vault root unmounted), not a write failure. Do not retry or re-write; trust the WRITTEN confirmation and move on. |
| **Partial field preservation on reminder write** | t32 explicitly preserved all fields when updating `due_on`. Never overwrite the full file with a stripped-down payload — read first, patch the target field, write the complete object. |

---

## Task-Type Insights and Shortcuts

### CRM — Rescheduling
- Always write both `rem_XXX.json` (`due_on`) **and** `acct_XXX.json` (`next_follow_up_on`) unless an audit or task explicitly says otherwise.
- Keep the diff minimal: change only the date field(s). Do not update `updated_at`, notes, or status unless asked.
- One write per file. If a write is confirmed (WRITTEN), do not re-issue it to "check."

### CRM — Audit-Driven Patches
- `candidate_patch` in the audit JSON is the authoritative scope signal. Treat it as a constraint, not a suggestion.
- Prefer a single read → single write pattern; avoid re-reading the same file to verify a write you just made.
- Read first, patch the target field in memory, write the complete object — never overwrite with a stripped payload.

### CRM — Account Lookup
- Search first with a broad keyword to get the candidate list, then read selectively.
- Stop as soon as a unique match is found. Reading further accounts after a confirmed match wastes steps and risks stall warnings.

### CRM — Inbox Handling
- Pattern: read relevant source document (invoice, contract, etc.) → compose payload → write to `/outbox/`.
- Always update `/outbox/seq.json` alongside the individual message file; both are required for a complete outbox write.
- Do not read back outbox files to verify — treat a WRITTEN confirmation as ground truth. Environment-level vault issues can produce false path-not-found errors on re-read.