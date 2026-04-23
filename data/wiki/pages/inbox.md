## Inbox Processing

### Proven Step Sequence (OUTCOME_OK)

**Standard inbox-to-capture-distill flow:**

1. Read the inbox source file — confirm content and target folder
2. Write capture file to `/01_capture/<folder>/YYYY-MM-DD__<slug>.md`
3. Create distill card at `/02_distill/cards/YYYY-MM-DD__<slug>.md`
4. Check for an existing thread file that the content relates to; if found, append a new bullet/entry rather than creating a duplicate thread
5. Delete the original inbox file only after all writes are confirmed

**Outbox message flow (email / reply tasks):**

1. Read inbox message to extract intent, recipient, and any required metadata
2. Verify sender domain or identity against known contact records before acting
3. Locate the referenced resource (e.g. latest invoice, document) by querying the relevant data store — do not guess or infer the record without a lookup
4. Read `/outbox/seq.json` to obtain the next available slot ID
5. Write composed message to `/outbox/<id>.json`
6. Write any required reminder or follow-up record (e.g. `/reminders/rem_<n>.json`) before or alongside the outbox write
7. Update `/outbox/seq.json` with incremented ID if required by convention

**Read-only lookup (no writes):**

1. List the relevant capture folder to retrieve filenames and embedded dates
2. Compute the target date from the query offset
3. Match against available filenames; report clearly if no match exists

---

## Key Risks and Pitfalls

- **Deleting before confirming writes** — always verify all destination files are written before issuing the delete on the source.
- **Duplicate thread creation** — before writing a new thread file, check whether a matching thread already exists; prefer appending to existing threads over creating near-duplicates.
- **Date arithmetic errors on lookups** — calendar offset queries can be off-by-one or require vault-specific adjustments; verify computed dates against actual filenames before concluding "not found."
- **OTP / credential values in fragments** — raw inbox messages may contain authentication tokens or sensitive identifiers; these are task inputs only and must not be surfaced in curated documentation or passed downstream outside their intended operation.
- **Scope creep on diff** — tasks that say "keep the diff focused" mean: write only the files explicitly required; do not touch unrelated vault files.
- **Acting on unverified sender identity** — for requests that trigger data retrieval or resend (e.g. invoice resend, document sharing), verify the sender's domain or contact record before fulfilling the request; do not rely solely on the display name in the `From:` field.
- **Locating "latest" records without a lookup** — requests for the most recent invoice, file, or entry must be resolved by querying the data store; never assume which record is latest based on the message text alone.
- **Missing reminder or follow-up write** — some outbox flows also require a companion reminder record; check task requirements before closing the sequence.

---

## Task-Type Insights and Shortcuts

### `inbox` — Capture + Distill

- Folder routing is explicit in the task (`'influential'`, `'cards'`, etc.); use it verbatim as the subdirectory path.
- The slug for all three files (inbox, capture, distill card) is typically identical — reuse it directly.
- A single inbox item often maps to **both** a card and a thread update; check for the thread before writing.

### `inbox` — Outbox Composition

- Always read `seq.json` first; the slot ID determines the output filename.
- The inbox message is the sole source of truth for recipient, subject, and body — do not infer beyond what is stated.
- For resource-resend requests (invoice, document, attachment): resolve "latest" or "most recent" by scanning the relevant data store with any account/contact identifier mentioned in the message.
- Confirmed pattern: read inbox → verify sender → lookup referenced resource → read `seq.json` → write outbox → write reminder (if required) → delete transient credential files (if any).
- Companion writes (e.g. reminders) should be completed in the same pass as the outbox write — do not defer them to a follow-up task.

### `inbox` — Lookup / Query

- List the target folder first; compute the date second; match third. Avoid computing dates in isolation before seeing what files actually exist.
- If no file matches the computed date, report "no match found" rather than guessing the nearest entry.
