## Lookup Tasks — Workflow Wiki

## Proven Step Sequences

### Contact Email Lookup (by person name)
**Pattern:** Direct name search → read matched contact file → extract email field.

1. `search` name tokens → resolves to `contacts/<id>.json`
2. `read` contact file → extract `email`
3. **Verify:** single unambiguous match; if multiple, check `account_id` to disambiguate.

---

### Account Legal Name Lookup (by descriptor/add-on/industry)
**Pattern:** Descriptor search may return no matches; fall back to notes directory, then accounts.

1. `search` descriptor keywords → if no matches, proceed to step 2
2. `read` relevant note file in `/01_notes/` → confirm account name hint
3. `search` confirmed name → resolves to `accounts/<id>.json`
4. `read` account file → extract `name` field (legal name)

---

### Primary Contact Lookup (by account description + nationality)
**Pattern:** Multi-hop; description alone is ambiguous — search iteratively, narrow by country/industry attribute.

1. `search` role/industry keywords → may return multiple account candidates
2. `read` each candidate account file → filter by country/industry match
3. `search` `account_id` of matched account → resolves to `contacts/<id>.json`
4. `read` contact file → extract `email`
- **Watch for stall:** if 6+ steps pass with no write/create/move, the agent must commit to a read path immediately.

---

### Account Manager Email Lookup (indirect — name not directly searchable)
**Pattern:** Account record holds manager name; manager contact stored in a separate `contacts/mgr_*.json` file.

1. `search` account descriptor keywords → resolves to `accounts/<id>.json`
2. `read` account file → extract `account_manager` name
3. `search` manager name → resolves to `contacts/mgr_<id>.json`
4. `read` manager contact file → extract `email`

---

## Key Risks & Pitfalls

### Ambiguous Account Names
- Generic brand names (e.g., "Acme") match multiple accounts across different industries and countries.
- **Fix:** Always filter candidates by at least one additional attribute (industry, country, add-on, role).

### Descriptor Searches Returning No Results
- Colloquial descriptions ("German AI-insights add-on subscriber") do not match indexed field values.
- **Fix:** Decompose into atomic keywords; fall back to `/01_notes/` for contextual hints before re-searching accounts.

### Stall Risk on Multi-Hop Lookups
- Chaining search→read→search→read without committing to a final read path triggers stall warnings at step 6.
- **Fix:** After identifying the target `account_id`, immediately pivot to a targeted contact search rather than issuing additional broad searches.

### Ambiguous Temporal References
- Tasks phrased as "X days ago" cannot be resolved without knowing the current date relative to file timestamps.
- **Fix:** Surface clarification immediately; do not attempt to infer from file listing alone.

---

## Task-Type Shortcuts

| Lookup Target | Fastest Path |
|---|---|
| Person email | `search` full name → `contacts/*.json` |
| Account legal name | `search` keywords → if miss, check `/01_notes/` → `accounts/*.json` |
| Primary contact for account | `search` account → read → get `account_id` → `search` contact by `account_id` |
| Account manager email | `search` account → read `account_manager` name → `search` name in `contacts/mgr_*.json` |

---

## Task-Type Insights

- **`/01_notes/` as fallback index:** When keyword searches against structured data fail, narrative note files often contain the canonical account name needed for a second-pass search.
- **Manager contacts use a separate namespace:** Account manager records appear under `contacts/mgr_*.json`, not `contacts/cont_*.json`. Include `mgr_` prefix in searches when looking for staff rather than client contacts.
- **Account files do not store contact emails directly:** Always follow `account_id` → contact file to retrieve email; the account record stores only the manager's display name.
