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

## Verified refusal: t12 (2026-04-29)
<!-- refusal: t12:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Send short follow-up email to Alex Meyer about next steps on the expansion. Keep the diff focused.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Cannot complete: Contact 'Alex Meyer' does not exist in the vault. Performed exhaustive search (10+ attempts) across /contacts, full vault, and /01_notes for 'Alex Meyer', 'Alex', and 'Meyer' — all re

**Probes before refusal:**
1. search
2. search
3. list(/contacts)
4. search
5. search
6. search

**Applies when:** email

## Successful pattern: t17 (2026-04-29)
<!-- researcher: t17:e5892dba994c -->

**Goal shape:** Email reminder to Albers Ralf at Acme Robotics with subject "Checking in" and about "Checking whethe

**Final answer:** Email reminder sent to Ralf Albers at Acme Robotics with subject 'Checking in' and body 'Checking whether now is a good time to pick up the next step.' All 4 required evidence items provided in ground

**Trajectory:**
1. search
2. read(/contacts/<file>)
3. read(/outbox/<file>)
4. write(/outbox/<file>)
5. read(/outbox/<file>)
6. read(/contacts/<file>)
7. read(/outbox/<file>)

**Key insights:**
- (none)

**Applies when:** email

## Successful pattern: t14 (2026-04-29)
<!-- researcher: t14:3ed30fcb7ff6 -->

**Goal shape:** Send email to Aperture AI Labs with subject "Security review follow-up" and body "Checking in on the

**Final answer:** Email queued to Aperture AI Labs (Jonas Schneider) with subject 'Security review follow-up' and body 'Checking in on the open security review. Happy to answer questions and align on next steps.'

**Trajectory:**
1. search
2. read(/accounts/<file>)
3. read(/contacts/<file>)
4. read(/outbox/<file>)
5. write(/outbox/<file>)
6. read(/outbox/<file>)
7. read(/accounts/<file>)
8. read(/contacts/<file>)
9. read(/outbox/<file>)
10. read(/outbox/<file>)
11. read(/accounts/<file>)
12. stall

**Key insights:**
- (none)

**Applies when:** email

## Verified refusal: t04 (2026-04-29)
<!-- refusal: t04:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Email Maya a brief update on whichever initiative matters most.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Cannot complete: vault lacks required infrastructure. After exhaustive verification:

1. /contacts/ directory does not exist - confirmed via list at steps 4 and 8
2. /outbox/ directory does not exist

**Probes before refusal:**
1. read(/90_memory/soul.md)
2. read(/90_memory/agent_initiatives.md)
3. search(?)
4. search
5. list(/)
6. search

**Applies when:** email

## Successful pattern: t26 (2026-04-29)
<!-- researcher: t26:1ca0c0b4cc89 -->

**Goal shape:** email to aperture ai labs with subject "Security review follow-up" and body "Checking in on the open

**Final answer:** Email queued to Aperture AI Labs (Leon Kooistra) with subject 'Security review follow-up' and body 'Checking in on the open security review. Happy to answer questions and align on next steps.'

**Trajectory:**
1. search
2. search
3. read(/accounts/<file>)
4. read(/contacts/<file>)
5. read(/outbox/<file>)
6. write(/outbox/<file>)
7. read(/outbox/<file>)
8. read(/accounts/<file>)
9. read(/contacts/<file>)
10. read(/outbox/<file>)
11. read(/outbox/<file>)

**Key insights:**
- (none)

**Applies when:** email
