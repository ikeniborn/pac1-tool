<!-- wiki:meta
category: lookup
quality: nascent
fragment_count: 3
fragment_ids: [t43_20260504T105345Z, t43_20260504T114608Z, t43_20260504T122556Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Task Type:** `lookup`

**Steps:**

1. Parse query for temporal reference (e.g., "2 days ago", "last week")
2. Attempt to resolve temporal anchor against captured metadata timestamps
3. If no matching article found for specified timeframe:
   - Return `OUTCOME_NONE_CLARIFICATION`
   - Await user clarification specifying article title, keyword, or exact date range

**Outcome Pattern:**
- `OUTCOME_NONE` — no matching vault items exist
- `OUTCOME_NONE_CLARIFICATION` — query requires additional user input to resolve ambiguous temporal or descriptive constraints

**Note:** Ambiguous time-based queries may need explicit title or keyword matching to retrieve results.

**Practical Example:**
- Input: `'need the article i captured 23 days ago'`
- Parsed temporal anchor: `23 days ago`
- Resolution attempt: Search captured metadata for items with timestamp matching ~<date>
- Outcome: `OUTCOME_NONE_CLARIFICATION` — no items found for that exact temporal range, requiring user to specify article title, keyword, or exact date

**Key Insight:** Even precise numeric temporal references (e.g., "23 days ago") can fail to resolve if vault metadata lacks sufficient timestamp granularity or capture date tracking. Such queries still require fallback to title or keyword matching for successful retrieval.

## Key pitfalls
**Risk: Premature NONE_CLARIFICATION before search operations**

When a user task contains ambiguous or incomplete temporal references (e.g., "27 days ago"), the agent may incorrectly assume it has insufficient information and return OUTCOME_NONE_CLARIFICATION without ever attempting a list/find/tree operation. In task t43 (lookup: "Find the article I captured 27 days ago"), the phrase "27 days ago" should be interpreted as a relative date filter rather than a reason to block execution. The agent should first attempt the search operation, then present results or refine based on what is found. Premature clarification requests frustrate users when the system could have successfully completed the task with standard date arithmetic. This pattern repeats consistently across different temporal spans: when t43 (<date>) asked about "which article I captured 2 days ago", the agent still returned OUTCOME_NONE_CLARIFICATION, demonstrating that even short relative periods (2 days) trigger the same premature blocking behavior as longer ones (27 days). The agent's inability to perform simple date arithmetic ("2 days ago" = <date> from <date>) and attempt a search results in unnecessary clarification requests for tasks that could be completed autonomously.

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

## Lookup Task: Finding Captured Articles by Date
**Pattern:** Article retrieval by capture timestamp

**Scenario:** Finding an article captured a specific number of days ago

**Recommended Step Sequence:**
1. Query vault storage with date range filter
2. Calculate target date: current date minus specified days (today − 27 days)
3. Search for articles with capture_timestamp matching or within target date range
4. Return matching results ordered by capture_timestamp descending
5. If results empty → return OUTCOME_NONE_CLARIFICATION
6. Present found articles with metadata for user verification

**Failure Handling:** When lookup returns no results, the agent should output OUTCOME_NONE_CLARIFICATION and prompt user to provide additional identifying details (title keywords, approximate topic, or alternative date estimate)

## Verified refusal: t43 (2026-05-04)
<!-- refusal: t43:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Find the article I captured 27 days ago.

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?
2. ?

**Applies when:** lookup
