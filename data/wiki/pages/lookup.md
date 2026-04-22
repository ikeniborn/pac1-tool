## Lookup Tasks

### Proven Step Sequence

1. **Search** the file system using the target entity's name as the query
   - Yields a file path and line reference (e.g., `contacts/cont_007.json:4`)
2. **Read** the identified file at the returned path
   - Extract the specific field requested from the JSON object

**Outcome:** OUTCOME_OK (`t16` — email lookup for Jesse Meijer via `contacts/cont_007.json`)

---

## Key Risks & Pitfalls

- **Name order variance:** Search queries should account for both `"First Last"` and `"Last First"` conventions; the stored name (`Jesse Meijer`) may differ from the query form (`Meijer Jesse`).
- **Partial reads:** Reading only the matched line number may truncate the JSON object — read the full file to ensure all fields are accessible.

---

## Task-Type Insights & Shortcuts

### Contact / Entity Lookups

| Pattern | Detail |
|---|---|
| File convention | Contacts stored as `contacts/cont_XXX.json` |
| Key fields | `id`, `account_id`, `full_name`, `role`, `email` |
| Fastest path | Search full name → read single JSON file → return field |
| Avoid | Re-searching after a file path is already returned; one read is sufficient |

- When the task says *"return only X"*, extract the single field — do not return the full record.
- `search` reliably returns `filename:line` references; use the filename directly in the subsequent `read` call.