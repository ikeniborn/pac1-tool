## Proven Step Sequences

### Account Lookup by Name
1. List `/accounts` to get candidate filenames
2. Read candidate files sequentially until account `name` or `industry` matches the query
3. Use the `id` field (e.g., `acct_009`) to cross-reference contacts and invoices

### Account via Contact
1. Resolve contact by name or email (see contacts.md)
2. Read `account_id` field from contact record
3. Read `/accounts/acct_{id}.json` for business context

### Account Update with Verification
1. Read target `/accounts/acct_{id}.json` to get current state
2. Modify JSON content and write to the same path
3. **Immediately re-read** the file to verify persistence and return the current state

### Filter Accounts by Field Value (e.g., Account Manager)
1. Iterate `/accounts/acct_{NNN}.json` sequentially starting from `001`
2. Read each file and inspect the target field (e.g., `account_manager`, `industry`, `status`)
3. Collect file IDs where field matches the query criteria
4. Stop at first non-existent ID or after covering the expected range

### Enumerate All Accounts for Cross-Account Analysis
1. Sequentially read `/accounts/acct_{NNN}.json` starting at `001` until reaching a file-not-found error
2. Aggregate required fields (`name`, `industry`, `account_manager`, `status`) from each record
3. Use collected data to answer aggregate queries (e.g., counts, lists by category)

### Full Vault Account Scan
1. Iterate sequentially from `acct_001` through `acct_010` (or until first not-found)
2. Read all fields in a single pass per file
3. Cache results to avoid redundant re-reads when answering multiple sub-queries

### Read-Then-Write Pattern
1. Read account file to capture current state
2. Write updated content to the same path
3. Re-read to confirm write succeeded and obtain authoritative return value

### Retry on Transient Read Errors
1. Attempt read of account file
2. On transient error (timeout, connection reset, server disconnect), retry the read immediately
3. Continue with task once successful read is obtained

## Key Risks and Pitfalls

- **Account ID does not predict company**: Account IDs (acct_001, acct_009, etc.) are vault-specific and change per randomization. Never assume a specific ID maps to a specific company — always look up by reading the file
- **Account manager names are vault-randomized**: The `account_manager` field values vary per session/vault and even across tasks for the same account ID. The same account ID shows different managers across tasks. Never hardcode expected manager names — always derive from current file reads
- **Account manager assignments are not persistent across tasks**: The same account ID shows different `account_manager` values across different task executions. Always read current state rather than assuming consistency within or across sessions
- **Manager field is highly volatile**: Across a single day's tasks, the same account ID can show multiple different manager names. Treat manager assignment as ephemeral per task invocation
- **Transient read failures require retry**: Read operations can fail with errors such as "timed out", "Connection reset by peer", "Server disconnected without sending a response", or generic "ERROR EXCEPTION". These are typically transient — retrying the same read often succeeds
- **Industry mismatch**: When searching by description (e.g., "AI insights"), compare the account's `industry` field to narrow candidates
- **Notes/reminders may use different status values**: Account JSON files may have `status: "active"`, `status: "churned"`, etc. — verify actual field content before reporting
- **Write verification required**: After writing to account files, always perform an immediate follow-up read to confirm persistence and retrieve the authoritative current state
- **Enumeration gaps**: When scanning sequentially, stop at the first missing ID (e.g., if acct_011 does not exist) to avoid unnecessary errors
- **Redundant reads are wasteful**: Reading the same account file multiple times in succession within a single task is redundant — extract all needed fields in a single read
- **Repeated reads of the same file in one task are unnecessary**: If the file content has not been modified, a single read is sufficient — multiple reads of unchanged files waste time without providing new information

## Task-Type Specific Insights

- **Email outreach**: Always read the account (`accounts/acct_{id}.json`) after resolving the contact — it provides the business context (company name, industry) needed for accurate outreach emails and must be included in grounding_refs
- **Invoice lookup**: Use `account_id` from the account file to filter `/my-invoices/` — do not rely on filenames alone
- **CRM reschedule**: Both the account's `next_follow_up_on` field and the reminder's date field must be updated when rescheduling follow-ups
- **Cross-account aggregation**: Tasks requiring data from multiple accounts (e.g., "Which accounts are managed by X", "List all active accounts") require sequential iteration since there is no index file; cache results if multiple derivations are needed from the same scan
- **Bulk account updates**: When updating multiple accounts, process each with an individual read-write-read cycle; do not assume batch write patterns
- **Avoid redundant reads**: Tasks requiring multiple pieces of data from the same account (e.g., name and industry) should extract all needed fields in a single read operation rather than re-reading the file
- **Verify after any write**: Even when no content changes were needed, the final read after a write confirms the authoritative state and provides the return value
- **Same account, different manager per task**: The same account ID may return different `account_manager` values in different task executions. When updating or referencing managers, always read the current file rather than assuming a previously-seen assignment persists
- **Full enumeration for email lookups**: Tasks asking for "email of X" across all accounts require scanning all account files — current vault contains accounts 001-010; account names and industries remain stable while managers change per task
- **Filtered enumeration for manager queries**: When looking for accounts managed by a specific person, only read account files that could match — skip obviously different industries if context is known, but do not assume manager stability based on observed assignments in other tasks
- **Account names and industries are stable**: Company names (e.g., "Nordlicht Health", "Acme Robotics") and industries are consistent across tasks for the same account ID — only manager assignments vary per task invocation
- **Handle transient read errors gracefully**: When encountering read timeouts, connection resets, or server disconnects, retry the read operation before escalating to error state — these failures are often transient and self-recovering
- **Cache stable account data separately**: Since company names and industries remain constant per account ID while managers fluctuate, consider caching the former when processing multiple queries that reference the same account
- **Single-pass data extraction**: When reading account files, extract all potentially-needed fields (name, industry, status, account_manager, contact info) in one read rather than planning to re-read later — this avoids redundant I/O and handles cases where the file might change between reads
- **Vault contains exactly 10 accounts**: The current vault includes accounts numbered 001 through 010 (acct_001 through acct_010); sequential scans should stop at 010 or first not-found error