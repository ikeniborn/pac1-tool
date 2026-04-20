## Proven Step Sequences

**Temporal Capture Retrieval**
1. Calculate absolute target date from relative reference (e.g., "13 days ago" → specific ISO date)
2. List `/00_inbox/` for recent captures not yet archived
3. List `/01_capture/` subdirectories (e.g., `/influential/`) for organized storage
4. Match filename prefix `YYYY-MM-DD__` against calculated target date

**Relative Date Calculation (Context-Based)**
1. Extract VAULT_DATE from the line starting with `VAULT_DATE:` — this is the ONLY authoritative "today"
2. Compute offset directly: "tomorrow" = +1, "day after tomorrow" = +2, "in N days" = +N, "in N weeks" = +(N×7)
3. DO NOT apply any additional offsets — the +8-day rule is CRM-ONLY (rescheduling)
4. Format output per task specification (e.g., YYYY-MM-DD or DD-MM-YYYY)

**Pure Date Calculation (Zero Filesystem)**
1. Extract VAULT_DATE from context
2. Calculate target date: VAULT_DATE + N days (direct offset, no CRM adjustments; convert weeks to days: ×7)
3. Apply required output formatting (e.g., DD-MM-YYYY, YYYY-MM-DD)
4. Return formatted string directly without file read operations

## Key Risks and Pitfalls

- **Unparameterized searches**: Executing `search` without query strings wastes steps and returns zero matches
- **Stall warnings**: Read-only discovery sequences (listing without write operations) trigger warnings after 6 steps; batch directory listings or use filtered list parameters
- **Split storage assumption**: Recent captures often reside in `/00_inbox/` while processed items are filed under `/01_capture/[category]/`
- **Output format mismatch**: Temporal queries may mandate specific output formats (e.g., DD-MM-YYYY or YYYY-MM-YYYY); filename conventions may not match requirements
- **Context date staleness**: VAULT_DATE provides the reference "today"; verify offset calculations when crossing midnight or timezone boundaries
- **CRM offset confusion**: The PAC1 +8-day rule applies ONLY to CRM reschedule tasks (reminders/accounts). NEVER apply it to pure temporal queries ("tomorrow", "in N days")
- **Unnecessary file lookups**: Attempting to read files for pure date calculation tasks wastes steps; derive dates mathematically from VAULT_DATE alone
- **Duration unit errors**: Week-based references ("in 3 weeks") require conversion to days (×7) before adding to VAULT_DATE; treating weeks as days causes incorrect dates
- **Output constraint violations**: Tasks demanding format "only" (e.g., "DD-MM-YYYY only") fail if response includes markdown, code blocks, labels, or explanatory text; emit raw value only

## Task-Type Specific Insights

**Temporal Queries**
- **Immediate date math**: Convert relative time references to absolute ISO dates (YYYY-MM-DD) before filesystem operations
- **Filename convention**: System uses `YYYY-MM-DD__title.md` format—extract temporal data from filename prefixes rather than file metadata
- **Inbox priority**: For targets <30 days old, check `/00_inbox/` before categorized subdirectories; it serves as the staging buffer
- **Curated content location**: "Influential" captures are stored in `/01_capture/influential/` with preserved date prefixes
- **Contextual baseline**: Use VAULT_DATE from environment context as "today" for calculations without filesystem lookup
- **Explicit format compliance**: Tasks may require DD-MM-YYYY, YYYY-MM-DD, or other formats; apply formatting as final step before output
- **Direct offset**: Relative phrases ("tomorrow" = +1, "day after tomorrow" = +2, "in N days" = +N, "in N weeks" = +N×7) map directly to VAULT_DATE + offset. No additional environment offsets for temporal queries.
- **Calculation-only path**: Pure temporal queries without file retrieval need no filesystem operations; derive from VAULT_DATE and offsets only
- **Response-only tasks**: When asked "what day is in X days/weeks" with no file context needed, skip directory listings and calculate immediately
- **Minimal output**: Provide only the requested date value when task specifies "Answer only YYYY-MM-DD" or similar constraints; suppress explanatory text, markdown fences, and code blocks
- **Week-to-day conversion**: Explicitly multiply week counts by 7 to derive day offsets before applying to VAULT_DATE (21 days for 3 weeks)