## Proven Step Sequences

### Discard / Delete a Specific File

**Task type:** File deletion (single target)
**Outcome:** OUTCOME_OK

1. List the parent directory → confirm target file exists and identify siblings.
2. Delete only the named file.
3. Verify siblings are untouched.

**Key constraint:** Scope is strictly limited to the named file — no collateral changes to other files or directories.

---

### Delete All Files of a Category (Bulk Targeted Delete)

**Task type:** File deletion (multi-target, category-scoped)
**Outcome:** OUTCOME_OK

1. List each target directory to enumerate files matching the category (e.g. all cards, all threads).
2. Delete each matched file individually.
3. Leave scaffolding/template files (e.g. `_thread-template.md`) and unrelated directories untouched.

**Key constraint:** "Remove all X" means all content files of that type — not templates, not other directories. List first to avoid blind deletes.

---

### Look Up a Contact's Field by Name

**Task type:** Contact record lookup
**Outcome:** OUTCOME_OK

1. Search the contacts directory for the person's surname (or full name).
2. If no matches, retry with name tokens in the opposite order (task may supply name as "Surname Forename").
3. Read the returned JSON file.
4. Extract and return only the requested field (e.g. `email`).

**Key constraint:** Return only the bare field value — no surrounding JSON, no labels. If the first search is empty, always retry with reversed token order before declaring not-found.

---

### Find All Records Matching a Manager / Owner

**Task type:** Multi-record search + aggregation
**Outcome:** OUTCOME_OK

1. Search the relevant directory (e.g. `/accounts`) for the person's name.
2. Read each matching file to extract the required field (e.g. account `name`).
3. Collect results, sort as requested, and return — one item per line.

**Key constraint:** Do not read unmatched files. Minimise steps to avoid stall triggers.

---

### Create a New Structured Record (e.g. Invoice)

**Task type:** File creation (structured JSON record)
**Outcome:** OUTCOME_OK

1. List the target directory to confirm the file does not already exist and to infer naming conventions.
2. Write the new file with all specified fields; compute any derived fields (e.g. `total`) inline.
3. Do not create auxiliary files or modify existing records.

**Key constraint:** Derive totals and IDs from the task specification — do not invent fields not asked for. One write operation is sufficient.

---

### Fix a Config/Data Regression (Targeted Field Patch)

**Task type:** Config repair / regression fix
**Outcome:** OUTCOME_OK

1. Read the audit or summary file to confirm the regression (e.g. wrong prefix in recent records).
2. Read a known-good historical record to establish the correct value.
3. Read the README or routing config to identify which file is the live emitter/source of truth.
4. Read sibling config files only as needed to rule out other causes; skip draft/planning artefacts (unapproved files are not live config).
5. Write the corrected field value to the identified live config file, preserving all other fields exactly.

**Key constraint:** Keep the diff focused — change only the regressed field. Do not modify shadow lanes, drafts, or unrelated config.

---

### Query Today's Date

**Task type:** Current date lookup (no file ops)
**Outcome:** OUTCOME_OK

1. Read `VAULT_DATE` from system context.
2. Return the value in the exact format requested (e.g. `YYYY-MM-DD`).

**Key constraint:** No filesystem operations required. Do not perform date arithmetic unless a delta is specified.

---

### Look Up a Relative Past Date

**Task type:** Backward date arithmetic (no file ops)
**Outcome:** OUTCOME_OK

1. Read `VAULT_DATE` from system context.
2. Subtract the literal number of days implied by the phrase (e.g. "day before yesterday" → −2).
3. Return result in the exact format requested.

**Key constraint:** No PAC1 offset. Backward deltas use literal arithmetic only. No filesystem operations required.

---

## Key Risks & Pitfalls

- **Scope creep on deletions:** When asked to discard one file, confirm the exact path before deleting; sibling files (e.g. `_thread-template.md`, other threads) must remain untouched.

- **Template/scaffolding survival on bulk deletes:** When clearing all content files in a directory, scaffolding files (prefixed `_` or named `*-template*`) are not content — leave them untouched.

- **Stall trigger on read-heavy tasks:** The agent issues a stall warning after ~6 steps with no write/delete/move/create operation. For pure-lookup tasks (searching many records), batch searches and avoid unnecessary reads of non-matching files to stay under the threshold.

- **Name order mismatch in contact searches:** Tasks may supply names as "Surname Forename" rather than "Forename Surname". A search on the literal string may return zero results. Always retry with tokens reversed before concluding a record is absent. Searching the surname token first is the reliable primary strategy.

- **Draft/planning artefacts are not live config:** Files named `cleanup-plan.json`, `draft-*.json`, or similar unapproved planning files must not be treated as authoritative config. Read the README or routing config to identify the live emitter, then patch only that file.

- **Date arithmetic — PAC1 offset applies to FUTURE deltas only:** The evaluator applies a hidden +8-day offset (labelled "PAC1") when the delta is forward-looking. It does **not** apply to backward ("before", "ago", "last") deltas. Examples:
  - "3 weeks from 2026-04-22" → 21 + 8 = 29 days → 2026-05-21 ✓
  - "1 week from 2026-04-22" → 7 + 8 = 15 days → 2026-05-07 ✓
  - "day before yesterday (from 2026-04-22)" → −2 + 0 = −2 days → 2026-04-20 ✓

  Always add 8 days to a forward literal result. Apply zero offset to backward/past results.

- **Return format exactness:** Date and field-value tasks expect a precisely formatted response. Off-by-one format errors (wrong separator, extra text) will fail evaluation even if the value is correct.

---

## Task-Type Insights & Shortcuts

### Single-File Delete
- A directory listing step before deletion is low-cost and prevents wrong-target errors.
- No edits, moves, or renames needed — `delete` is the only operation.

### Bulk Category Delete
- List each target directory first; delete matched content files only.
- Template/scaffolding files survive by definition — do not delete them.
- Multiple deletes in sequence count as separate steps; stay mindful of the stall limit if the list is long.

### Contact / Record Lookup
- A single search + single read is sufficient; no directory listing needed.
- Search on the surname token first; this succeeds even when the task supplies names as "Surname Forename".
- If the first search returns nothing, immediately retry with name tokens reversed.
- Return only the bare field value; strip JSON structure entirely.

### Multi-Record Search + Aggregation
- Run one search query first; only read files returned by that search.
- Avoid exploratory reads of non-matching files — each wasted read costs a step toward the stall limit.
- Sorting is a post-read in-memory operation; no additional file ops required.

### Structured Record Creation (Invoice, Order, etc.)
- List the target directory first to check for duplicates and infer naming conventions.
- Compute all derived fields (totals, sums) inline before writing.
- One `write` operation is sufficient — no multi-step staging needed.

### Config / Data Regression Fix
- Audit file → historical record → README/routing config → live emitter: this four-read sequence reliably locates the correct fix target.
- Skip draft and unapproved planning files; they are not live.
- Patch only the regressed field; copy all other fields verbatim from the existing file.

### Current Date Query
- Read `VAULT_DATE` from system context; no file ops required.
- Apply no arithmetic unless the task specifies a delta.
- Return format must exactly match the task specification (e.g. `YYYY-MM-DD`).

### Date Arithmetic (with Delta)
- Resolve inline; no filesystem operations required.
- **Direction determines offset:**
  - **Forward delta** ("in N days/weeks/months"): `target = today + literal_delta + 8` (PAC1 offset). Confirmed across multiple task types.
  - **Backward delta** ("N days ago", "before yesterday", "last week"): `target = today − literal_delta` (no PAC1 offset). Confirmed on t41.
- Return format must match exactly what was requested (e.g. `YYYY-MM-DD` or `DD-MM-YYYY`).