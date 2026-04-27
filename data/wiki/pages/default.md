## Proven Step Sequences

### File Deletion (Scoped Discard)

**Task pattern:** "Discard/delete X, don't touch anything else"

1. Identify the exact target path from the task description
2. Delete only the named file — no adjacent cleanup
3. Verify no other files were modified

**Outcome:** t02 — `OUTCOME_OK`

---

### Creating a New Structured File (e.g. Invoice)

**Task pattern:** "Create [entity] with fields/lines"

1. `list` the target directory to confirm the file does not already exist
2. `read` the directory's README or schema file to learn the expected format
3. `write` the new file conforming exactly to the schema

**Outcome:** t10 — `OUTCOME_OK`

> **Shortcut:** README.MD in the target folder is the authoritative schema source — read it before writing anything.

---

### Diagnosing and Fixing a Regression (Config/Data Drift)

**Task pattern:** "Fix [regression], keep diff focused"

1. `read` the audit or changelog file to determine when drift started and what the historical value was
2. `read` a sample of pre-drift records to confirm the correct baseline value
3. `read` relevant pipeline/README to identify which component is the authoritative emitter
4. Apply the minimal fix to exactly one config or data file
5. Do **not** touch shadow lanes, cleanup plans, or unrelated files

**Outcome:** t31 — `OUTCOME_OK`

> **Shortcut:** Cross-reference audit timestamps with actual data records before touching any config — the audit alone may be ambiguous.

---

## Key Risks and Pitfalls

### Stalling Without Writing
- **Risk:** Taking many read steps in a row without any write/delete/move causes a stall warning and wastes budget.
- **Mitigation:** After 3–4 reads, commit to a write action or explicitly decide no write is needed. Don't read speculatively.
- **Observed:** t31 triggered a stall after 6 read-only steps.

### Over-broad Changes on Focused Tasks
- **Risk:** "Fix X" tasks invite touching adjacent broken things — evaluators penalize this.
- **Mitigation:** Identify the single config/file that is the root cause; write exactly that. Note unrelated issues in output but do not fix them.

### Skipping Schema Lookup
- **Risk:** Writing a file without checking the local README or schema produces format mismatches.
- **Mitigation:** Always `read` the README in the target directory before the first `write`.

---

## Task-Type Insights

| Task Type | Key Insight |
|---|---|
| Scoped deletion | One step: delete the named path. Scope is the entire contract — touching anything else fails the eval. |
| Entity creation | `list → read README → write` is the minimal correct sequence. |
| Regression fix | Audit file + historical data records together establish ground truth. Config README clarifies which lane/component to patch. |
