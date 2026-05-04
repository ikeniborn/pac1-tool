<!-- wiki:meta
category: temporal
quality: nascent
fragment_count: 1
fragment_ids: [t43_20260504T121542Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Temporal Query Pattern: Date-Relative Resolution**

When resolving date-relative queries, the core mechanism involves:

1. **Anchor Derivation**: Calculate the reference date by applying the relative offset to the current context date.
   - For task t43: context date <date> minus 19 days = anchor date <date>

2. **Vault Anchor**: Use the derived anchor date to locate the relevant vault entry or capture record associated with that temporal position.

3. **Candidate File Inversion**: When standard forward-scanning fails, invert the search approach:
   - Identify candidate dates within the expected range
   - Search backward from the anchor date
   - Match against stored capture metadata

**Example Workflow (t43):**
```
Input: "Looking back exactly 19 days, which article did I capture?"
Context date: <date>
Calculation: <date> - 19 days = <date>
Vault lookup: retrieve article captured on <date>
Result: [article identification via vault anchor]
```

This pattern ensures accurate temporal anchoring for retrospective queries where the user seeks historical capture records.

## Key pitfalls
**Risk: System-Clock vs Vault-Time Temporal Confusion**

Temporal queries using relative offsets (e.g., "19 days ago," "last month," "yesterday") are prone to confusion between the agent's system clock and the actual timestamp metadata stored in the vault. If the agent resolves "look back exactly 19 days" against its own system time rather than the vault's recorded capture timestamps, it will anchor on the wrong date range, causing tasks to be matched against incorrect temporal boundaries.

**Risk: Wrong Temporal Anchor Selection**

When processing temporal filters, the agent may select an incorrect anchor point—such as using a file's modification date instead of its capture date, or defaulting to the current system date when the user intended a historical vault reference. This produces incorrect or empty result sets for date-anchored queries.

**Risk: Premature NONE_CLARIFICATION on Temporal Queries**

The agent may emit `NONE_CLARIFICATION` for temporal queries before exhausting all available resolution paths. For queries like "which article did I capture 19 days ago?", the agent should attempt to resolve the relative date, query the vault index with that resolved anchor, and optionally use `find` or `list` operations with date filters before declaring the query unresolvable. Premature abandonment leads to unnecessary clarification prompts when the data exists but the temporal interpretation failed.

## Shortcuts
When a temporal query asks "looking back N days", the system inverts the relationship using the candidate inversion formula:

```
implied_today = file_date + N
file_date = implied_today - N
```

**VAULT_DATE as lower bound**: The VAULT_DATE establishes the earliest permissible date. If the calculated file_date would predate VAULT_DATE, the query is invalid or no artifact exists in that window.

**ESTIMATED_TODAY derivation**: When a specific date is absent from the task context, ESTIMATED_TODAY is derived by working backwards from known file dates using the inversion formula. For the query "looking back exactly 19 days", the system computes:

```
if ESTIMATED_TODAY is known: target_file_date = ESTIMATED_TODAY - 19
if ESTIMATED_TODAY is unknown: candidate implied_today = file_date + 19
```

**Outcome handling for t43**: The task date of <date> with N=19 produces a target of <date>. When OUTCOME_NONE_CLARIFICATION is returned, this indicates no article artifact was found at the calculated file_date, requiring either verification of the ESTIMATED_TODAY value or confirmation that the artifact predates VAULT_DATE.

## Verified refusal: t43 (2026-05-04)
<!-- refusal: t43:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** Looking back exactly 19 days, which article did I capture?

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** (unspecified)

**Probes before refusal:**
1. ?

**Applies when:** temporal
