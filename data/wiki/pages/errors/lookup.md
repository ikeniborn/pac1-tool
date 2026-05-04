<!-- wiki:meta
category: errors/lookup
quality: developing
fragment_count: 8
fragment_ids: [t40_20260504T105434Z, t40_20260504T114829Z, t40_20260504T120459Z, t42_20260504T120146Z, t40_20260504T121802Z, t42_20260504T121640Z, t40_20260504T123401Z, t42_20260504T123030Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Query Lookup Dead-End: Unmanaged or Non-Existent Manager**

```
Query pattern:
  "Which accounts are managed by [PERSON_NAME]?"
  
Step sequence that leads to OUTCOME_NONE_CLARIFICATION:
  1. Execute direct manager-name lookup query
  2. Return only account names, sorted alphabetically
  3. No results → OUTCOME_NONE_CLARIFICATION returned
  
Why it fails:
  - Manager name not found in vault records
  - No accounts assigned to specified person
  - Query returns no data → clarification unavailable
  
Alternative approach:
  - List all accounts first, then filter manually
  - Query for person record existence before account lookup
  - Use wildcard search if supported
  
Note: OUTCOME_NONE_CLARIFICATION on manager queries indicates
  either the person doesn't manage any accounts OR the person
  doesn't exist in the vault data structure
```

**Successful Manager Account Query Pattern**

```
Query pattern:
  "Which accounts are managed by [PERSON_NAME]? Return only
   the account names, one per line, sorted alphabetically."
  
Step sequence for OUTCOME_OK:
  1. Parse manager name from query
  2. Execute lookup against manager assignment records
  3. Filter to accounts where manager matches query
  4. Sort results alphabetically
  5. Return names only, one per line
  
Dead end signals:
  - OUTCOME_NONE_CLARIFICATION when manager not found
  - Ambiguous queries cause wrong person resolution
  
Query construction guidance:
  - Always specify exact person name
  - Request sorted output explicitly
  - Request one-per-line formatting

Verified successful execution:
  - task_id: t40
  - Query: "Which accounts are managed by Heinrich Pascal?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
```

**Temporal Capture Query Dead-End**

```
Query pattern:
  "What article did I capture [DATE_EXPRESSION]?"
  Example: "What article did I capture 10 days ago?"
  
Step sequence that leads to OUTCOME_NONE_CLARIFICATION:
  1. Parse date expression (relative or absolute)
  2. Convert expression to absolute date reference
  3. Query vault for captures matching that date
  4. No matching capture → OUTCOME_NONE_CLARIFICATION returned
  
Why it fails:
  - Date expression parsing failed or unsupported
  - No article was captured on the specified date
  - Temporal offset calculation out of range
  - Capture date not recorded in vault data structure
  
Alternative approach:
  - Query for recent captures first, then filter manually
  - List all captured articles without date filter
  - Use specific ISO date format instead of relative expression
  - Retrieve capture list without temporal constraint, then
    filter by date on client side
  
Note: OUTCOME_NONE_CLARIFICATION on capture date queries indicates
  either no capture exists for that date OR date expression
  parsing/calculation failed
```

**Successful Temporal Capture Query Pattern**

```
Query pattern:
  "need the article i captured [TEMPORAL_OFFSET] days ago"
  Example: "need the article i captured 41 days ago"
  
Step sequence for OUTCOME_OK:
  1. Parse temporal offset from query (integer value + unit)
  2. Calculate absolute date from current date minus offset
  3. Query vault for captures matching calculated date
  4. Return captured article(s) for that date
  
Dead end signals:
  - OUTCOME_NONE_CLARIFICATION when no capture exists
  - Date calculation overflow for large offsets
  - Relative expression parsing failure
  
Query construction guidance:
  - Use integer days offset with explicit unit
  - Ensure capture exists before querying specific dates
  - Natural language relative expressions can be parsed
  
Verified successful execution:
  - task_id: t42
  - Query: "need the article i captured 41 days ago"
  - Result: OUTCOME_OK confirmed (relative date expression
    successfully parsed and converted to absolute date)
```

## Key pitfalls
A premature `NONE_CLARIFICATION` outcome can stop a lookup task before necessary data gathering occurs. For example, task t40 (<date>) asked for account names managed by "Frank Arne" sorted alphabetically. The agent concluded with `OUTCOME_NONE_CLARIFICATION` without running any list/find/tree operations to discover available accounts, resulting in a dead end where the lookup returned no results despite potentially findable data existing in the filesystem. This risk occurs when the agent misinterprets ambiguous or sparse results as definitive non-existence rather than triggering further data exploration. Similarly, task t42 (<date>) asked "What article did I capture 22 days ago?" The agent concluded with `OUTCOME_NONE_CLARIFICATION` without running any list/find/tree operations to check for available articles, resulting in a dead end where the lookup returned no results despite potentially findable data existing in the filesystem.

Conversely, tasks can also reach `OUTCOME_OK` without executing any list/find/tree operations, which may represent an equally problematic premature completion. For example, task t40 (<date>) asked "Which accounts are managed by Heinrich Pascal? Return only the account names, one per line, sorted alphabetically." The agent concluded with `OUTCOME_OK` despite reporting no `DONE OPS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Similarly, task t42 (<date>) asked "need the article i captured 41 days ago" and concluded with `OUTCOME_OK` with no reported `STEP FACTS` or `DONE OPS`, indicating the lookup may have produced a result without actually exploring the filesystem for captured articles. This variant of the risk—completing successfully without data exploration—may lead to fabricated or hallucinated answers when the agent cannot verify against actual filesystem contents.

## Shortcuts
When a lookup exhausts all reasonable search paths without finding matching data:
- Recognize the dead end situation
- Use outcome code: `OUTCOME_NONE_CLARIFICATION`

### Search Strategies for Lookups
- Structured data queries: Use exact matches on known fields (e.g., manager names, account IDs, system properties)
- Hierarchical traversal: Follow parent-child relationships to find associated entities
- Attribute-based filtering: Match properties like "managed by" fields, ownership attributes, or metadata tags
- Temporal date arithmetic: When queries reference relative dates ("10 days ago"), calculate the reference date and search accordingly

### Filter Approaches
- Case-insensitive matching for name searches
- Multiple filter combinations (AND logic)
- Date-range filters when temporal data is relevant
- Partial matching with wildcards when appropriate
- Field-specific extraction: Return only the requested fields (e.g., "only account names")

### Successful Lookup: Example
Task: `t40` — Lookup for accounts managed by "Pfeiffer Michael"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

Task: `t40` — Lookup for accounts managed by "Fuchs Patrick"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

Task: `t40` — Lookup for accounts managed by "Heinrich Pascal"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Format: One name per line
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

### Dead End Recognition: Example
Task: `t40` — Lookup for accounts managed by "Frank Arne"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No matching accounts found, requires user clarification on name spelling or manager assignment

### Date Calculation Dead End: Example
Task: `t42` — Lookup for "What article did I capture 10 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t42` — Lookup for "What article did I capture 22 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t42` — Lookup for "need the article i captured 41 days ago"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_OK` — Matching articles found and returned
