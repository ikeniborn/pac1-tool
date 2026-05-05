<!-- wiki:meta
category: lookup
quality: mature
fragment_count: 37
fragment_ids: [t43_20260504T105345Z, t43_20260504T114608Z, t43_20260504T122556Z, t40_20260504T154747Z, t43_20260504T154303Z, t43_20260504T172813Z, t40_20260504T174705Z, t40_20260504T181350Z, t43_20260504T181155Z, t16_20260504T192847Z, t34_20260504T194407Z, t38_20260504T194925Z, t39_20260504T195012Z, t16_20260504T202555Z, t34_20260504T204435Z, t38_20260504T204123Z, t39_20260504T203953Z, t43_20260504T204330Z, t16_20260504T211914Z, t34_20260504T213720Z, t38_20260504T213127Z, t39_20260504T213218Z, t40_20260504T213857Z, t43_20260504T213713Z, t16_20260504T221950Z, t38_20260504T223049Z, t40_20260504T223944Z, t16_20260504T231505Z, t34_20260504T233326Z, t39_20260504T233903Z, t40_20260504T234106Z, t43_20260504T233809Z, t16_20260505T001610Z, t34_20260505T003554Z, t38_20260505T003757Z, t39_20260505T004041Z, t43_20260505T004011Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Task Type:** `lookup`

**Steps:**

1. Parse query for temporal reference (e.g., "2 days ago", "last week")
2. Attempt to resolve temporal anchor against captured metadata timestamps

**Outcome Pattern:**
- `OUTCOME_OK` — query matched existing vault items successfully
- `OUTCOME_NONE` — no matching vault items exist
- `OUTCOME_NONE_CLARIFICATION` — query requires additional user input to resolve ambiguous temporal or descriptive constraints

**Note:** Ambiguous time-based queries may need explicit title or keyword matching to retrieve results. Entity-based queries (e.g., person names, account identifiers) tend to resolve more reliably than numeric temporal references alone. Account identifiers may include compound descriptors (e.g., geographic region + business type + internal classification tags) that require exact matching against vault metadata. Account identifiers may include multiple compound descriptor elements such as business type classification, customer/client type designation, geographic region, and account name that must all be matched precisely against vault metadata for successful resolution.

**Practical Examples:**

- Input: `'Which accounts are managed by Becker Lara?'`
- Parsed entity reference: `Becker Lara` (person name)
- Resolution attempt: Query vault for accounts associated with specified entity
- Outcome: `OUTCOME_OK` — matched items returned successfully


- Input: `'Which accounts are managed by Sauer Robert? Return only the account names, one per line, sorted alphabetically.'`
- Parsed entity reference: `Sauer Robert` (person name)
- Resolution attempt: Query vault for accounts associated with specified entity
- Output formatting: Return account names sorted alphabetically, one per line
- Outcome: `OUTCOME_OK` — matched items returned with requested sorting and formatting

- Input: `'What is the email address of Fischer Leon? Return only the email'`
- Parsed entity reference: `Fischer Leon` (person name)
- Resolution attempt: Query vault for contact attributes associated with specified entity
- Output formatting: Return only the email attribute value
- Outcome: `OUTCOME_OK` — email attribute extracted and returned

- Input: `'What is the exact legal name of the German ecommerce retail logo Silverline account? Answer with the exact legal name only.'`
- Parsed entity reference: `Silverline account` (account identifier)
- Resolution attempt: Query vault for account metadata including legal name attribute
- Output formatting: Return only the legal name field
- Outcome: `OUTCOME_OK` — legal name attribute extracted and returned

- Input: `'What is the email of the primary contact for the Benelux services account? Return only the email.'`
- Parsed entity reference: `Benelux services account` (account name) with role qualifier `primary contact`
- Resolution attempt: Query vault for contact with primary contact role associated with specified account, extract email attribute
- Output formatting: Return only the email attribute value
- Outcome: `OUTCOME_OK` — role-specific email attribute extracted and returned

- Input: `'What is the email address of the account manager for the Aperture account? Return only the email.'`
- Parsed entity reference: `Aperture account` (account name) with role qualifier `account manager`
- Resolution attempt: Query vault for contact with account manager role associated with specified account, extract email attribute
- Output formatting: Return only the email attribute value
- Outcome: `OUTCOME_OK` — role-specific email attribute extracted and returned



- Input: `'Which accounts are managed by Voigt Elisabeth? Return only the account names, one per line, sorted alphabetically.'`
- Parsed entity reference: `Voigt Elisabeth` (person name)
- Resolution attempt: Query vault for accounts associated with specified entity
- Output formatting: Return account names sorted alphabetically, one per line
- Outcome: `OUTCOME_OK` — matched items returned with requested sorting and formatting

- Input: `'What is the exact legal name of the Benelux vessel-schedule logistics customer CanalPort account? Answer with the exact legal name only.'`
- Parsed entity reference: `Benelux vessel-schedule logistics customer CanalPort account` (compound account identifier)
- Resolution attempt: Query vault for account metadata including legal name attribute, matching all compound descriptor elements
- Output formatting: Return only the legal name field
- Outcome: `OUTCOME_OK` — legal name attribute extracted and returned


**Key Insight:** Entity-based lookups (person names, account identifiers) demonstrate higher success rates than pure temporal queries. Successful entity queries can also return results in specified output formats, including sorted or filtered presentations. Even precise numeric temporal references (e.g., "23 days ago", "48 days ago", "27 days ago", "19 days ago", "16 days ago") can fail to resolve if vault metadata lacks sufficient timestamp granularity or capture date tracking. Such queries still require fallback to title, keyword, or entity matching for successful retrieval. Lookup queries can also target specific attributes (email addresses, legal names) or role-specific contacts (primary contact, account manager) and return only the requested field value rather than complete records.

## Key pitfalls
**Risk: Premature NONE_CLARIFICATION before search operations**

When a user task contains ambiguous or incomplete temporal references (e.g., "27 days ago"), the agent may incorrectly assume it has insufficient information and return OUTCOME_NONE_CLARIFICATION without ever attempting a list/find/tree operation. In task t43 (lookup: "Find the article I captured 27 days ago"), the phrase "27 days ago" should be interpreted as a relative date filter rather than a reason to block execution. The agent should first attempt the search operation, then present results or refine based on what is found. Premature clarification requests frustrate users when the system could have successfully completed the task with standard date arithmetic. This pattern repeats consistently across different temporal spans: when t43 (<date>) asked about "which article I captured 2 days ago", the agent still returned OUTCOME_NONE_CLARIFICATION, demonstrating that even short relative periods (2 days) trigger the same premature blocking behavior as longer ones (27 days). The agent's inability to perform simple date arithmetic ("2 days ago" = <date> from <date>) and attempt a search results in unnecessary clarification requests for tasks that could be completed autonomously. Task t43 demonstrates this same failure with "48 days ago", showing the pattern holds across additional temporal ranges beyond those already documented. Task t43 (<date>) further confirms this issue with "30 days ago", where the agent again returned OUTCOME_NONE_CLARIFICATION instead of computing the relative date and executing the search. Task t43 further demonstrates this issue with "47 days ago", where the agent again returned OUTCOME_NONE_CLARIFICATION. Task t43 further demonstrates this issue with "12 days ago", where the agent again returned OUTCOME_NONE_CLARIFICATION, showing the pattern persists across mid-range temporal spans not previously documented. Task t43 with "19 days ago" further demonstrates this issue, showing the pattern persists across this additional temporal span not previously documented. Task t43 with "16 days ago" further demonstrates this issue, showing the pattern persists across this additional temporal span not previously documented.

**Risk: False matches with loose temporal filters**

When interpreting vague temporal references like "27 days ago" as date ranges, the agent may produce false matches if the calculation is incorrect or if multiple items fall within the approximated window. For example, if the agent calculates "27 days ago" as <date> and finds multiple captured articles on that date, it cannot reliably determine which article the user means. This creates ambiguity that may lead to returning the wrong item or requiring user disambiguation anyway. Even tighter windows like "2 days ago" do not eliminate this risk if the user captured multiple articles within that span, as the agent would still lack sufficient disambiguation criteria to select the correct item.

**Risk: Wrong filters from incorrect temporal interpretation**

The agent must accurately translate relative time expressions into concrete date ranges before applying search filters. Errors in this conversion (time zone issues, off-by-one errors, leap year handling) result in wrong filters that miss the intended items entirely. In task t43, if "27 days ago" is computed as <date> instead of <date>, articles captured on the correct date will be excluded from results, causing the agent to return empty results despite the item existing. This risk is exacerbated when the agent cannot perform the calculation at all (as in the OUTCOME_NONE_CLARIFICATION case) and never applies any filter, resulting in zero results being returned rather than potentially returning the wrong subset.

## Shortcuts
**Temporal/Date-Based Lookup Strategy**
- When task references "captured [X] days ago", "created [timeframe]", or similar relative dates, use date-based filtering
- Convert relative dates to absolute ranges (e.g., "27 days ago" → specific date range)
- Search within file metadata (capture timestamps, creation dates) rather than content keywords

**Filter Approach: Time Windowing**
- Define exact date ranges based on relative time mentions
- Filter results by timestamp metadata fields
- For "captured" content specifically, search capture_date or similar metadata fields

**Multi-Stage Search for Date-Based Lookups**
1. First identify the target date range (calculate from relative time)
2. Apply temporal filter to narrow dataset
3. Verify match against additional metadata if available
4. If no match found, expand window slightly (±1-2 days) to account for time zone or timestamp precision issues

**Handling None-Clarification Outcomes**
- When combined temporal + content-type lookup returns no match, evaluate which criterion caused the failure
- Mismatch between "captured" metadata and temporal range may indicate user means different date reference (e.g., "captured" vs "created" vs "modified")
- OUTCOME_NONE_CLARIFICATION signals ambiguity in which date field or time reference to prioritize
- Consider expanding time window beyond ±1-2 days when compound filters produce no results
- Clarification should address whether "captured" refers to capture_date metadata or content creation date

**Content-Type Filtering**
- When lookup specifies "article", apply document type filter
- Combine content-type filter with date filter for precision
- Common type identifiers: .md, .txt, document formats, wiki entries

**Combined Multi-Criteria Lookup Strategy**
- When lookup combines multiple filter types (date + content-type + metadata), apply filters sequentially for precision
- "Captured [timeframe]" with content type implies searching metadata fields for both capture_date and document type simultaneously
- Build compound filter: temporal range AND content-type AND optional metadata flags
- Verify all criteria match before returning result; mismatch across criteria types may indicate clarification needed

**Attribute/Field-Based Lookup Pattern**
- When task specifies an attribute value (e.g., "managed by [Name]", "created by [User]"), search that specific field for exact match
- Return all items where the field value matches the specified criteria
- Apply result ordering when specified (alphabetical, chronological, etc.)
- Output formatting requirements (one item per line) should be preserved in result presentation
- When task requests "only [specific field] names" or similar selective field output, return exclusively the requested field values without additional metadata
- Common attribute field patterns include: "managed by", "created by", "owned by", "assigned to" — these map to corresponding metadata fields

**Simple Direct Attribute Lookup**
- When task requests a single attribute for an explicitly named entity (e.g., "email of [Name]", "phone of [Contact]"), perform direct field lookup on the identified entity
- No compound filtering required when entity is explicitly named
- Output restriction ("only the [field]") applies to return format only; entity identification requires no additional filtering
- Return the exact requested attribute value without accompanying context or metadata
- Task explicitly specifying "exact legal name" or similar precision qualifiers indicates preference for verified field values over display names

**Exact Value Extraction Pattern**
- When task includes qualifier "exact" (e.g., "exact legal name"), return the precise attribute value as stored in the authoritative field
- Do not normalize, abbreviate, or apply display formatting to exact value fields
- "Exact legal name" typically maps to a dedicated legal_name field separate from display or trading names

**Complex Account/Entity Identification Patterns**
- When lookup specifies an account or entity with compound identifiers (e.g., "[Region] [Type] account" or "account with [Qualifier]"), parse all identifier components as filter criteria
- Compound identifiers may include: region/territory, account type, business function, status qualifier, or subscription type
- Distinguishing qualifiers like "seeded for [purpose]" or "[add-on] subscriber" narrow identification to specific accounts within a category
- Each component of the identifier should be matched against corresponding metadata fields
- Verify all components match before returning result; partial matches may indicate incorrect account selection

**Chained Attribute Lookup Strategy**
- When task asks for a field belonging to a related entity (e.g., "email of the account manager for [Account]"), perform sequential lookup: first identify account, then retrieve associated role holder's target field
- Role identifiers (primary contact, account manager, owner) map to related entity fields or contact references
- Tasks combining entity identification with role-based lookup require resolving both criteria before extracting target attribute
- Output restriction ("only the [field]") applies to final result, not intermediate identification steps
- Chained lookups with compound account identifiers (region + type + name) first resolve all account filter components, then apply role-based extraction on the matched account
- Common role types include: primary contact, account manager, owner — each maps to a distinct related entity field

**Brand/Account Type Qualified Lookups**
- When task includes brand filter combined with account type (e.g., "under the [Brand] account"), apply both criteria as independent constraints
- Brand qualifier and account type are separate filter dimensions that must both be satisfied
- Role-based extraction still applies on the filtered account set
- Compound account identifiers like "[Region] [Brand] manufacturing account" require parsing: region applies territorial filter, brand applies business segment filter, type applies account classification filter

**Temporal + Content-Type Compound Ambiguity**
- When relative date ("X days ago") is combined with content-type ("article"), "captured" may refer to different date fields (capture_date metadata vs content creation date)
- The phrase pattern "captured [X] days ago" with article/document type is a known disambiguation trigger
- This compound filter pattern frequently produces OUTCOME_NONE_CLARIFICATION when the selected date field contains no entries matching both criteria
- Clarification requests should ask which date interpretation applies when temporal+type lookup fails

**Date Reference Type Disambiguation**
- "Captured" can mean: (1) capture_date metadata field, (2) content creation date, (3) file modification timestamp
- Each interpretation yields potentially different results from the same temporal query
- When temporal queries with content type return no match, the ambiguity is likely in which date field to query

**Concrete Ambiguity Example**
- Task "Find the article I captured 30 days ago" combines three ambiguity vectors: "captured" date field interpretation, "30 days ago" date range calculation, and "article" content-type specification
- OUTCOME_NONE_CLARIFICATION in this scenario indicates that either no article exists within the 30-day window for the chosen date field, or the date field interpretation is incorrect
- Resolution requires clarifying which date field ("captured" metadata vs content creation date) applies to the article query



## Successful pattern: t40 (2026-05-04)
<!-- researcher: t40:e3b0c44298fc -->

**Goal shape:** Which accounts are managed by Becker Lara? Return only the account names, one per line, sorted alpha

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?
9. ?
10. ?
11. ?
12. ?
13. ?
14. ?
15. ?
16. ?
17. ?
18. ?
19. ?
20. ?
21. ?
22. ?
23. ?
24. ?
25. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t16 (2026-05-04)
<!-- researcher: t16:e3b0c44298fc -->

**Goal shape:** What is the email address of Fischer Leon? Return only the email

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t34 (2026-05-04)
<!-- researcher: t34:e3b0c44298fc -->

**Goal shape:** What is the exact legal name of the German ecommerce retail logo Silverline account? Answer with the

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t38 (2026-05-04)
<!-- researcher: t38:e3b0c44298fc -->

**Goal shape:** What is the email of the primary contact for the Benelux services account seeded for duplicate-conta

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?
9. ?
10. ?
11. ?
12. ?
13. ?
14. ?
15. ?
16. ?
17. ?
18. ?
19. ?
20. ?
21. ?

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t39 (2026-05-04)
<!-- researcher: t39:e3b0c44298fc -->

**Goal shape:** What is the email address of the account manager for the German AI-insights add-on subscriber Apertu

**Final answer:** (unspecified)

**Trajectory:**
1. ?
2. ?
3. ?
4. ?
5. ?
6. ?
7. ?
8. ?
9. ?
10. ?
11. ?
12. ?
13. ?
14. ?
15. ?
16. ?
17. ?
18. ?
19. ?
20. ?
21. ?
22. ?
23. ?

**Key insights:**
- (none)

**Applies when:** lookup
