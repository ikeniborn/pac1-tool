## Proven Step Sequences (OUTCOME_OK)

- **Contact file lookup**: Read from `/contacts/<file> using sequential ID pattern (`cont_NNN` or `mgr_NNN`)
- **JSON parsing workflow**: Parse returned JSON to extract `id`, `account_id`, `role`, `preferred_tone`, `last_seen_on` fields
- **Bulk contact discovery**: Chain multiple sequential reads (`<contact>` through `cont_NNN`) to enumerate account contacts
- **Manager contact access**: Use `mgr_NNN` prefix for internal staff contacts with tags array

## Key Risks and Pitfalls

- **Data volatility**: Same contact ID returns completely different person on repeated reads (e.g., `<contact>` returned 3 different names across tasks)
- **Identity inconsistency**: Same person appears under different contact IDs at different times
- **Role oscillation**: Single contact ID cycles through multiple roles (e.g., `<contact>` → QA Lead → Operations Director → Head of Engineering)
- **Redundant reads**: Identical reads repeated back-to-back (t14, t17, t35, t36) waste operations
- **Stale metadata**: `last_seen_on` dates range from <date> to <date>, indicating severely unrefreshed records
- **Email-ID dissociation**: Same email appears under different contact IDs (e.g., `<email>` at `<contact>` and `<contact>`)

## Task-Type Specific Insights and Shortcuts

- **File naming convention**: External contacts use `cont_NNN` prefix; internal staff use `mgr_NNN` prefix
- **Account linkage**: Each contact file contains `account_id` field for cross-referencing
- **Tone preferences**: Stored values include `formal`, `direct`, `brief`, `warm` — useful for communication tone selection
- **Tag extraction**: Manager contacts include tags array (e.g., `"account_manager"`, `"internal"`) for role classification
- **Data freshness check**: Always check `last_seen_on` field; large gaps indicate stale records requiring verification
- **Manager stability**: `mgr_NNN` contacts appear consistent (Ronja Barth reliable across reads) unlike volatile `cont_NNN` records
- **Multiple role types**: QA Lead and Operations Director appear frequently across different contacts
