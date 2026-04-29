## Successful Email Sequence: Account → Contact → Outbox

**When to use:** Task references an account (company name, account attribute, or account descriptor).

1. `search` for account name or identifier
2. `read` `/accounts/<file> → extract `primary_contact_id`
3. `read` `/contacts/<file> → extract `email`
4. `read` `/outbox/<file> → extract next sequence number
5. `write` `/outbox/<file> with `to`, `subject`, `body`
6. `read` written file to verify write succeeded

**Rationale:** Account files link to contact IDs. Contact files contain the verified email. Sequence file prevents ID collisions.

---

## Successful Email Sequence: Direct Contact Search

**When to use:** Task names a person (full name or partial name) without specifying account.

1. `search` for contact name (try full name first, then last name if needed)
2. `read` `/contacts/<file> → extract `email`
3. `read` `/outbox/<file> → extract next sequence number
4. `write` `/outbox/<file> with `to`, `subject`, `body`
5. `read` written file to verify

**Rationale:** Direct contact search bypasses account lookup when a person is named.

---

## Verified Refusal: Contact Not Found

**Trigger:** Search returns zero matches AND exhaustive contact file reads confirm absence.

**Correct response:** Refuse with `OUTCOME_NONE_CLARIFICATION`. Do not proceed to outbox.

**Incorrect response (t12 pitfall):** Iterating through all contact files without finding a match causes stall escalation without advancing toward completion. After 3 failed searches, refuse rather than exhaustive file-by-file read.

**Prerequisite checks before refusal:**
- At least one `search` with no matches
- If name is ambiguous (e.g., "Alex"), try partial name search before concluding contact does not exist

---

## Verified Refusal: No Contacts Directory

**Trigger:** Task is email but vault lacks `/contacts` directory.

**Correct response:** Refuse with `OUTCOME_NONE_CLARIFICATION`.

**Example (t04):** Vault is personal knowledge repository (HN links, AI engineering notes, agent memory) with no contacts directory. Task named "Sam" cannot be resolved.

**Mitigation:** `list` root directory first to verify contacts directory exists before proceeding.

---

## Pitfall: Wiki-Cached Recipient Info

**Symptom:** Emails sent to wrong recipient.

**Root cause:** Using cached/remembered recipient data instead of reading current `/contacts/<file> file.

**Fix (FIX-337):** ALWAYS read the contact file fresh before writing outbox. Never skip the contact read step even if you believe you know the recipient.

**Trajectory evidence:** t14 succeeded by reading contact twice (steps 4 and 9); t17 succeeded by reading contact once; t26 succeeded by reading contact once. Inconsistent contact reads across tasks indicate risk.

---

## Pitfall: Stall Escalation from Exhaustive Contact Search

**Symptom:** Multiple `[STALL ESCALATION]` warnings during sequential contact file reads.

**Root cause:** Reading contact files one-by-one instead of using search to narrow candidates.

**Evidence (t12):** 15 stall escalations after 9 contact files read sequentially with no match found.

**Mitigation:**
- Use `search` before reading contact files
- Limit to 3 search attempts before concluding contact does not exist
- After 3 failed searches, refuse rather than exhaustive read
- Combine reads where possible: after reading one contact file, immediately check if it matches target

---

## Pitfall: Multiple Redundant Reads

**Symptom:** Same file read multiple times within single trajectory.

**Examples:**
- t14: read account (step 4), contact (step 5), outbox (step 6), write, then read all three again (steps 10-12)
- t35: read account 3x, contact 2x, outbox 2x

**Mitigation:** Verify content immediately after write in a single read. Do not re-read files unless verification specifically fails.

---

## Core Rule: Read Before Write

**Immutable sequence for email tasks:**
1. Locate correct contact file
2. Extract `email` field from that file
3. THEN write to outbox

Skipping step 1-2 for any reason (time pressure, "I know this person already", relying on prior context) causes wrong-recipient failures.

---

## Core Rule: Verify Write Immediately

**Correct pattern:** After writing outbox file, read it once to confirm content matches task requirements.

**Anti-pattern:** Re-reading accounts/contacts after successful outbox write—indicates uncertainty that should have been resolved before write.

---

## Task-Type Insight: Email with Vague Descriptor

**Challenge:** Task describes account by attribute (e.g., "Dutch banking customer with open security review") rather than naming it directly.

**Pattern (t35):**
- Multiple `search` attempts may be needed before finding matching account
- Use `search` with attribute keywords (industry + compliance flag)
- Once account found, standard Account→Contact→Outbox sequence applies

**Optimization:** Batch attribute keywords into fewer searches rather than searching each term separately.
