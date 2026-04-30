<!-- wiki:meta
category: errors/lookup
quality: developing
fragment_count: 5
fragment_ids: [t30_20260430T140045Z, t40_20260430T140604Z, t42_20260430T140456Z, t30_20260430T165750Z, t40_20260430T170204Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Listing directories first** to see available files before reading (e.g., `list: /accounts` to see `README.MD`) provides structural overview before deep reads
- **Reading README or schema files first** establishes expected data formats and field names, which aids in constructing correct queries
- **Reading account files sequentially** (e.g., `<account>.json`, `<account>.json`) is necessary for full account audits, each file containing structured JSON with fields like `account_manager` for filtering
- **Search with empty pattern** can return file path matches (e.g., search results showing file locations and line numbers), useful for discovering relevant files before reading them
- **Timeouts on file reads** (e.g., `read: /docs/channels/telegram.txt` failing with "ERROR: The read operation timed out") mean some vault lookups are blocked by unavailable files; track which files timeout and consider retrying or skipping
- **Repeated stalls** (6+ reads without writes) indicate the agent is doing sequential discovery reads; for counting queries, consider whether a more efficient traversal method exists to avoid excessive individual file reads
- **Compliance and flags** can be queried by reading account files and checking fields like `compliance_flags` (array of flags per account)
- **Persistent read failures** (same file timing out on 2+ consecutive attempts with "EXCEPTION" and "path does not exist") signal the file is structurally unavailable rather than temporarily slow; track these and skip rather than retry indefinitely
- **Search with invalid or empty patterns** can return `INVALID_ARGUMENT` errors rather than empty results; ensure patterns are non-empty strings with actual characters before invoking search
- **Stall hints embed actionable error details** in the stall warning itself (e.g., "Error 'EXCEPTION' on path '/docs/channels/Telegram.txt' has occurred 2 times — path does not exist"), which may surface failure reasons earlier than waiting for explicit error line reads
- **Reading manager contact files first** (e.g., `search: <manager_name>` to find `mgr_XXX.json`) can establish manager-to-account relationships before iterating all account files, reducing total reads when a manager manages multiple accounts
- **Search may return no matches** for manager-related files even when the manager exists; when search returns empty results, fall back to listing the directory and reading files sequentially
- **Sequential account reading at scale** (10+ files) will generate repeated stall warnings up to and including `[STALL ESCALATION]` level; account for the fact that some manager lookup queries require reading all account files to confirm matches and are inherently multi-step

## Key pitfalls
- **Premature NONE_CLARIFICATION (t30):** The agent attempted to read `/docs/channels/telegram.txt` twice, receiving timeouts on both attempts. Instead of retrying with adjusted parameters, listing the parent directory to verify the file's existence and accessibility, or trying alternative approaches (e.g., splitting the path or checking for encoding issues), the agent abandoned the lookup and reported a dead end. The file existed in the filesystem but was never successfully accessed. In a subsequent run, the agent again attempted to read `/docs/channels/Telegram.txt` multiple times without first confirming the file's accessibility by listing the parent directory. Timeouts on file reads should trigger immediate verification of the path's validity before retrying the same operation.

- **Wrong filter behavior (t40):** The task asked for accounts managed by "Voigt Elisabeth." The agent read every account file individually (`<account>.json` through `<account>.json`) without applying any filter during search or list operations. This caused the agent to stall repeatedly after each read step without producing output. The correct approach would have been to use a targeted search query (e.g., searching for "account_manager" or the manager name) or to filter results programmatically rather than brute-forcing sequential reads. In a subsequent run, the task asked for accounts managed by "Pfeiffer Antonia." The agent found the manager file, identified the correct manager, then proceeded to read every account file sequentially (<account> through <account>) despite multiple stall warnings, continuing even after escalation. The agent never attempted a filtered search or programmatic filter and stuttered through 14+ read operations instead of narrowing the search space.

- **False match (t42):** The agent searched for a file captured 42 days prior to <date> (approximately <date>). The search returned `2026-02-10__how-i-use-claude-code.md`, which was approximately 79 days prior—nearly double the requested timespan. The agent accepted this result without validating the date arithmetic or recalculating the target capture date, leading to an incorrect answer.

## Shortcuts
## Lookup-specific Patterns: Search Strategies, Filter Approaches

### Search Pattern Requirements

- **Non-empty patterns required**: Search with empty or whitespace-only patterns returns `ERROR INVALID_ARGUMENT`. Always provide a valid search term.
- **Pattern validation**: Even a single whitespace character is invalid and causes `ERROR: invalid search pattern`.

### Search Result Structure

- Search results use format `path:lineNumber` (e.g., `contacts/<manager>.json:4`, `docs/channels/Telegram.txt:1`).
- Multiple results from the same file appear on separate lines.

### Path Accessibility Issues

- A path appearing in search results does not guarantee the path is currently accessible (e.g., `/docs/channels/Telegram.txt` appeared in results but all read attempts failed with timeout or exception).
- When repeated `read` failures occur, the system may report "path does not exist" even if the file name was found in search.
- **Strategy**: If a search locates a file but `read` repeatedly times out or throws exceptions, treat the path as unavailable after 2–3 attempts rather than continuing to retry.

### Filter Approaches for JSON Account Files

- Account data stored as individual JSON files (e.g., `/accounts/<file>).
- Key fields for filtering include `account_manager`, `name`, `industry`, `region`, `status`.
- When filtering by a manager name, read each account file individually and match the `account_manager` field.

### Stall Detection in Lookup Tasks

- Taking many sequential read operations without any write, delete, move, or create triggers stall warnings starting at ~6 steps.
- Stall escalation occurs at 12+ steps without action.
- **Mitigation**: After locating target data, prepare output immediately rather than continuing to explore unrelated files.

### Lookup Task Outcome Notes

- Both example tasks (`t30`, `t40`) show `OUTCOME: OUTCOME_OK` despite dead-end failures — this indicates the task completed but without finding the requested information.

## Lookup Patterns: Search Strategies and Filter Approaches
### Task-Driven File Discovery

When asked to look up specific information, begin by searching for relevant files in logical locations rather than assuming directory structures exist. If a direct file path times out, try a parent directory search instead. For example, `/docs/channels/telegram.txt` may fail, but `search` in `/docs/` or `/docs/channels/` can surface alternative sources. Use broad search queries first, then narrow based on results.

### Sequential File Enumeration for Account Data

When querying account records, iterate through numbered files systematically (`<account>.json`, `<account>.json`, etc.) rather than searching within files. Each read operation extracts the relevant field—in this case `account_manager`—to match against the query target. Normalize name variants during comparison: "Voigt Elisabeth" should match "Elisabeth Voigt" in the JSON field.

### Stall-Aware Progress Tracking

A stall counter increments each step without a write, delete, move, or create operation. When the counter reaches 6+ steps (especially during repeated reads), the pattern suggests the task may be stuck. Acknowledge the stall and either provide the accumulated answer or explicitly signal a dead end rather than continuing to read without producing output.

### Date-Based Content Retrieval

For time-offset queries like "42 days ago," calculate the target date relative to the current execution date, then search for matching filenames or content. Filename conventions like `YYYY-MM-DD__description.md` in capture directories (`01_capture/influential/`) provide reliable anchors. If the calculated date yields no matches, fall back to listing the capture directory structure to identify contents.

### Handle Search and Read Failures Gracefully

When a file read produces an error exception or timeout, do not retry indefinitely. Mark the read as failed, attempt an alternative approach (search in parent directory, list folder contents), and if no alternative succeeds, conclude with a dead-end result rather than stalling indefinitely.
