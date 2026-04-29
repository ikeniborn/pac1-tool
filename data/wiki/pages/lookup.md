## Proven Step Sequences

### Search-First Lookup (Efficient)
**When:** Account name is known from query; target is a field in account or contact record.

**Trajectory:**
1. `search` → locate target account file
2. `read(/accounts/<file>)` → extract field (legal_name, primary_contact_id)
3. `read(/contacts/<file>)` if primary_contact_id → extract contact email

**Why it works:** Search narrows to the relevant account file in one step. No iteration required.

### Multi-Search with Progressive Refinement
**Observed in:** t16, t34, t38, t39

**Pattern:**
1. `search` → no matches
2. `search` → partial matches or narrower results
3. `read(/accounts/<file>)` → identify correct account
4. `read(/contacts/<file>)` if needed

**Why it works:** First search uses broad terms; retry with more specific keywords. Multiple matches require reading files to disambiguate.

---

## Key Risks and Pitfalls

### Initial Search Often Fails
**Observed in:** t16, t34, t38, t39

**Problem:** First `search` query returns no matches. Requires second attempt with different keywords.

**Fix:** Always plan for retry search. If first search fails, rephrase terms or search by different attributes (region, industry, keywords).

### Multiple Account Matches Require Disambiguation
**Observed in:** t34

**Problem:** Search by "Acme" returned matches in <account> and <account>. Agent had to read both files to determine correct legal_name.

**Fix:** When search returns multiple account files, read all to verify which matches the query criteria (region, industry, use case).

### Iterating All Accounts (Inefficient)
**Observed in:** t38 (historical example)

**Problem:** Agent listed accounts and read 6 files sequentially before locating the target.

**Bottleneck:** Not using search when the query names the account.

**Fix:** Use `search` with account name keywords to locate the file directly.

### Stall Warnings Indicate Inefficiency
**Observed in:** t39 (3 stall warnings)

**Problem:** Excessive reads without producing output.

**Indicator:** Stall count increases when the agent iterates rather than searches.

### Manager vs Contact Reference Confusion
**Observed in:** t39

**Problem:** `account_manager` field points to an internal staff record (`mgr_*`) not an external contact (`cont_*`). Agent required a second search to locate the manager's contact file.

**Fix:** When query asks for account_manager email, note that a second search for `mgr_` prefixed files may be needed.

---

## Task-Type Specific Insights

### Lookup Task Patterns
| Target Field | Source Location | Reference Chain |
|--------------|-----------------|-----------------|
| legal_name | /accounts/<file> | direct |
| primary_contact_id | /accounts/<file> | account → cont_N → contacts/ |
| account_manager | /accounts/<file> | account → mgr_N → contacts/ |
| contact email | /contacts/<file> | direct |

### Reference Path Reminders
- `primary_contact_id` → `/contacts/<file>
- `account_manager` → `/contacts/<file> (internal staff, not external contacts)

### Efficient vs Inefficient Trajectories
| Approach | Steps | Stall Risk |
|----------|-------|------------|
| search → read | 2 | Low |
| search → search → read → read | 4 | Medium |
| list → iterate → read | 5+ | High (stall warnings) |
| search → read → search → read | 4–5 | Medium |

### Date-Based Lookups Require Clarification
**Observed in:** t43

**Problem:** Query "article captured 14 days ago" could not be resolved. No file matched the relative date.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Fix:** Relative date queries ("X days ago") should be flagged for clarification. Convert to absolute date range or ask for confirmation.

---

## Successful Patterns

### t16 (<date>)
**Goal:** What is the email address of Maas Lois? Return only the email.

**Answer:** <email>

**Trajectory:** search → search → read(/contacts/<file>)

**Key insights:** First search failed; second search using partial name located the contact file directly.

### t34 (<date>)
**Goal:** What is the exact legal name of the Benelux cross-dock logistics buyer under the Acme brand account?

**Answer:** Acme Logistics B.V.

**Trajectory:** search → search → read(<account>.json) → read(<account>.json)

**Key insights:** Two Acme accounts exist with similar naming. Search returned matches in both; disambiguation required reading both files.

### t38 (<date>)
**Goal:** What is the email of the primary contact for the Austrian grid-modernization energy customer account?

**Answer:** <email>

**Trajectory:** search → search → search → read(<account>.json) → read(<contact>.json)

**Key insights:** Three searches needed to locate the account file. Energy industry + Austria region narrowed results.

### t39 (<date>)
**Goal:** What is the email address of the account manager for the Dutch banking customer with an open security review account?

**Answer:** <email>

**Trajectory:** search × 4 → read(<account>.json) → search(<manager>.json) → stall → read(<manager>.json) → stall

**Key insights:** Four searches needed for account. Account manager required separate manager contact file lookup. Stalls occurred after multiple reads.

---

## Verified Refusals

### t43 (<date>) — OUTCOME_NONE_CLARIFICATION
**Goal:** need the article i captured 14 days ago

**Problem:** Relative date reference could not be resolved to a specific file.

**Files checked:** /01_capture/influential/ (5 files, none dated 14 days prior)

**Outcome:** Agent correctly declined to guess; flagged for clarification.

**Probes:** search → list(/01_capture) → list(/01_capture/influential) → search
