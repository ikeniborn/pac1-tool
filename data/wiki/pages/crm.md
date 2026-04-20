## Proven Step Sequences

**CRM Follow-up Date Correction:**
1. **Read audit context** (`docs/*-audit.json`) first to check `candidate_patch` scope
2. **Read target reminder** (`/reminders/rem_*.json`) to verify current state
3. **Write updated reminder** with new `due_on` date
4. **Verify output** via done ops list, not by re-reading the file

## Key Risks and Pitfalls

- **Stall threshold**: 6 consecutive read/search/list operations without a write triggers stall warnings; batch your reads or write early
- **Scope violations**: Writing to `/accounts/` when audit specifies `candidate_patch: "reminder_only"` creates unfocused diffs and wastes I/O
- **Redundant round-trips**: Re-reading a file immediately after writing (`write` → `read` → `write`) doubles step count without adding safety

## Task-Type Specific Insights (CRM)

- **Respect candidate_patch**: Audit files contain a `candidate_patch` field with values like `"reminder_only"`—treat this as the authority on which file types to modify
- **Keep diffs surgical**: For follow-up date changes, touch only the `due_on` field in the specific reminder file; account metadata remains unchanged
- **ISO date format**: Ensure new dates match the existing `YYYY-MM-DD` format exactly to prevent regression
- **Directory listing hygiene**: Listing `/reminders` is only necessary for ID generation; if the audit provides the specific `rem_*.json` path, skip the directory listing