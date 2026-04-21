## Proven Step Sequences

**Date Arithmetic (relative reference)**
1. Extract VAULT_DATE from context — check one account record (`last_contacted_on`) if VAULT_DATE seems stale
2. Compute offset: "today"=0, "yesterday"=-1, "tomorrow"=+1, "N days ago"=-N, "in N days"=+N, "in N weeks"=+N×7
3. Format output per task constraint (YYYY-MM-DD or DD-MM-YYYY); emit raw value only when "Answer only" specified

**Temporal File Retrieval**
1. Compute target date from VAULT_DATE + offset
2. Search `/00_inbox/` then `/01_capture/[category]/` for files prefixed `YYYY-MM-DD__`
3. Return file content or report absence

## Key Risks and Pitfalls

- **VAULT_DATE staleness**: VAULT_DATE is estimated from file timestamps — for "what is today?" verify against `last_contacted_on` in an account record
- **CRM offset confusion**: The +8-day reschedule offset is CRM-ONLY — never apply it to temporal queries
- **Output format**: DD-MM-YYYY requires explicit rearrangement of ISO date as final step
- **Week conversion**: "in N weeks" = N×7 days before adding to VAULT_DATE
- **Raw output**: "Answer only YYYY-MM-DD" means no markdown, labels, or explanation — bare string only

## Task-Type Specific Insights

**Temporal Queries**
- Relative offsets map directly: "today"=0, "yesterday"=-1, "tomorrow"=+1, "day after tomorrow"=+2, "in N days"=+N, "N days ago"=-N, "in N weeks"=+N×7
- For pure calculation tasks (no file lookup), derive date from VAULT_DATE without filesystem operations
- For file retrieval, check `/00_inbox/` first (staging), then `/01_capture/[category]/` (processed)
- When task specifies output format constraint, apply format conversion as the last step before answering