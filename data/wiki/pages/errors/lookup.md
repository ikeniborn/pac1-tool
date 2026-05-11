<!-- wiki:meta
category: errors/lookup
quality: nascent
fragment_count: 4
fragment_ids: [t01_20260511T111747Z, t04_20260511T121123Z, t08_20260511T121802Z, t12_20260511T123908Z]
last_synthesized: 2026-05-11
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Direct Catalog Lookup**: Queries specifying Brand, Product Line, and Attributes (e.g., Color, Length) can resolve with `OUTCOME_OK` without recorded file operations (t01).
- **Count Queries**: Category-based product count requests (e.g., "Lawn Mower") utilize `<COUNT:n>` output formatting (t12).
- **Attribute Filtering**: Successful lookups may filter by specific technical attributes (e.g., Adapter Type, Vehicle Type, Protection Type) alongside Brand and Line (t04, t08).

## Key pitfalls
- **False Matches:** Specific product lines (e.g., Caparol Premium Amphi, Valeo All Season) combined with attributes (color, protection type) risk false matches if existence is not verified.
- **Wrong Filters:** Multiple attribute constraints (length, adapter type, vehicle type) increase risk of wrong filters if applied before list/find/tree operations.
- **Premature NONE_CLARIFICATION:** Declaring no results before running list/find/tree operations leads to dead ends, especially on count queries (e.g., Lawn Mower catalogue) or detailed lookups.
- **Verification Gaps:** Tasks ending in dead ends often show no prior operations (DONE OPS: none), indicating list/find/tree steps were skipped before filtering or clarification.

## Shortcuts
- **Hierarchical Identification**: Narrow searches via Brand → Product Line → Model/SKU sequence to isolate specific items.
- **Composite Filtering**: Apply concurrent filters for technical specs (length, adapter, vehicle type) and properties (color, protection type).
- **Aggregation Handling**: Detect count intents (e.g., "How many") and return formatted totals exactly as requested (e.g., `<COUNT:n>`).
- **Natural Language Mapping**: Translate mixed identifiers in user queries to structured catalogue fields without losing specificity.
- **Strict Validation**: Verify all requested criteria are met before confirming availability or count accuracy.
