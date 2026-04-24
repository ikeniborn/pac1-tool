## Truncated/Ambiguous Task Input
- Condition: User task text is cut off mid-word or mid-sentence (e.g., "Create captur", "Process this inbox ent") leaving intent underspecified.
- Root cause: Agent attempted to act or report completion on an incomplete instruction instead of requesting clarification, resulting in INVALID_ARGUMENT on reportTaskCompletion.
- Solution: Detect truncated input (trailing partial tokens, missing object/target) and return a clarification request to the user before invoking any tool; do not call reportTaskCompletion until the task is fully specified.

## Invalid reportTaskCompletion Arguments
- Condition: `reporttaskcompletion` call fails with ERROR INVALID_ARGUMENT.
- Root cause: The completion call was issued with missing or malformed required fields (e.g., no outcome, no task_id, or called before any operation was performed).
- Solution: Populate all required arguments (task_id, outcome enum, summary) and only invoke reportTaskCompletion after the task has been either executed or explicitly resolved as a clarification; validate argument schema before the call.

## Missing Required Schema Field (account_id)
- Condition: Task requests creating a domain record (e.g., invoice SR-13 with line items) but provides no value for a required field defined by the directory's README/schema (e.g., `account_id`).
- Root cause: Agent has a fully-specified surface request but the local schema (discovered via README.MD) mandates fields the user did not supply; proceeding would fabricate data, and completing silently would produce an invalid record.
- Solution: Before writing, read the directory README/schema, diff required fields against the task input, and if any required field is unresolvable from context, return OUTCOME_NONE_CLARIFICATION asking the user for the missing values instead of inventing them.

## Fabricated Writes on Truncated Inbox Task
- Condition: Task text is truncated (e.g., "Process this inbox ent") yet the agent proceeds to write multiple distill cards, threads, and changelog entries before reporting OUTCOME_OK.
- Root cause: Agent invented a plausible inbox-processing workflow and produced derivative artifacts (cards/threads/changelog) without an identified source inbox entry, conflating "process inbox" with "synthesize new content from memory".
- Solution: On truncated/under-specified inbox tasks, do not emit any writes; request clarification identifying the specific inbox entry (path or ID) before reading sources or producing distill artifacts.
