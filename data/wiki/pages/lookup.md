## Lookup Tasks

### Proven Step Sequences

#### Entity Field Lookup
1. **Search** the file system using the target entity's name as the query
   - Yields a file path and line reference (e.g., `contacts/cont_007.json:4`)
2. **Read** the identified file at the returned path
   - Extract the specific field requested from the JSON object

**Outcome:** OUTCOME_OK (`t16` — email lookup for Jesse Meijer via `contacts/cont_007.json`)

---

#### Aggregate / Count Lookup
1. **Search** using the relevant filter terms (e.g., `"blacklist"`, `"telegram"`)
   - Expect multiple file hits; collect all matching paths
2. **Read** each matched file (or scan directory listing if results cluster in one folder)
   - Apply both filter conditions (e.g., platform = telegram AND status = blacklisted)
3. **Count** qualifying records; return the integer only when the task demands a bare number

**Outcome:** OUTCOME_OK (`t30` — count of blacklisted Telegram accounts, answer-only-number format)

---

#### Indirect / Two-Hop Lookup
Use when the target entity (e.g., an account manager) is not named in the task — only their associated record (e.g., an account) is described.

1. **Search** using descriptive terms from the task (e.g., industry, location, specialty keywords)
   - Yields an account-level file path (e.g., `accounts/acct_001.json:14`)
2. **Read** the account file
   - Extract the reference field naming the target person (e.g., `"account_manager": "Kai Möller"`)
3. **Search** again using the extracted name
   - Yields the person's contact file path (e.g., `contacts/mgr_001.json:4`)
4. **Read** the contact file
   - Return the requested field (e.g., `email`)

**Outcome:** OUTCOME_OK (`t39` — email lookup for Nordlicht Health's account manager Kai Möller via `accounts/acct_001.json` → `contacts/mgr_001.json`)

---

## Key Risks & Pitfalls

- **Name order variance:** Search queries should account for both `"First Last"` and `"Last First"` conventions; the stored name (`Jesse Meijer`) may differ from the query form (`Meijer Jesse`).
- **Partial reads:** Reading only the matched line number may truncate the JSON object — read the full file to ensure all fields are accessible.
- **Double-filter errors:** For aggregate queries with two conditions (e.g., platform + status), verify *both* filters are applied before counting — a single-condition pass inflates results.
- **Scattered records:** Blacklist/status data may be spread across multiple files; do not stop at the first match when counting.
- **Indirect reference traps:** When a task describes an account or organization rather than a person, the person's name is embedded in the account record — do not attempt to search for the person directly without first resolving the account. Skipping the intermediate read will yield no results.

---

## Task-Type Insights & Shortcuts

### Contact / Entity Lookups

| Pattern | Detail |
|---|---|
| File convention | Contacts stored as `contacts/cont_XXX.json`; managers as `contacts/mgr_XXX.json` |
| Key fields | `id`, `account_id`, `full_name`, `role`, `email` |
| Fastest path | Search full name → read single JSON file → return field |
| Avoid | Re-searching after a file path is already returned; one read is sufficient |

### Indirect / Two-Hop Lookups

| Pattern | Detail |
|---|---|
| Trigger signal | Task describes an organization/account but asks for a *person's* field (email, phone, etc.) |
| Hop 1 | Search with account descriptors → read account file → extract named reference (e.g., `account_manager`) |
| Hop 2 | Search extracted name → read contact file → return target field |
| File conventions | Accounts: `accounts/acct_XXX.json`; account managers: `contacts/mgr_XXX.json` |
| Avoid | Searching for the person before resolving which person is meant; always anchor to the account first |

### Aggregate / Count Lookups

| Pattern | Detail |
|---|---|
| Trigger phrase | *"how many … ?"* or *"count of …"* |
| Filter strategy | Search with the most selective term first (e.g., platform name), then filter by status in-memory |
| Output format | When task says *"answer only with the number"*, return bare integer — no prose, no units |
| Avoid | Counting search result hits directly; hits represent file matches, not individual records |

### General Output Rules

- When the task says *"return only X"*, extract the single field — do not return the full record.
- `search` reliably returns `filename:line` references; use the filename directly in the subsequent `read` call.
- *"Answer only with …"* phrasing is a strict format constraint — suppress all explanation.
