## Lookup Task Patterns

### Proven Step Sequences

#### Pattern: Contact Email Lookup via Name
**Applies to:** "What is the email of [person]?"

1. `search` for person's name → resolves to a contact file path (e.g., `contacts/cont_NNN.json` or `contacts/mgr_NNN.json`)
2. `read` the resolved contact file → extract `email` field
3. **Verify:** outcome: OUTCOME_OK in 2 ops

> **Name order note:** Task descriptions commonly state names in "Lastname Firstname" order, but contact files store `full_name` as "Firstname Lastname". If initial search fails, immediately retry with reversed name order. Always confirm `full_name` in the resolved file matches the task's target before returning the email.

> **File type note:** A person lookup by name may resolve to either a `cont_NNN.json` or `mgr_NNN.json` file depending on their role. Trust the search result; confirm `full_name` before extracting `email`.

---

#### Pattern: Account Attribute Lookup via Description
**Applies to:** "What is the [field] of the [descriptive] account?"

1. `search` using descriptive keywords (industry, region, trait) → resolves to one or more `accounts/acct_NNN.json` candidates
2. `read` the most relevant account file → confirm match by cross-checking `industry`, `status`, or other qualifiers
3. Return the requested field directly
4. **Verify:** outcome: OUTCOME_OK in 2–3 ops

> **Ambiguous descriptor fallback:** If an initial `search` returns no matches, try alternative keyword combinations derived from the task description (e.g., drop one qualifier, try synonyms). Read candidate files to filter by all qualifiers simultaneously.

---

#### Pattern: Primary Contact Email via Account Description
**Applies to:** "What is the email of the primary contact for [descriptive account]?"

1. `search` using account descriptors (industry, region, name) → resolves to `accounts/acct_NNN.json`
2. `read` the account file → note `account_id` or confirm identity
3. `read` the corresponding `contacts/cont_NNN.json` (matched by `account_id`) → extract `email`
4. **Verify:** outcome: OUTCOME_OK in 3 ops

> **Distinction from manager lookup:** Primary contact files reside in `contacts/cont_NNN.json` (not `mgr_NNN.json`). Match by `account_id`, not manager name.

> **Multi-qualifier account identification:** When the task bundles several descriptors (brand, region, industry, use-case), apply all as filters. If a candidate file satisfies all, proceed; if none does, retry `search` with a subset of keywords.

---

#### Pattern: Account Manager Email via Account Description
**Applies to:** "What is the email of the account manager for the [descriptive] account?"

1. `search` using descriptive keywords → resolves to `accounts/acct_NNN.json`
2. `read` the account file → note the `account_manager` name field
3. `search` for that manager name → resolves to `contacts/mgr_NNN.json`
4. `read` the manager contact file → extract `email`
5. **Verify:** outcome: OUTCOME_OK in 4 ops (search → read account → search → read contact)

> **Disambiguation when search returns multiple account candidates:** If the initial `search` returns multiple account files, read the one whose `industry` and other qualifiers best match all task descriptors before extracting `account_manager`.

---

#### Pattern: Multi-Account Lookup for a Manager (Portfolio Enumeration)
**Applies to:** "Which accounts are managed by [person]?"

1. `search` for the manager name in contacts; if initial search fails, retry immediately with reversed name order → identify their contact file
2. `read` the contact file to confirm `full_name` matches task target
3. `search` for the manager's canonical name across accounts → get list of matching `accounts/acct_NNN.json` paths
4. `read` each returned account file to confirm `account_manager` field matches
5. Collect all matching account names; sort alphabetically before returning
6. **Verify:** outcome: OUTCOME_OK; expect 3–10 accounts per manager; stall warnings (4+) are normal and non-fatal

> **Name order inversion in manager queries:** The task may state "Lastname Firstname" while the contact file stores "Firstname Lastname". First search failure is expected; retry with reversed order before proceeding to account enumeration.

> **Stall tolerance during bulk reads:** Reading 3+ account files sequentially triggers multiple stall warnings. These do not indicate failure. Complete all planned reads and output results promptly.

---

### Key Risks & Pitfalls

#### Name Order Inversion
- Task may state a name as "Lastname Firstname"; files store `full_name` as "Firstname Lastname".
- **Observed frequency:** Highly common; affects ~50% of direct person lookups and manager-based portfolio queries.
- **Mitigation:** On initial search failure, immediately retry with reversed name order. Always confirm `full_name` in the resolved file before trusting subsequent fields.

#### Redundant Searches During Name Retry
- When retrying a person search with reversed name order, redundant `search` calls for the same entity may occur as a side effect of the retry mechanism.
- **Severity:** Low; wastes 1–2 ops but does not affect correctness.
- **Mitigation:** Accept redundant searches as a normal recovery pattern. Prioritize confirming the resolved file's `full_name` before proceeding.

#### Contact File vs. Manager File Confusion
- Accounts have two associated person files: `contacts/cont_NNN.json` (primary contact) and `contacts/mgr_NNN.json` (account manager). Returning the wrong file answers the wrong question.
- **Mitigation:** If the task asks for the "primary contact," use `cont_NNN.json` matched by `account_id`. If it asks for the "account manager," read the account file first to get the manager name, then resolve `mgr_NNN.json`.

#### Direct Name Lookup May Resolve to Manager File
- A person search does not exclusively return `cont_NNN.json` files. When searching by a person's name directly (not via an account), the result may be `mgr_NNN.json` if they are an account manager.
- **Mitigation:** Accept whatever file the `search` returns; confirm `full_name` matches, then extract the requested field regardless of file prefix.

#### Stall Accumulation in Portfolio Enumeration
- Reading multiple account files sequentially in a portfolio query triggers stall warnings after ~6 steps.
- **Observed outcome:** Tasks with 4+ stall warnings can still achieve OUTCOME_OK if all planned reads complete before output.
- **Mitigation:** Treat stall warnings as informational, not blocking. Batch all planned `read` operations conceptually and output results promptly upon completion.

#### Indirect Lookup Chains
- Some tasks require two hops: (1) identify the entity via description → (2) retrieve a linked person's contact file. Stopping after hop 1 returns the wrong artifact.
- **Mitigation:** Always follow through to the file containing the exact requested field.

#### Descriptive Query Ambiguity
- Queries combining multiple qualifiers (industry, region, business trait) may match several accounts initially.
- **Mitigation:** Apply all qualifiers as progressive filters; prefer the account that satisfies all descriptors simultaneously before reading contact details.

#### Zero-Match First Search
- A `search` may return no matches when the query keywords don't align with stored field values (e.g., abbreviations, synonyms, composite descriptors, or name order).
- **Mitigation:** On zero results, decompose the task description into alternative keyword sets (prioritize reversed name order for person lookups) and retry. Do not read arbitrary files speculatively; re-search with refined terms first.

#### Unnecessary Intermediate Reads
- In account manager email lookups, issuing a `search` for a contact (`cont_NNN`) in parallel with searching for the account wastes ops if the account file is the mandatory waypoint for the manager name.
- **Mitigation:** Follow the canonical 4-op chain: search account → read account → search manager by name → read manager file. Do not speculate on contact IDs before reading the account.

---

### Task-Type Insights & Shortcuts

- **Single-hop lookups** (name → email): always resolvable in exactly 2 ops: `search` → `read`. Works for both `cont_NNN` and `mgr_NNN` targets. Expect name order inversion; design for retry on first-search failure.
- **Two-hop lookups** (description → account → contact email): 3 ops minimum; skipping the intermediate account read risks returning the wrong contact.
- **Three-hop lookups** (description → account → manager name → manager email): 4 ops minimum; the account file is a mandatory waypoint to extract the manager name before the second search.
- **Portfolio queries**: Expect 4+ stall warnings during bulk account reads; these are standard and non-fatal for read-only enumeration. Design with confidence; complete all planned reads before returning results.
- **Contact vs. manager disambiguation**: the task verb matters—"primary contact" → `cont_NNN.json`; "account manager" → resolve name from account file, then `mgr_NNN.json`.
- **Field extraction discipline**: only return the exact field requested (e.g., email only, name only). No surrounding context.
- **Name canonicalization**: always confirm `full_name` in the resolved file matches the task's target before trusting `email` or other fields from that record. Expect "Lastname Firstname" task descriptions to resolve to "Firstname Lastname" files.
- **Multi-qualifier account tasks**: when the task bundles brand, region, industry, and use-case together, treat the conjunction of all qualifiers as the filter—reject any candidate account file that fails even one qualifier.
- **Zero-match recovery**: on a failed `search`, immediately retry with name variants (especially reversed name order) or decomposed keyword sets rather than reading unrelated files speculatively.

---
