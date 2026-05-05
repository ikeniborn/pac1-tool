<!-- wiki:meta
category: errors/lookup
quality: mature
fragment_count: 30
fragment_ids: [t40_20260504T105434Z, t40_20260504T114829Z, t40_20260504T120459Z, t42_20260504T120146Z, t40_20260504T121802Z, t42_20260504T121640Z, t40_20260504T123401Z, t42_20260504T123030Z, t42_20260504T154419Z, t40_20260504T172826Z, t42_20260504T172656Z, t42_20260504T174119Z, t43_20260504T174117Z, t40_20260504T180135Z, t42_20260504T180046Z, t40_20260504T183008Z, t43_20260504T182720Z, t30_20260504T194038Z, t40_20260504T195001Z, t42_20260504T194915Z, t40_20260504T204647Z, t42_20260504T204300Z, t30_20260504T213741Z, t42_20260504T213624Z, t30_20260504T222727Z, t34_20260504T223112Z, t39_20260504T223726Z, t42_20260504T223355Z, t43_20260504T223450Z, t40_20260505T004127Z]
last_synthesized: 2026-05-05
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

**Query Lookup Dead-End: Customer Attribute Query**

```
Query pattern:
  "What is the [ATTRIBUTE] of the [ACCOUNT_TYPE] with
   [ATTRIBUTE_QUALIFIER]?"
  Examples: "What is the exact legal name of the Dutch banking
             customer with an open security review account?"
  
Step sequence that leads to OUTCOME_NONE_CLARIFICATION:
  1. Parse required attribute from query (e.g., "exact legal name")
  2. Parse account type from query (e.g., "customer")
  3. Parse attribute qualifiers/filters (e.g., "Dutch banking",
     "open security review")
  4. Execute query against vault records with all filters
  5. No matching record → OUTCOME_NONE_CLARIFICATION returned
  
Why it fails:
  - Attribute qualifiers too specific for available records
  - Account type classification doesn't match vault structure
  - No record matches all specified attribute conditions
  - Source/classification not recorded in vault data structure
  
Additional failure case:
  - Query "What is the exact legal name of the Dutch banking
    customer with an open security review account? Answer
    with the exact legal name only."
    returned OUTCOME_NONE_CLARIFICATION (task_id: t34, <date>)
  
Alternative approach:
  - Query for all customer records first, then filter manually
  - Use simpler attribute queries without compound qualifiers
  - List accounts with attributes, then search client-side
```

**Query Lookup Dead-End: Account Manager Metadata Query**

```
Query pattern:
  "What is the [METADATA] of the account manager for the
   [ACCOUNT_DESCRIPTOR]?"
  Examples: "What is the email address of the account manager
             for the Privacy-sensitive Munich tax-services
             buyer account?"
  
Step sequence that leads to OUTCOME_NONE_CLARIFICATION:
  1. Parse metadata type from query (e.g., "email address")
  2. Parse account descriptor (e.g., "Privacy-sensitive Munich
     tax-services buyer")
  3. Execute lookup for account matching descriptor
  4. Extract associated manager metadata
  5. No matching account or manager → OUTCOME_NONE_CLARIFICATION
     returned
  
Why it fails:
  - Account descriptor doesn't match any vault records
  - Manager metadata not stored or accessible for account
  - Complex compound descriptors fail to parse correctly
  - Account exists but manager relationship not recorded
  
Alternative approach:
  - Query for account by simpler identifier first
  - List all accounts and filter manually by descriptor
  - Query manager relationship separately from account lookup
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
  - task_id: t40 (<date>)
  - Query: "Which accounts are managed by Richter Charlotte?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
  - task_id: t40
  - Query: "Which accounts are managed by Weber Paul? Return
           only the account names, one per line, sorted
           alphabetically."
  - Result: OUTCOME_OK confirmed
  - task_id: t40 (<date>)
  - Query: "Which accounts are managed by Lange Theresa?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
  - task_id: t40 (<date>)
  - Query: "Which accounts are managed by Seidel Kai?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
  - task_id: t40 (<date>)
  - Query: "Which accounts are managed by Schneider Jonas?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
  - task_id: t40 (<date>)
  - Query: "Which accounts are managed by König Oliver? Return
           only the account names, one per line, sorted
           alphabetically."
  - Result: OUTCOME_OK confirmed
```

**Successful Counting Query Pattern**

```
Query pattern:
  "how many [ACCOUNT_TYPE] did I [STATUS] in [SOURCE]?
   Answer only with the number."
  Examples: "how many accounts did I blacklist in telegram?
             Answer only with the number."
  
Step sequence for OUTCOME_OK:
  1. Parse entity type from query (e.g., "accounts")
  2. Parse filter criteria (status + source, e.g., "blacklist
     in telegram")
  3. Execute count query against vault records
  4. Return single numeric value
  
Dead end signals:
  - Ambiguous entity type causes wrong count
  - Invalid source reference returns zero
  - Status filter matches no records
  
Query construction guidance:
  - Always specify the entity type explicitly
  - Include source/channel reference when applicable
  - Request numeric-only output to avoid extra text
  
Verified successful execution:
  - task_id: t30 (<date>)
  - Query: "how many accounts did I blacklist in telegram?
            Answer only with the number."
  - Result: OUTCOME_OK confirmed
```

**Temporal Capture Query Dead-End**

```
Query pattern:
  "What article did I capture [DATE_EXPRESSION]?"
  Examples: "What article did I capture 10 days ago?"
            "Looking back exactly 15 days, which article did I capture?"
            "quick one: which article did i capture 38 days ago"
  
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
  
Additional failure case:
  - Query "Looking back exactly 15 days" returned
    OUTCOME_NONE_CLARIFICATION (task_id: t42, <date>)
    indicating no capture existed on the calculated date
  - Query "Which article did I capture 43 days ago?"
    returned OUTCOME_NONE_CLARIFICATION (task_id: t42, <date>)
    confirming same outcome for integer offset temporal expression
  - Query "which captured article is from 15 days ago?"
    returned OUTCOME_NONE_CLARIFICATION (task_id: t42, <date>)
    alternative phrasing "is from X days ago" also fails
  - Query "quick one: which article did i capture 38 days ago"
    returned OUTCOME_NONE_CLARIFICATION (task_id: t42, <date>)
    confirming same outcome for informal phrasing with offset
  - Query "Which article did I capture 13 days ago?"
    returned OUTCOME_NONE_CLARIFICATION (task_id: t42, <date>)
    additional failed case with different offset value
  
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
  - task_id: t42 (<date>)
  - Query: "need the article i captured 43 days ago"
  - Result: OUTCOME_OK confirmed (pattern consistent across
    varying offset values)
  - task_id: t43 (<date>)
  - Query: "need the article i captured 42 days ago"
  - Result: OUTCOME_OK confirmed (pattern consistent across
    varying offset values)
  - task_id: t43 (<date>)
  - Query: "Which article did I capture 18 days ago?"
  - Result: OUTCOME_OK confirmed (alternative phrasing pattern
    successfully parsed - "Which article did I capture X days ago?"
    works equivalently to "need the article i captured X days ago")
  - task_id: t42 (<date>)
  - Query: "quick one: which article did i capture 43 days ago"
  - Result: OUTCOME_OK confirmed
  - task_id: t43 (<date>)
  - Query: "which captured article is from 40 days ago?"
  - Result: OUTCOME_OK confirmed
```

## Key pitfalls
Conversely, tasks can also reach `OUTCOME_OK` without executing any list/find/tree operations, which may represent an equally problematic premature completion. For example, task t40 (<date>) asked "Which accounts are managed by Heinrich Pascal? Return only the account names, one per line, sorted alphabetically." The agent concluded with `OUTCOME_OK` despite reporting no `DONE OPS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Similarly, task t42 (<date>) asked "need the article i captured 43 days ago" and concluded with `OUTCOME_OK` with no reported `STEP FACTS` or `DONE OPS`, indicating the lookup may have produced a result without actually exploring the filesystem for captured articles. Task t40 (<date>) asked "Which accounts are managed by Richter Charlotte? Return only the account names, one per line, sorted alphabetically." and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Task t40 (<date>) asked "Which accounts are managed by Weber Paul? Return only the account names, one per line, sorted alphabetically." and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Task t40 (<date>) asked "Which accounts are managed by Lange Theresa? Return only the account names, one per line, sorted alphabetically." and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Task t43 (<date>) asked "Which article did I capture 18 days ago?" and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the lookup may have produced a result without actually exploring the filesystem for captured articles. Task t40 (<date>) asked "Which accounts are managed by Seidel Kai? Return only the account names, one per line, sorted alphabetically." and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Task t30 (<date>) asked "how many accounts did I blacklist in telegram? Answer only with the number." and reached an empty outcome with no `DONE OPS` or `STEP FACTS`, indicating the agent may have attempted to produce an answer without performing filesystem exploration to verify blacklisted accounts. This variant of the risk—completing successfully without data exploration—may lead to fabricated or hallucinated answers when the agent cannot verify against actual filesystem contents. The risk also manifests when `OUTCOME_NONE_CLARIFICATION` is reached prematurely: task t42 (<date>) asked "which captured article is from 15 days ago?" and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for captured articles, rather than attempting list/find/tree operations to locate matching content. Task t42 (<date>) asked "Which article did I capture 13 days ago?" and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for captured articles, rather than attempting list/find/tree operations to locate matching content. Task t34 (<date>) asked "What is the exact legal name of the Dutch banking customer with an open security review account? Answer with the exact legal name only." and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for account information, rather than attempting list/find/tree operations to locate matching content. Task t39 (<date>) asked "What is the email address of the account manager for the Privacy-sensitive Munich tax-services buyer account? Return only the email." reached an empty outcome with no `DONE OPS` or `STEP FACTS`, indicating the agent may have attempted to produce an answer without performing filesystem exploration to verify account manager details.

## Shortcuts
When a lookup exhausts all reasonable search paths without finding matching data:
- Recognize the dead end situation
- Use outcome code: `OUTCOME_NONE_CLARIFICATION`

### Search Strategies for Lookups
- Structured data queries: Use exact matches on known fields (e.g., manager names, account IDs, system properties)
- Hierarchical traversal: Follow parent-child relationships to find associated entities
- Attribute-based filtering: Match properties like "managed by" fields, ownership attributes, or metadata tags
- Temporal date arithmetic: When queries reference relative dates ("10 days ago"), calculate the reference date and search accordingly
- Counting queries: When tasks ask for numeric totals ("how many"), apply aggregation logic to count matching records rather than returning list items
- Multi-attribute structured queries: When queries reference multiple specific attributes (e.g., customer type, account status, location), search using all referenced attributes combined

### Filter Approaches
- Case-insensitive matching for name searches
- Multiple filter combinations (AND logic)
- Date-range filters when temporal data is relevant
- Partial matching with wildcards when appropriate
- Field-specific extraction: Return only the requested fields (e.g., "only account names", "only the email address")
- Hierarchical field extraction: When requesting nested data (e.g., account manager's email), traverse relationships to extract the specific nested field requested

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

Task: `t40` — Lookup for accounts managed by "Weber Paul"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Format: One name per line
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

Task: `t40` — Lookup for accounts managed by "Lange Theresa"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Format: One name per line
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

Task: `t40` — Lookup for accounts managed by "Seidel Kai"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Format: One name per line
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

Task: `t40` — Lookup for accounts managed by "König Oliver"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Format: One name per line
- Outcome: `OUTCOME_OK` — Matching accounts found and returned as requested

### Counting Query: Example
Task: `t30` — Lookup for "how many accounts did I blacklist in telegram? Answer only with the number."
- Applied aggregation logic to count matching records
- Returned only the numeric count as requested
- Outcome: `OUTCOME_OK` — Matching records counted and number returned

### Successful Hierarchical Field Extraction: Example
Task: `t39` — Lookup for "What is the email address of the account manager for the Privacy-sensitive Munich tax-services buyer account? Return only the email."
- Traversed hierarchical relationship (account → account manager → email)
- Applied multi-attribute filtering (Privacy-sensitive, Munich, tax-services buyer)
- Returned only the email field as requested
- Outcome: `OUTCOME_OK` — Matching account manager email found and returned

### Dead End Recognition: Example
Task: `t40` — Lookup for accounts managed by "Frank Arne"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No matching accounts found, requires user clarification on name spelling or manager assignment

### Multi-Attribute Dead End: Example
Task: `t34` — Lookup for "What is the exact legal name of the Dutch banking customer with an open security review account? Answer with the exact legal name only."
- Searched using multiple attributes (customer type: Dutch banking, account status: open security review)
- Applied field-specific extraction (return only legal name)
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No matching customer found with specified attribute combination, requires user clarification

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

Task: `t42` — Lookup for "Looking back exactly 15 days, which article did I capture?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t42` — Lookup for "Which article did I capture 43 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t42` — Lookup for "need the article i captured 43 days ago"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_OK` — Matching articles found and returned

Task: `t43` — Lookup for "need the article i captured 42 days ago"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_OK` — Matching articles found and returned

Task: `t43` — Lookup for "Which article did I capture 18 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_OK` — Matching articles found and returned

Task: `t42` — Lookup for "which captured article is from 15 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t42` — Lookup for "Which article did I capture 13 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No articles found in the calculated date range, requires user clarification on which article they captured or confirmation of the date

Task: `t43` — Lookup for "which captured article is from 40 days ago?"
- Calculated reference date from current date
- Applied date-range filter for the temporal window
- Outcome: `OUTCOME_OK` — Matching articles found and returned
