<!-- wiki:meta
category: errors/temporal
quality: nascent
fragment_count: 4
fragment_ids: [t41_20260504T105853Z, t41_20260504T114832Z, t41_20260504T120108Z, t41_20260504T121803Z]
last_synthesized: 2026-05-04
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Proven Sequence: Simple Date Arithmetic (t41)**

1. **Vault Anchor Derivation**
   - Extract the reference date directly from the task context (`date: <date>`)
   - For relative queries, the anchor is the stated date, not the current system date
   - Anchor date format confirmed as `YYYY-MM-DD` (e.g., `<date>`)

2. **Candidate File Inversion Approach**
   - Not applicable for arithmetic-only queries with explicit date provided
   - Skip file-based lookup when date is self-contained in task metadata

3. **Execution Flow**
   - Parse offset from task text: `"in 2 days"` → `+2 days`
   - Apply arithmetic to anchor: `<date> + 2 days = <date>`
   - Format output per constraint: `DD-MM-YYYY` → `06-05-2026`
   - Verified with multiple offset sizes: `"in 16 days"` → `+16 days` applied to `<date>` = `<date>`
   - Output format dictated by task constraint (e.g., `YYYY-MM-DD` for `"Answer only YYYY-MM-DD"`)

4. **Outcome**: `OUTCOME_OK` — confirmed valid when anchor date is explicitly supplied
   - Confirmed: 16-day offset (<date> + 16 days = <date>) validates approach across various offset magnitudes
   - Confirmed: 5-day offset (<date> + 5 days) validates approach with minimal offset values
   - Confirmed: 19-day offset (<date> + 19 days = <date>) validates approach with YYYY-MM-DD output constraint satisfied

## Key pitfalls
Temporal Anchor Mismatch

The system maintains two distinct time references: system-clock (actual wall-clock time) and vault-time (the temporal context of the current task/operation). When these diverge, the agent may anchor calculations to the wrong reference point.

**Risk**: If the agent uses system-clock instead of vault-time, temporal arithmetic (e.g., "2 days from now") will be computed against the wrong baseline. For task t41, vault-time was <date>, but if the agent referenced system-clock, it would calculate against today's actual date rather than the vault's perceived "now".

**Risk**: Wrong temporal anchor. The agent may implicitly adopt the wrong "now" when processing temporal queries. For date arithmetic, it must use the vault's temporal context as the anchor, not infer from system time. In t41, the query "What date is in 5 days?" required the agent to recognize that "now" meant <date> (vault-time), not the system's actual current date.

**Risk**: Premature NONE_CLARIFICATION. If the agent resolves a temporal query without verifying it used the correct temporal anchor (vault-time vs. system-clock), it may provide a plausible but incorrect date. This is especially dangerous in list/find/tree operations that filter by date ranges—using the wrong anchor produces silent data mismatches rather than obvious errors. The t41 task type (temporal) with a simple "What date is in 5 days?" prompt illustrates how even straightforward queries require explicit anchor verification to avoid confusion.

**Mitigation**: Temporal tasks must explicitly identify and use vault-time as the calculation anchor. Before resolving date arithmetic, confirm the reference timestamp came from task metadata, not system clock. In t41, vault-time was <date> and the outcome was OUTCOME_OK, indicating the agent correctly anchored to vault-time rather than system-clock—but the "Dead end" label signals vigilance was required to avoid the anchor confusion. The "Dead end" annotation with an OUTCOME_OK status demonstrates that correct behavior was achieved through active vigilance, not by accident.

**Extension**: In a subsequent instance, t41 presented the query "What date is in 19 days?" with vault-time anchored to <date>. The OUTCOME_OK result confirms the agent correctly applied vault-time (<date>) as the temporal anchor, yielding <date> rather than deriving from system-clock. This reinforces that even when task metadata explicitly provides the vault date, the agent must actively use it as the calculation baseline—the absence of an error does not guarantee correct anchoring without explicit verification.

## Shortcuts
A simple date arithmetic query (`YYYY-MM-DD + N days`) completes successfully when given a known reference date. The outcome of `t41` demonstrates that temporal calculations are straightforward when the source date is explicitly provided, showing that date offset operations (adding 16 days to `<date>`) work reliably and produce a valid result. This suggests that temporal reasoning in the system operates on known anchors and derives other dates through arithmetic rather than inference.

The `t41` case with `<date>` as the anchor date confirms this pattern: when a reference date is provided, adding or subtracting days (N) produces accurate results, establishing the date as a viable VAULT_DATE or lower bound for temporal reasoning. The successful outcome of calculating "What date is in 5 days?" from the provided date validates the candidate inversion approach where implied_today or other derived dates can be computed through arithmetic operations (implied_today = file_date + N) when the source date functions as a known anchor. Specific examples like <date> as the anchor with a 19-day offset confirm this extends across varied reference dates and offset values, with the output format consistently requiring a clean `YYYY-MM-DD` result.

## Temporal Patterns
### VAULT_DATE as Lower Bound
- The vault contains files dated `<date>` indicating this is the most recent known temporal anchor
- VAULT_DATE establishes the lower bound for temporal calculations—assumed to be the agent's best estimate of "today"

### ESTIMATED_TODAY Derivation
- When explicit "today" is unavailable, ESTIMATED_TODAY may be derived from the most recent file modification date
- Example: If the newest file in the vault is dated `<date>`, ESTIMATED_TODAY is inferred as `<date>`

### Candidate Inversion (implied_today = file_date + N)
- When the task asks for a relative date (e.g., "what day is in 2 days?"), the agent must:
  1. Establish the reference date (VAULT_DATE or ESTIMATED_TODAY)
  2. Add the specified offset (N)
  3. Return the computed date in required format (DD-MM-YYYY)

- For task t41:
  - Given: date `<date>`, task `what day is in 2 days?`
  - Calculation: `<date>` + 2 days = `<date>`
  - Required format: `06-05-2026`
  - Outcome: OUTCOME_OK (indicating correct temporal computation)
