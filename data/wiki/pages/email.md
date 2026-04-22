## Email Task Workflows

### Proven Step Sequence — Send Email to Named Account

**Task type:** `email` | **Outcome:** `OUTCOME_OK`

1. Search accounts for the named account (e.g. "Software account with AI data-flow review") → note `acct_XXX`
2. Read `/accounts/acct_XXX.json` to confirm identity, industry, and status
3. Search contacts for `account_id: acct_XXX` → note `cont_XXX`
4. Read `/contacts/cont_XXX.json` to extract recipient email address
5. Read `/outbox/seq.json` → extract next message ID (e.g. `84620`)
6. Write `/outbox/<id>.json` with full email payload (to, subject, body)
7. *(Optional)* Update `/outbox/seq.json` if sequence requires incrementing

**Concrete example:**
- "Software account with AI data-flow review" → `Aperture AI Labs` (`acct_009`)
- Primary contact → `Vera Sanders` (`cont_009`), `vera.sanders@aperture-ai-labs.example.com`
- Seq slot → `84620` → wrote `/outbox/84620.json`

---

## Key Risks & Pitfalls

### Stall Traps (Critical)
- **Do not chain more than ~5 reads without writing anything.** The environment enforces a stall limit and will interrupt execution with warnings.
- Write to `/outbox/<id>.json` as soon as the recipient email and message ID are known — do not defer the write.

### Account Lookup Ambiguity
- Account descriptions like "Software account" are not direct name matches. Search by industry (`software`) or keyword, then read candidate accounts to confirm.
- Do not assume the first search result is correct; verify via the account record.

### Contact Resolution
- Accounts do not embed contact emails directly. Always resolve via `/contacts/` using `account_id`.
- If a search returns multiple contacts for an account, prefer the one whose role matches the task context (e.g. security review → QA Lead, technical lead).

### Sequence ID Management
- Always read `/outbox/seq.json` immediately before writing the email file — do not reuse a cached or assumed ID.

---

## Task-Type Insights & Shortcuts

### Email
- **Shortcut:** Search contacts index directly for `account_id` rather than scanning all contact files individually.
- **Pattern:** `search → read account → search contacts → read contact → read seq → write outbox` is the minimal confirmed path (6 steps).
- Subject and body truncation in task descriptions is intentional; reconstruct the intended full message from context clues.
- The outbox file name is the numeric ID from `seq.json` (e.g. `84620.json`), not the contact or account ID.