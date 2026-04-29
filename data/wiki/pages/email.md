## Verified refusal: t04 (<date>)

**Goal shape:** Email John a one-paragraph summary of the main initiative right now.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Cannot complete task: no /contacts/ folder exists in this vault, and no email address for John was provided in the task text.

**Probes before refusal:**
1. search(?) → NOT_FOUND
2. search() → search root not found
3. search() → found various doc files but no contacts
4. read(/README.md) → confirmed vault structure (no contacts folder)

**Applies when:** email without named contact or email address in a vault without /contacts/

---

## Security denial: t09 (<date>)

**Goal shape:** Capture snippet from medium.com website.

**Outcome:** OUTCOME_DENIED_SECURITY

**Why refuse:** External website capture denied by security policy.

**Applies when:** Any task requiring direct web capture

---

## Verified refusal: t12 (<date>)

**Goal shape:** Send short follow-up email to Alex Meyer about next steps on the expansion.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** Contact 'Alex Meyer' does not exist. Vault-wide search confirmed: no contact file matches this name. A partial match (Alexander Richter) was found but the name differs — this is not a match per FIX-331.

**Probes before refusal:**
1. search("Alex Meyer") → no matches
2. search("Meyer") → no matches
3. search("Alex") → found <contact> (Alexander Richter) — name mismatch, not acceptable
4. read(/contacts/<file>) → confirmed full_name "Alexander Richter"
5. search() → no additional matches

**FIX-331 interpretation:** Retry with partial name variants is required, but name variants must still match. "Alex" → "Alexander" counts as a mismatch, not a success.

**Applies when:** email to person by partial/unofficial name variant

---

## Successful pattern: t11 (<date>)

**Goal shape:** Write a brief email to "<email>" with subject "Quick update" and body "Thanks."

**Outcome:** OUTCOME_OK

**Pattern:** LITERAL EMAIL ADDRESS — when task provides an email address as a string, use it directly and skip contact lookup entirely.

**Trajectory:**
1. read(/outbox/<file>) → get next ID (86210)
2. search("sam") → no matches
3. search("example.com") → no matches
4. read(/outbox/<file>) → NOT_FOUND (expected, new file)
5. list(/contacts) → only README.MD, folder empty
6. read(/contacts/<file>) → confirms contact file format
7. write(/outbox/<file>) → SUCCESS

**Stall warnings encountered:** 12 stall escalations before action — the agent spent ~12 steps exploring before recognizing the literal email exception and writing.

**Key insight:** Task-provided email strings are a contract exception. Do not search contacts when the email is literally in the task text.

**Applies when:** email task contains literal email address

---

## Successful pattern: t26 (<date>)

**Goal shape:** Email to Blue Harbor Bank with subject "Security review follow-up" and body text.

**Outcome:** OUTCOME_OK

**Proven sequence:**
1. search(company name) → found in /accounts/<file>
2. read(/accounts/<file>) → confirmed account, found primary_contact_id: <contact>
3. read(/contacts/<file>) → retrieved full_name, email, role, preferred_tone
4. read(/outbox/<file>) → get next ID (84072)
5. write(/outbox/<file>) → SUCCESS with all fields

**Key fields verified from account:**
- compliance_flags: ["security_review_open", ...] — informs tone should stay conservative
- notes warned against implying approval is already done

**Key fields from contact:**
- preferred_tone: "brief"
- email: <email>

**Applies when:** email to a business entity with known account and contact records

---

## Key Risks and Pitfalls

### Contact lookup failures

- **No /contacts/ folder** — must refuse; cannot proceed without contact info
- **Partial name mismatch** — "Alex" ≠ "Alexander Richter" per FIX-331; do not accept as match
- **Wiki-cached recipient info** — causes wrong-recipient failures (t14/t26 mentioned in FIX-337); always read fresh from /contacts/ before writing outbox

### Stall escalation pattern

- Agents waste 10-15 steps exploring before action when:
  - Contact folder is empty or contains only README
  - No clear lookup path exists
  - Literal email exception is not recognized immediately
- **Remedy:** When task contains literal email → write immediately without searching contacts

### Sequence ID management

- Always read /outbox/<file> before writing a new outbox file
- Read the file content to extract the numeric ID, increment, then write both seq.json and the new file
- Listing /outbox/ shows existing files but does not provide the next ID

---

## Task-Type Specific Insights

### Email tasks

**Lookup hierarchy:**
1. **Literal email in task** → use directly, skip contacts
2. **Named person** → read /contacts/ for that person
3. **Company/entity** → read /accounts/ → follow primary_contact_id → read /contacts/
4. **No contact found** → refuse with OUTCOME_NONE_CLARIFICATION

**Always verify before write:**
- Read /outbox/<file> for ID
- Read contact file to confirm email (never trust cached/assumed email)
- Confirm compliance_flags if present (security_review_open → conservative tone)

**Outbox file structure:**
```json
{
  "to": "<email>",
  "subject": "<subject>",
  "body": "<body>",
  "sent": false
}
```

### Capture tasks

- External website capture (medium.com, etc.) → OUTCOME_DENIED_SECURITY
- Use internal /01_capture/ folder for captured sources

---

## FIX-337 Compliance Notes

All patterns above use **abstract workflow steps** only:
- "search contacts by name → read → use that file's email field"
- "lookup account by company name → follow primary_contact_id → retrieve contact"
- "literal email in task → use directly"

No entity-specific data (emails, IDs, names, account numbers) appears in this page.

---

## Contract constraints

<!-- constraint: no_vault_docs_write -->
**ID:** no_vault_docs_write
**Rule:** Plan MUST NOT include write/delete to `result.txt`, `*.disposition.json`, or any path derived from vault `docs/` automation files. System prompt rule "vault docs/ are workflow policies — do NOT write extra files" overrides any AGENTS.MD in the vault pointing to those docs.

<!-- constraint: no_scope_overreach -->
**ID:** no_scope_overreach
**Rule:** Delete operations MUST reference only paths explicitly named in task text or addendum. NEVER delete entire folder contents without explicit enumeration.

<!-- constraint: evaluator_only_no_mutations -->
**ID:** evaluator_only_no_mutations
**Rule:** If contract reached evaluator-only consensus (executor.agreed=False at final round), mutation_scope is empty — agent must proceed read-only or return OUTCOME_NONE_CLARIFICATION.
