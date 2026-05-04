<!-- wiki:meta
category: errors/default
quality: mature
fragment_count: 25
fragment_ids: [t13_20260503T205916Z, t40_20260503T210241Z, t41_20260503T210345Z, t42_20260503T210031Z, t13_20260503T210928Z, t40_20260503T211217Z, t41_20260503T210910Z, t42_20260503T210846Z, t13_20260503T211758Z, t41_20260503T211755Z, t42_20260503T211714Z, t43_20260503T211853Z, t13_20260503T212508Z, t40_20260503T212704Z, t41_20260503T212640Z, t42_20260503T212548Z, t13_20260503T213243Z, t40_20260503T213508Z, t41_20260503T213147Z, t42_20260503T213134Z, t43_20260503T213209Z, t42_20260504T105415Z, t42_20260504T114647Z, t43_20260504T120202Z, t41_20260504T122901Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
Outcome: <date>
What failed:
- (see outcome above)

## Dead end: t41
Outcome: <date>
What failed:

## Key pitfalls
- **Inability to answer simple date-based questions**: The agent failed to determine the day after tomorrow, indicating a lack of real-time date/time awareness or external tool integration for temporal calculations. Confirmed by repeated failures on simple relative date queries (e.g., "what date is in 1 week?"), which undermines any downstream task requiring date math, including scheduling.
- **Failure to retrieve managed account information**: Querying accounts by handler (e.g., "which accounts are managed by Adler Svenja?") resulted in dead ends, suggesting missing or incomplete database linking between personnel and account records. Verified with additional query for Hartmann Tobias also returning no results, indicating the issue extends beyond a single personnel record.
- **Poor historical data retention**: The agent could not identify a previously captured article from 45 days ago, indicating insufficient memory tracking, inconsistent naming conventions, or lack of persistent archive metadata. Extended to shorter windows: even articles captured 4 days ago could not be recalled, suggesting the capture mechanism lacks reliable indexing and retrieval paths. The same limitation prevents retrieval of articles from 49 days ago, showing the failure is not window-dependent but a fundamental indexing gap.
- **Incomplete follow-up scheduling**: Tasks requiring rescheduling or future action tracking (e.g., two-week follow-up for Nordlicht Health) may be lost or mishandled, pointing to gaps in agenda or reminder management. Exacerbated by the agent's inability to perform date calculations required to determine target dates. Direct attempts to reschedule such follow-ups result in dead ends, confirming the scheduling system cannot process time-based task management.

## Shortcuts
**Dead-end Task Analysis: t13**
- **Pattern**: Rescheduling follow-up requests
- **Insight**: When rescheduling, minimize changes to existing calendar entries ("keep the diff focused" indicates preference for surgical edits over wholesale replacement)

**Dead-end Task Analysis: t40**
- **Pattern**: Account enumeration queries
- **Insight**: List queries require strict output formatting — names only, one per line, alphabetically sorted. Any extra data breaks expected output format.

**Dead-end Task Analysis: t41**
- **Pattern**: Relative date calculations
- **Insight**: Date queries demand exact format compliance (DD-MM-YYYY). Ambiguous date formats in responses will cause failure. Date format requirements are task-specific — must match exactly what is requested (YYYY-MM-DD, DD-MM-YYYY, etc.)

**Dead-end Task Analysis: t42**
- **Pattern**: Historical content retrieval using temporal offsets
- **Insight**: Requires calculating a past date from "N days ago" and then matching against captured/archived content. Without reliable date metadata on captures, this query type dead-ends. Retrieval appears limited to relatively recent captures; extended temporal offsets (35+ days) likely exceed available capture window. Even short temporal offsets (7 days) fail when date metadata on captures is absent — the core limitation is not the offset distance but the lack of temporal reference data on archived content.

**Dead-end Task Analysis: t43**
- **Pattern**: Content identification via temporal offset
- **Insight**: Queries asking "which one was it from N days ago" fail because captures lack timestamp metadata. Without date/time data associated with each capture, the system cannot match temporal references to specific archived items.

## Dead end: t42
Outcome: 
What failed: Attempted to retrieve a previously captured article by asking for one captured 7 days ago. The task failed because the agent lacks capability to list, search, or recall past captured articles from memory. No metadata or index of captures appears to be maintained.
