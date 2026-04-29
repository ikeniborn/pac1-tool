## Redundant File Reads in Session
- Condition: Agent reads the same file multiple times within a single task session (e.g., `<contact>.json`, `msg_001.txt` read twice in t20).
- Root cause: Agent does not retain or reference data previously read during the same session; it re-reads files when the content is needed again.
- Solution: Cache file contents in working memory during session; before reading, check if content was already retrieved in this task.

## Stalled Execution Without Action
- Condition: Agent receives consecutive "stall" hints (6+ steps without writing/deleting/creating) while listing or reading the same directory.
- Root cause: Agent gathers information but delays taking action—either waiting for more data or losing track of the primary goal.
- Solution: After 3+ stall hints, force a decision point: either write the output, escalate, or explicitly acknowledge insufficient data to proceed.

## Sequential Invoice Scan Instead of Filtering
- Condition: Agent iterates through invoice files one-by-one (`INV-006-01`, `INV-006-02`, ...) until manually stopping, rather than filtering by `account_id` first.
- Root cause: Agent lacks a filtering strategy for structured file collections; it performs linear scans to find records matching a specific field value.
- Solution: When searching invoice collections, use the `account_id` field to filter directory listings or perform targeted reads; avoid iterating through all invoices for an account when file names or directory structures support filtering.

## Post-Write File Exploration
- Condition: Agent writes the output file (e.g., `/outbox/<file>) then continues reading additional files (e.g., `/accounts/<file>) before task completion.
- Root cause: Agent does not recognize the write action as the terminal step for the current task; it continues exploring after the deliverable is produced.
- Solution: Treat the write confirmation as the task completion signal; any reads after the write should only occur if required for the write itself or explicitly triggered by a new task.
