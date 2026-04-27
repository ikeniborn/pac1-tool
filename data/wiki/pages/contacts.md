## Contact File Access Patterns

### Proven Step Sequences

- **Single-contact lookup:** `read /contacts/<file> → parse `account_id`, `role`, and contact fields in one pass → use `account_id` to join with account data if needed.
- **Multi-contact batch lookup:** Issue all required `read /contacts/<file> calls before processing any results; avoids interleaved reads that complicate error handling.
- **Manager vs. contact distinction:** Manager records live under `mgr_NNN.json`; general contacts under `cont_NNN.json`. Always resolve the correct prefix before reading.

### Key Risks and Pitfalls

- **Stale or conflicting data across files:** The same logical ID has been observed returning different `full_name` and `role` values across tasks — confirmed for multiple IDs. Do **not** cache contact records between tasks; always re-read from the file system for each task execution.
- **Truncated read results — email field especially:** Multiple reads return visibly truncated JSON, with email fields consistently cut off mid-string across both contact and manager file types. Validate that all required fields are fully present before consuming the record; retry or flag for review if truncated.
- **Prefix mismatch:** Confusing manager files with contact files leads to wrong-record reads. Derive the filename prefix from the source that provided the ID (e.g., account record, task parameter), not from assumptions about role names.
- **Role label is not a reliable proxy for file prefix:** Role labels appear across multiple file types and vary within a single file type across reads. Use the explicit file path, not the role string, to determine record type.
- **Manager records exhibit the same field drift as contact records:** Apply the same no-cache, re-read-each-task policy to all contact file types.

### Task-Type Specific Insights

- **Account-to-contact resolution:** The `account_id` field inside a contact file is the reliable join key back to account data; the `id` field is the canonical contact key for downstream references.
- **Batch tasks reading multiple contacts:** Collect all contact IDs up front, read all files in sequence, then process — this makes partial-failure detection straightforward.
- **No persistent contact registry needed:** Because multiple fields can change between reads, maintain no long-lived in-memory registry; treat each read as authoritative only for the current task scope.
- **Field-level instability spans all mutable fields:** Observed drift spans `full_name`, `role`, and `email`. Only `id` and `account_id` are stable join keys.
- **Same-day multi-read drift is real:** Multiple reads of the same file on the same date have returned distinct field values. Every read must be treated as potentially different from a prior read in the same session.
