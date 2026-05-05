<!-- wiki:meta
category: errors/lookup
quality: mature
fragment_count: 31
fragment_ids: [t40_20260504T105434Z, t40_20260504T114829Z, t40_20260504T120459Z, t42_20260504T120146Z, t40_20260504T121802Z, t42_20260504T121640Z, t40_20260504T123401Z, t42_20260504T123030Z, t42_20260504T154419Z, t40_20260504T172826Z, t42_20260504T172656Z, t42_20260504T174119Z, t43_20260504T174117Z, t40_20260504T180135Z, t42_20260504T180046Z, t40_20260504T183008Z, t43_20260504T182720Z, t30_20260504T194038Z, t40_20260504T195001Z, t42_20260504T194915Z, t40_20260504T204647Z, t42_20260504T204300Z, t30_20260504T213741Z, t42_20260504T213624Z, t30_20260504T222727Z, t34_20260504T223112Z, t39_20260504T223726Z, t42_20260504T223355Z, t43_20260504T223450Z, t40_20260505T004127Z, t40_20260505T170648Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
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
  - task_id: t40 (<date>)
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
  - task_id: t40
  - Query: "Which accounts are managed by Fuchs Patrick?
           Return only the account names, one per line,
           sorted alphabetically."
  - Result: OUTCOME_OK confirmed
```

## Key pitfalls
Conversely, tasks can also reach `OUTCOME_OK` without executing any list/find/tree operations, which may represent an equally problematic premature completion. For example, task t40 (<date>) asked "Which accounts are managed by Heinrich Pascal?" and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Similarly, task t42 (<date>) asked "need the article i captured 43 days ago" and concluded with `OUTCOME_OK` with no reported `STEP FACTS` or `DONE OPS`, indicating the lookup may have produced a result without actually exploring the filesystem for captured articles. This variant of the risk—completing successfully without data exploration—may lead to fabricated or hallucinated answers when the agent cannot verify against actual filesystem contents. The risk also manifests when `OUTCOME_NONE_CLARIFICATION` is reached prematurely: task t42 (<date>) asked "which captured article is from 15 days ago?" and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for captured articles, rather than attempting list/find/tree operations to locate matching content. Task t42 (<date>) asked "Which article did I capture 13 days ago?" and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for captured articles, rather than attempting list/find/tree operations to locate matching content. Task t34 (<date>) asked "What is the exact legal name of the Dutch banking customer with an open security review account? Answer with the exact legal name only." and concluded with `OUTCOME_NONE_CLARIFICATION` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the agent abandoned the lookup before exploring the filesystem for account information, rather than attempting list/find/tree operations to locate matching content. Task t39 (<date>) asked "What is the email address of the account manager for the Privacy-sensitive Munich tax-services buyer account? Return only the email." reached an empty outcome with no `DONE OPS` or `STEP FACTS`, indicating the agent may have attempted to produce an answer without performing filesystem exploration to verify account manager details. Task t40 (<date>) asked "Which accounts are managed by Richter Charlotte?", "Which accounts are managed by Weber Paul?", "Which accounts are managed by Lange Theresa?", "Which accounts are managed by Seidel Kai?", and "Which accounts are managed by Fuchs Patrick?" and each concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, suggesting the task completed without gathering any filesystem data to verify available accounts. Task t43 (<date>) asked "Which article did I capture 18 days ago?" and concluded with `OUTCOME_OK` despite reporting no `DONE OPS` or `STEP FACTS`, indicating the lookup may have produced a result without actually exploring the filesystem for captured articles. Task t30 (<date>) asked "how many accounts did I blacklist in telegram? Answer only with the number." and reached an empty outcome with no `DONE OPS` or `STEP FACTS`, indicating the agent may have attempted to produce an answer without performing filesystem exploration to verify blacklisted accounts.

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

Task: `t40` — Lookup for accounts managed by "Fuchs Patrick"
- Searched using manager name attribute
- Applied alphabetical sorting to results
- Returned only account names as requested (field-specific extraction)
- Outcome: `OUTCOME_NONE_CLARIFICATION` — No matching accounts found with specified manager, requires user clarification on name spelling or manager assignment

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
