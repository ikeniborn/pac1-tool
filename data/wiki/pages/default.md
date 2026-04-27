## Bulk Delete: Cards and Threads

### Proven Step Sequence
1. `list /02_distill/cards` — confirm files present, identify templates to skip
2. `list /02_distill/threads` — same
3. `delete` each non-template file individually
4. Verify only `_card-template.md` and `_thread-template.md` remain

### Key Rules
- **Never delete template files** (`_card-template.md`, `_thread-template.md`) unless explicitly asked
- Scope: "remove all cards and threads" means only `02_distill/cards/` and `02_distill/threads/` — nothing else in the repo
- "Let's start over" and "remove all captured cards and threads" are equivalent phrasings of the same scoped bulk-delete intent
- Both directories must be listed before any deletions begin — do not interleave list and delete across directories

---

## Single File Delete

### Proven Step Sequence
1. `list <parent-dir>` — confirm target exists before deleting
2. `delete <file>` — execute deletion
3. Verify target removed; confirm no collateral damage

### Key Rules
- Always list the directory first to confirm the exact filename before deletion
- "Don't touch anything else" is a hard constraint — no side-effect writes or renames
- "Discard entirely" and "discard [file] entirely" are equivalent to delete — no archiving, renaming, or moving implied
- Applies to both cards and threads; phrases like "Discard thread X entirely" follow identical step pattern

---

## Truncated / Ambiguous Task

### Pitfall
- Task `t08` was truncated (`"Create captur"`); agent correctly halted and requested clarification rather than guessing intent
- Task `t18` contained truncation marker (`'REVIEW INBOX...'`); agent correctly halted after initial exploration rather than inventing action
- Task `t20` was vague without specific directive (`'HANDLE INBOX!'`); agent correctly halted and requested clarification on intended outcome
- Task `t37` was truncated with ellipsis (`"review the inbox..."`); agent correctly halted after list and requested complete instruction
- **Rule:** If a task instruction appears cut off mid-sentence, **incomplete with ellipsis**, or **vague without concrete action verbs**, halt immediately and ask for complete instruction — do not infer intent or proceed with assumed actions

---

## Create File from Schema (Invoice / Structured Record)

### Proven Step Sequence
1. `list <target-dir>` — check for duplicates and confirm directory exists
2. `read README.MD` (or schema file) in that directory — extract required JSON shape
3. `write <target-dir>/<ID>.json` — use schema-conformant structure with user-provided values
4. `read <target-dir>/<ID>.json` — verify written content matches task requirements

### Key Rules
- Always check for a `README.MD` or schema document before writing a new structured file
- Confirm no duplicate file exists before writing
- List step and read step can be done in either order; both must complete before writing
- **Do not attempt to `read` a file path before writing it** — NOT_FOUND errors on the destination path are expected and should not trigger retries; proceed to `list` then `write`

### Pitfall
- Agent repeatedly attempted to `read` the not-yet-created target file (`SR-13.json`), triggering multiple NOT_FOUND errors before proceeding correctly
- Task `t10` confirmed: two NOT_FOUND attempts on `/my-invoices/SR-13.json` before agent pivoted to schema read + write — this is expected behavior for schema-driven creates
- **Rule:** A NOT_FOUND error on the write destination is expected; the second occurrence should trigger immediate pivot to `list` + schema read + `write`

---

## Bug Fix: Prefix / Config Regression

### Proven Step Sequence
1. `read audit.json` (or equivalent drift report) — identify canonical value and regression window
2. `read` representative data records to confirm correct prefix in production data
3. `read` the specific config file (e.g. `lane_a.json`) — confirm the incorrect value
4. `write` corrected config with minimal diff

### Key Rules
- Ground the fix in both the audit report **and** raw data records — audit alone may be stale
- Scope: fix only the identified regression; do not refactor unrelated fields
- **Stall guard:** If 5+ steps pass without a write/delete/move, re-evaluate — likely have enough context to act
- The canonical prefix is determinable after reading audit + 1–2 data records; reading more records beyond that is over-reading
- Reading the config file to confirm the bad value can happen before or after reading data records — both must complete before writing
- Pipeline config docs (`processing/README.MD`) are optional if the emitter file is already identified from the audit

### Pitfall
- Over-reading: agent stalled at 6–7 read steps before writing; the correct value was determinable after step 2
- Stall warnings fired twice (at steps 6 and 7) before the agent acted — a single stall warning should be treated as a hard trigger to write immediately if the fix is known
- Reading `processing/README.MD` to identify the emitter is unnecessary if `audit.json` already names the component
- Task `t31` confirmed: 4-step sequence (1 audit read + 1 data read + 1 config read + 1 write) completes safely without triggering stall guard

---

## Search and Retrieve: Single Record

### Proven Step Sequence
1. `search <query-term>` — locate record path matching criteria
2. `read <identified-path>` — retrieve full record
3. Extract and return requested field(s)

### Key Rules
- Use `search` to identify record path before reading; do not guess paths
- For single-criterion queries (e.g., "email of Johanna Schäfer"), search + read one path is sufficient
- Return only the requested field unless full context required

### Proven Example
- Task `t16`: search "Schäfer" → located `contacts/<contact>.json` → read record → returned email address

---

## Capture: Create Unstructured File

### Proven Step Sequence
1. `list <target-dir>` — confirm directory exists
2. `write <target-file>` — create file with snippet, source attribution, and metadata
3. (Optional) Verify write if confirmation needed

### Key Rules
- No schema validation needed for text/snippet captures
- Include source attribution (URL, date, author context) in the file
- Directory must exist; no NOT_FOUND error expected
- Single list + write pattern suffices; no schema read required

### Proven Example
- Task `t33`: listed `/01_capture/influential` → wrote `2026-04-04__prompting-review-snippet.md` with snippet and source attribution

---

## Search with Cross-Verification: Multi-Record Query

### Proven Step Sequence
1. `list <candidate-dir>` — enumerate all possible records
2. `read` each candidate record to inspect criteria (location, sector, focus, etc.)
3. Identify unique match against all criteria
4. Return answer with confidence: "unique match is X" or report if multiple/zero matches found

### Key Rules
- When criteria are specific and uniqueness is required, cross-verify **all** candidates before claiming a unique answer
- Do not stop at first partial match; verify uniqueness across the full set
- Document which criteria matched in your reasoning (auditable)
- If multiple records match or no match found, report explicitly rather than guessing

### Proven Example
- Task `t34`: listed all 10 accounts → read all 10 → cross-verified Berlin + digital-health + triage-backlog focus → identified unique match `<account>` (Nordlicht Health)

---
