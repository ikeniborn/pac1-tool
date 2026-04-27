## Email Task Workflows

### Proven Step Sequences

#### Send Email by Contact Name (OUTCOME_OK)
1. Search `/contacts` using the recipient's name or partial name (surname-only is valid) → locate matching contact file
2. Read the matched contact file → extract the `email` field
3. Read `/outbox/<file> → extract the next message ID slot
4. Write `/outbox/<file> with subject, body, and recipient email from step 2; update `seq.json`

**Verify:** Two files written — `seq.json` updated, `<id>.json` created.

**Confirmed by:** t17, t26 both completed successfully via this sequence.

> **Shortcut:** Steps 2 and 3 have no dependency on each other. `seq.json` can be read as early as step 1 (in parallel with contact resolution) to shave a round-trip from the critical path. Write only after both reads are complete.

---

#### Send Email by Account/Organisation Name (OUTCOME_OK)
1. Search `/contacts` using the organisation name keyword → if no match, proceed to step 2
2. Search `/accounts` using a short keyword extracted from the organisation name (not the full descriptive phrase) → locate matching account file
3. Read the matched account file → extract the account ID
4. Search `/contacts` filtering by that account ID → locate the primary contact file
5. Read the contact file → extract the `email` field
6. Read `/outbox/<file> → extract the next message ID slot *(can be done in parallel with steps 2–4)*
7. Write `/outbox/<file> with subject, body, and recipient email from step 5; update `seq.json`

**Verify:** Two files written — `seq.json` updated, `<id>.json` created.

**Confirmed by:** t14 completed successfully via this sequence.

> **Shortcut:** Steps 2–4 can overlap. `seq.json` (step 6) should be read in parallel with the searches and account file read, not deferred until after contact resolution. This parallelization reduces total steps to 4–5 and avoids stall detection warnings.

> **Keyword tip:** When searching `/accounts`, use a short distinctive keyword (e.g. a proper noun from the org name) rather than the full verbose task description. Full phrases cause false negatives.

---

### Key Risks and Pitfalls

#### Wrong-Recipient Failures (Critical)
- **NEVER** use wiki-cached, session-memory, or previously-seen contact/account IDs to skip the contact-file read. Always read the contact file at runtime to obtain the `email` field.
- The agent MUST read `/contacts/<file> before every outbox write, even when the recipient seems obvious from the task description.
- Skipping the contact-file read — e.g. jumping directly to a specific contact file after a failed search without going through account resolution — has caused wrong-recipient delivery failures.
- This includes the antipattern of reading a hardcoded or recalled contact path after a contact-name search returns no matches: the correct fallback is the account-resolution path (steps 2–5 above), not a direct file read.

#### Vault Structure Absent (Critical)
- Before any search, confirm that `/contacts` and `/outbox` directories exist in the vault tree.
- If listing the vault root does not show both directories (or directory search returns `NOT_FOUND`), surface a `CLARIFICATION` outcome immediately — no further steps can succeed.
- Do not attempt contact resolution or outbox writes against a missing vault structure.
- **Evidence:** t04 encountered vault structure failure (no `/contacts` or `/outbox` in vault root listing). Correctly escalated to CLARIFICATION.

#### Contact Not Found → Clarification Required
- Attempt full-name, surname-only, and first-name-only searches against `/contacts` before concluding no match exists.
- If all name-based searches return no matches and a subsequent account search also yields nothing, do **not** guess or fabricate an address.
- Surface a `CLARIFICATION` outcome: state which name(s) or organisation was searched and that no match was found.
- Do not write to `/outbox/<file> without a confirmed recipient address obtained from a file read in the current session.
- **Evidence:** t12 executed surname-only and first-name-only searches with no matches, then account-keyword search also failed. Correctly surfaced CLARIFICATION.

#### Stall Detection (Avoid)
- The harness issues stall warnings after ~6 steps with no write/delete/create operation.
- If reads are complete and the next message ID is known, proceed immediately to the write step — do not add intermediate no-op reads.
- Typical safe path for contact-name tasks: search → read contact in parallel with read seq → write outbox (≤3 steps).
- For account-routed tasks, read `seq.json` in parallel with searches (steps 1–4), not after contact resolution. This reaches the write step with all required data in 4–5 steps, avoiding stall warnings.
- **Evidence:** t14 triggered multiple stall warnings (6, 7, 8 step marks) when `seq.json` was deferred until after contact resolution. Parallelizing would have reduced to 4–5 steps.

#### Ambiguous Recipient
- Tasks naming only a first name or a vague org descriptor without a vault match will fail contact resolution.
- Partial-name searches (surname only, or first name only) should be attempted before surfacing clarification, but if both yield no match, stop immediately.

---

### Task-Type Specific Insights

#### Email Tasks — Shortcuts
- **Name search first, account search second.** Searching `/contacts` directly by name (or surname) is faster than routing through `/accounts` first. Fall back to account search only when the name search yields no matches.
- **Org-keyword searches on `/contacts` can directly match contact files.** Searching `/contacts` with a keyword derived from an organisation name can sometimes locate a contact file immediately, providing a faster path than account resolution.
- **Multiple name-search attempts may succeed when the first fails.** When an initial search (full name, surname, or org variant) returns no matches, secondary searches using other name patterns can still locate the contact file.
- **seq.json is dependency-free and can be read early.** Reading `/outbox/<file> as the first or concurrent operation (before or in parallel with contact resolution) is safe and reduces total steps when contact lookup takes multiple searches.
- **seq.json auto-increments after write.** After writing an outbox message, seq.json is automatically updated to the next ID; no manual increment is required.
- Contact files contain: `id`, `account_id`, `full_name`, `role`, `email`. The `email` field is the only value needed for outbox dispatch.
- Account files contain: `name`, `account_manager`, `status`, `industry`. Use account files only to bridge org name → account ID → contact lookup; do not use them as email sources.
- For account-routed tasks, searching `/accounts` with a short keyword (not the full descriptive org phrase) yields faster matches and avoids false negatives.
- **Surname-only and first-name-only searches are valid fallbacks** and frequently resolve contacts when full-name search fails.
- **Parallelizing seq.json read in account-path tasks prevents stall warnings** and reduces step count by 2–3. Read `seq.json` in parallel with the `/accounts` and `/contacts` searches, not sequentially after them.

#### Clarification Triggers
| Condition | Action |
|---|---|
| `/contacts` or `/outbox` directories not found in vault root listing | Surface `CLARIFICATION`: vault structure absent |
| Full-name, surname-only, first-name-only, and account searches all return no matches | Surface `CLARIFICATION`: recipient unresolvable |
| Task names only a first name with no surname or org context | Attempt partial searches; if none match, surface `CLARIFICATION` |
| Search root errors (`NOT_FOUND`) on first step | Surface `CLARIFICATION`: vault inaccessible |

---
