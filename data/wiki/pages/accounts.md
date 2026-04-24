# Workflow Wiki — AI File-System Agent

> ## ⚠️ Do NOT Mutate Fields the Task Didn't Name
> Only write fields the current task explicitly instructs you to change. On reschedule, rename, or status-change tasks, leave every other field exactly as read. Never "normalize," "refresh," or "sync" sibling fields (e.g., `account_manager`, `industry`) just because they appeared in the read payload. Field-diff checks will fail if untouched fields are rewritten.

## Proven Step Sequences (OUTCOME_OK)

### Read-then-Write (single account mutation)
1. `read` the target account file → verify=payload parses and contains the field to be changed.
2. Construct the write payload by copying the read result and mutating **only** the task-named field.
3. `write` the target file → verify=`WRITTEN: <path>` confirmation returned.

### Read-only lookup (single or multi-account scan)
1. `read` each referenced account file in sequence → verify=each payload parses.
2. Aggregate the requested fields in-memory; do not issue writes unless the task asks for them.

## Key Risks & Pitfalls

- **Silent field drift on write-back.** Echoing the full read payload into a write re-serializes every field; if any value was stale or differs from canonical, it gets overwritten. Mitigation: diff the outgoing payload against the read result and confirm only task-named fields differ.
- **Cross-task stale assumptions.** The same account path can hold different values across tasks — the `account_manager` for a given file has been directly observed to change between task runs. Always re-`read` at the start of the task; never reuse values cached from a prior task or from this wiki.
- **Over-broad "confirmed writable fields" lists.** Any wiki line that enumerates a fixed set of writable fields tempts the agent to touch them all. Writability is per-task, defined by the task instructions — not by the schema.
- **Adjacent-field cleanup.** Do not "fix" a field that looks wrong unless the task names it. Surface the discrepancy instead.
- **Treating `account_manager` as stable identity.** It is a mutable attribute, not a key. Do not use it to deduplicate reads, correlate files, or short-circuit a lookup.

## Task-Type Insights & Shortcuts

### Mutation tasks (rename / reschedule / status change)
- Minimum viable diff: one field changed, all others byte-identical to the read.
- If the task names exactly one field, the write payload should differ from the read in exactly that one key.
- Never carry a sibling field (e.g., `account_manager`) over from memory or a prior task — always source it from the fresh read and leave it untouched.

### Lookup / reporting tasks
- No writes. A write on a pure-lookup task is always a defect.
- Batch reads are fine; order is insignificant unless the task specifies it.
- Single-file lookups still require a fresh `read`; do not answer from recalled values.

### Cross-account tasks
- Read all referenced files before composing any output; partial reads yield incomplete reports.
- Treat each file independently — a shared `account_manager` value across files is coincidence, not a key, and must not be used to skip reads.
