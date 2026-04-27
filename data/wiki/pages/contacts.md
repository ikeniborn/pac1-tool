## Contact File Access Patterns

### Proven Step Sequences

**Reading a contact by known ID**
1. Construct path as `/contacts/<file> where `<id>` follows the `cont_NNN` or `mgr_NNN` naming scheme.
2. Issue a single `read` call; parse the returned JSON for `id`, `account_id`, `role`, and `email` fields.
3. If the file is found, proceed with downstream task using extracted fields.

**Reading multiple contacts in one task**
1. Identify all required contact IDs upfront.
2. Read each file sequentially or in batch; collect results before proceeding.
3. Cross-reference `account_id` values when joining contacts to accounts.

---

### Key Risks and Pitfalls

- **Name-based paths fail.** Using a human-readable name (e.g., `alice-tran.json`) instead of the canonical `cont_NNN` or `mgr_NNN` identifier causes `NOT_FOUND` errors. Always resolve to the canonical ID before constructing a path.
- **ID namespace split.** Contacts may live under either `cont_NNN` or `mgr_NNN` prefixes. Assuming all contacts use `cont_NNN` will miss manager-type records.
- **Inconsistent field data.** The same `cont_NNN` file can return different `full_name` or `role` values across task runs — treat contact data as mutable; do not cache identity fields across sessions.
- **Truncated reads.** Several fragment reads end mid-field (e.g., `"email": "`), suggesting the file or read buffer may be larger than the preview. Always consume the full JSON before extracting fields.

---

### Task-Type Specific Insights

**Contact lookup tasks**
- Canonical file pattern: `/contacts/<file> — always use ID-based paths.
- `account_id` is reliably present and suitable as a join key to account records.
- `role` field is useful for routing (e.g., filtering by `Operations Director`, `Head of Engineering`) but should not be assumed stable across runs.

**Account-to-contact resolution**
- No directory listing shortcut is documented; iterate over known ID ranges or maintain a separate index if bulk enumeration is needed.
- `mgr_NNN` records are stored in the same `/contacts/<file> directory as `cont_NNN` records — treat the directory as a mixed namespace.
