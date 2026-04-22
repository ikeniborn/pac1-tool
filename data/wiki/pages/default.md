## Proven Step Sequences

### Discard / Delete a Specific File

**Task type:** File deletion (single target)
**Outcome:** OUTCOME_OK

1. List the parent directory → confirm target file exists and identify siblings.
2. Delete only the named file.
3. Verify siblings are untouched.

**Key constraint:** Scope is strictly limited to the named file — no collateral changes to other files or directories.

---

## Key Risks & Pitfalls

- **Scope creep on deletions:** When asked to discard one file, confirm the exact path before deleting; sibling files (e.g. `_thread-template.md`, other threads) must remain untouched.
- **Date arithmetic errors:** Pure date calculations (no file ops needed) should be handled directly. Observed miscalculation in t41: task asked for +10 days from 2026-04-22 but evaluator recorded +18 days (result 2026-05-10). Treat this as a pitfall — verify arithmetic independently.

---

## Task-Type Insights & Shortcuts

### Single-File Delete
- A directory listing step before deletion is low-cost and prevents wrong-target errors.
- No edits, moves, or renames needed — `delete` is the only operation.

### Date Arithmetic (No File Ops)
- Resolve inline; no filesystem operations required.
- Double-check the delta: off-by-N errors have been observed in this agent's history.
- Return format should match exactly what was requested (e.g. `DD-MM-YYYY`).