## Proven Step Sequences

**Direct Email (explicit address given)**
1. Read `/outbox/seq.json` for current ID
2. Write `/outbox/{id}.json` with recipient, subject, body
3. Seq file auto-increments on write — explicit update not needed

**Person-First (name given)**
1. Search contacts for person name (try reversed order if no match: "Frank Arne" → "Arne Frank")
2. Read matched contact (`cont_*.json` or `mgr_*.json`) → extract `email` and `account_id`
3. Read `/outbox/seq.json` → write email → update seq

**Account/Organization-First (org name given)**
1. Search accounts for org name → read account file → extract `account_manager`
2. Search contacts for manager name → read matched contact file → extract `email`
3. Read `/outbox/seq.json` → write email → update seq

**Industry-First (customer described by sector)**
1. Read all accounts sequentially, filter by `industry` field
2. Read matched account → extract `account_manager`
3. Search contacts for manager name → read contact file → extract `email`
4. Read `/outbox/seq.json` → write email → update seq

## Key Risks and Pitfalls

- **Both contact prefixes**: Account managers use `mgr_*.json`, primary contacts use `cont_*.json`; try both when the first fails
- **Atomic sequence**: read seq → write email → update seq — all three in order; skipping seq update causes ID collision
- **Account manager search by name**: `account_manager` in account file may have different numeric suffix than `acct_NNN` — always search by name, don't assume suffix match
- **Stall warning**: 6 reads without write triggers stall; account/industry-first paths are read-heavy — write email as soon as email is resolved, before reading notes or additional files
- **Search with empty query**: initial search may return no matches; need to refine query (account name, manager name, etc.)

## Task-Type Specific Insights

**Email Tasks**
- `/outbox/seq.json` schema: `{"id": integer}` — write triggers auto-increment; no explicit update needed
- Notes in `/01_notes/{kebab-org}.md` are optional context — skip if missing or if step budget is tight
- Explicit email address = 2-step path (seq + write) — no contact resolution needed
- `search` over `list+read` for account/contact discovery — fewer steps, avoids stall
- Finance industry = banking customers; filter `industry: "finance"` in account records