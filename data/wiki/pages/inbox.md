## Inbox Task Workflows

### Invoice Resend Request — Proven Step Sequence

**Task type:** `inbox` | **Outcome:** `OUTCOME_OK`

**Pattern:** Contact requests resend of their latest invoice.

**Proven steps:**
1. Read the inbox message to extract: sender name, described account, and request type.
2. Search `contacts/` for the sender's name or email to resolve `account_id`.
3. Query `my-invoices/` filtered by `account_id`; select the invoice with the latest `issued_on` date.
4. Read `/outbox/<file> to obtain the next outbox sequence ID.
5. Write `/outbox/<file> containing the reply email (recipient, subject, body) and the invoice as attachment.

**Key shortcut:** The sender's contact record is the fastest bridge from name → `account_id` → invoice. Skip account-notes files unless the contact lookup fails.

---

## Risks & Pitfalls

- **Stalling on reads without writing:** The agent accumulated 13 read/search steps before producing any output. Act as soon as the data needed for the write is available — do not continue exploring once `account_id`, latest invoice, and `seq_id` are in hand.
- **Searching notes files first:** Account notes (e.g. `/01_notes/`) are narrative and slow to parse. Prefer structured lookups (`contacts/`, `my-invoices/`) for identity and billing resolution.
- **Repeated failed searches before pivoting:** Two consecutive empty search results should trigger an immediate strategy change (e.g. try a different search term or read the file directly).
- **Reading `seq.json` too early or too late:** Read it immediately before writing to outbox to avoid ID drift; do not defer it to the end after other stalls have already occurred.

---

## Task-Type Insights

### `inbox` — General

- Resolve the sender to a contact record before doing anything else; `account_id` unlocks all downstream lookups.
- "Latest invoice" means highest `issued_on` date for the resolved `account_id`.
- Outbox workflow: read `seq.json` → increment or use current ID → write `<id>.json`.
- Incomplete inbox tasks (no `OUTCOME_OK`) carry no learnable step sequence — skip them in future synthesis.
