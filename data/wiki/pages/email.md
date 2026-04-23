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

**Concrete examples:**
- "Software account with AI data-flow review" → `Aperture AI Labs` (`acct_009`)
  - Primary contact (Operations Director) → `Casper Timmers` (`cont_009`), `casper.timmers@aperture-ai-labs.example.com`
  - Head of Product → `Vera Sanders` (contact ID unverified; email `vera.sanders@aperture-ai-labs.example.com` confirmed deliverable)
  - Head of Engineering → `Leon Kooistra` (contact ID unverified)
  - Seq slots used: `84025`, `84195`, `84620`, `84897`
- "Blue Harbor Bank" → `acct_004`
  - Contact by name → `Roel Boer` (`cont_004`), `roel.boer@blue-harbor-bank.example.com`
  - Contact by role → `Lois Maas` (`cont_004`, Head of Engineering), `lois.maas@blue-harbor-bank.example.com`
  - Seq slots used: `84110`, `84253`
- "GreenGrid Energy" → `acct_005`
  - Contact by name → `Katharina Krause` (`cont_005`, Product Manager)
  - Seq slot used: `84506`

---

### Proven Step Sequence — Send Email to Wiki-Known Account & Contact

**Task type:** `email` | **Outcome:** `OUTCOME_OK`

1. Read `/outbox/seq.json` → extract next message ID
2. Write `/outbox/<id>.json` using the cached email address from the wiki

> **Shortcut:** When both the account and a suitable contact are already resolved in the wiki, skip all lookup steps. Minimal path is 2 steps.

**Concrete examples:**
- Aperture AI Labs, security review follow-up → `vera.sanders@aperture-ai-labs.example.com` → slot `84025` (t14), slot `84195` (t26)

---

### Proven Step Sequence — Send Email to Literal Address

**Task type:** `email` | **Outcome:** `OUTCOME_OK`

1. Read `/outbox/seq.json` → extract next message ID
2. Write `/outbox/<id>.json` with email payload using the literal address from the task

**Concrete examples:**
- `priya@example.com`, subject `Friday status`, body `Quick note.` → slot `84544`
- `priya@example.com`, subject `Project check-in`, body `Brief update.` → slot `87018`

> **Shortcut:** When a full email address is explicitly provided in the task, skip all account/contact lookup steps. Minimal path is 2 steps: read seq → write outbox.

---

### Proven Step Sequence — Lookup Contact Email (No Send)

**Task type:** `email` (lookup only) | **Outcome:** `OUTCOME_OK`

1. Search accounts for the named account → note `acct_XXX`
2. Read `/accounts/acct_XXX.json` to confirm identity
3. Search contacts for `account_id: acct_XXX` → read `/contacts/cont_XXX.json`
4. Return the email field — no outbox write required

**Concrete example:**
- "German AI-insights add-on subscriber Aperture account" → `acct_009` (Aperture AI Labs)
- Primary contact → `Vera Sanders`, `vera.sanders@aperture-ai-labs.example.com`

---

## Key Risks & Pitfalls

### Stall Traps (Critical)
- **Do not chain more than ~5 reads without writing anything.** The environment enforces a stall limit and will interrupt execution with warnings.
- Write to `/outbox/<id>.json` as soon as the recipient email and message ID are known — do not defer the write.

### Account Lookup Ambiguity
- Account descriptions like "Software account" are not direct name matches. Search by industry (`software`) or keyword, then read candidate accounts to confirm.
- Do not assume the first search result is correct; verify via the account record.
- Descriptors like "German AI-insights add-on subscriber" are qualifier clues — search by or read directly by the core name (e.g. `acct_009`) and confirm via account fields.
- For wiki-known account IDs, go directly to `read /accounts/acct_XXX.json` — skip the search step entirely.

### Contact Resolution
- Accounts do not embed contact emails directly. Always resolve via `/contacts/` using `account_id`.
- If a search returns multiple contacts for an account, prefer the one whose role matches the task context (e.g. security review → Operations Director or Head of Engineering; product question → Head of Product).
- Named contacts (e.g. "Krause Katharina") can be searched directly by surname in the contacts index — no need to go through the account first.
- **Wiki contact-ID accuracy:** Verify contact IDs on first use per task. Example: `cont_009` resolves to Casper Timmers (Operations Director), not Vera Sanders — t35 confirmed via direct read. Vera Sanders' contact ID remains unverified in the filesystem; her email address (`vera.sanders@aperture-ai-labs.example.com`) is confirmed deliverable from prior tasks but should not be assumed to equal `cont_009`.

### Sequence ID Management
- Always read `/outbox/seq.json` immediately before writing the email file — do not reuse a cached or assumed ID.
- The outbox file name is the numeric ID from `seq.json` (e.g. `84544.json`), not the contact or account ID.

### Wiki Cache Reuse
- When a prior task has already resolved an account/contact, reuse that mapping directly instead of re-searching. Confirmed effective in `t14`, `t26` (Aperture AI Labs → vera.sanders, 2-step path).
- Treat contact ID mappings as provisional until verified by a direct file read in the current task session.

---

## Task-Type Insights & Shortcuts

### Email
- **Shortcut — literal address:** If the task supplies a full email address, skip all lookup steps. Minimal path: `read seq → write outbox` (2 steps).
- **Shortcut — wiki-known account + contact:** If both account and a suitable contact are cached in the wiki, skip all lookup steps. Minimal path: `read seq → write outbox` (2 steps).
- **Shortcut — wiki-known account, unknown contact:** Go directly to `read /accounts/acct_XXX.json` (skip search), then resolve contact. Saves one search step.
- **Shortcut — contact by name:** Search the contacts index directly by surname when the task names a specific individual. Faster than going `account → contacts`.
- **Minimal confirmed paths:**
  - Literal address: `read seq → write outbox` (2 steps)
  - Wiki-known account + wiki-known contact: `read seq → write outbox` (2 steps)
  - Wiki-known account, unknown contact: `read account → search/read contact → read seq → write outbox` (4 steps)
  - Unknown account, unknown contact: `search account → read account → search contacts → read contact → read seq → write outbox` (6 steps)
- Subject and body truncation in task descriptions is intentional; reconstruct the intended full message from context clues.

### Known Account & Contact Registry

| Account | `acct_id` | Contact | `cont_id` | Role | Email |
|---|---|---|---|---|---|
| Aperture AI Labs | `acct_009` | Casper Timmers | `cont_009` | Operations Director | `casper.timmers@aperture-ai-labs.example.com` |
| Aperture AI Labs | `acct_009` | Vera Sanders | unverified | Head of Product | `vera.sanders@aperture-ai-labs.example.com` |
| Aperture AI Labs | `acct_009` | Leon Kooistra | unverified | Head of Engineering | — |
| Blue Harbor Bank | `acct_004` | Roel Boer | `cont_004` | — | `roel.boer@blue-harbor-bank.example.com` |
| Blue Harbor Bank | `acct_004` | Lois Maas | `cont_004` | Head of Engineering | `lois.maas@blue-harbor-bank.example.com` |
| GreenGrid Energy | `acct_005` | Katharina Krause | `cont_005` | Product Manager | — |