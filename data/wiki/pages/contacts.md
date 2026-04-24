## Workflow Patterns

### Reading Contact Records
- Contact records live under `/contacts/<file> and are stored as individual JSON files.
- File naming follows two conventions:
  - `cont_NNN.json` for standard contact entries
  - `mgr_NNN.json` for manager-tier entries
- Each record is keyed by an `account_id` that links the contact to an account namespace (`acct_NNN`).
- Standard schema fields observed: `id`, `account_id`, `full_name`, `role`, `email`.
- The `role` field is free-form and may describe seniority (e.g., "Head of ...", "Operations Director"), not just function — a senior/managerial title can still live in a `cont_NNN.json` file.
- Conversely, an `mgr_NNN.json` file may carry a non-executive role string (e.g., "Account Manager") — prefix signals tier, not title.
- Field order in raw files is consistent: `id`, `account_id`, `full_name`, `role`, `email` — `email` is reliably the trailing field.

### Proven Step Sequence (Lookup by ID)
1. Resolve the contact ID (`cont_NNN` or `mgr_NNN`) → verify: ID matches file-name convention.
2. Read `/contacts/<file> directly → verify: JSON parses and contains the expected schema fields.
3. Extract only the field(s) required by the task → verify: no unrelated fields are surfaced.
4. If the required field is `email` (always trailing), confirm the read was not truncated before returning → verify: closing `}` is present.

## Risks and Pitfalls

- **Prefix ambiguity:** Manager contacts use `mgr_` rather than `cont_`. Do not assume `cont_` for every contact lookup — check both prefixes when an ID is not given.
- **Title ≠ prefix:** A senior title (e.g., "Head of X", "Director") does not imply an `mgr_` file, and an `mgr_` file may hold a non-senior role. Trust the ID/file prefix, not the `role` string, when locating the record.
- **Account ID ≠ Contact ID:** `account_id` and `id` share the numeric suffix but are distinct namespaces (`acct_` vs `cont_`/`mgr_`). Do not substitute one for the other in path construction.
- **Truncated reads:** Raw reads are frequently cut off mid-field — the `email` value is the most common casualty since it is always the trailing field. Re-read the full file before relying on `email`; never infer or reconstruct a truncated value.
- **PII handling:** Contact files contain personal data (names, emails). Surface only the minimum needed; avoid building registries or aggregate dumps of personal fields.

## Task-Type Insights

### Direct-Lookup Tasks
- Prefer a single targeted read of `/contacts/<file> over directory listings when the ID is known.
- The `role` field is the fastest discriminator for filtering by function or seniority.
- Numeric suffixes across both prefixes are independent — a `cont_NNN` and `mgr_NNN` with the same suffix can coexist and point to different accounts.

### Shortcuts
- The `_NNN` suffix is a reliable join key between `/contacts/<file> and `/accounts/<file> — use it to pivot without enumerating either directory.
- When uncertain whether a contact is managerial, attempt `mgr_NNN.json` before falling back to a broader directory scan.
- If a truncated read hides the trailing field, re-issue the read with a larger range rather than inferring the value.
- Expect `email` to be the truncation victim by default — budget read size accordingly on first attempt.
