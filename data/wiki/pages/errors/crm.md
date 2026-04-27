## Read-Before-Write Omission on Mismatched Reminder
- Condition: Agent locates a reminder file (via search or direct lookup) and applies updates without verifying the `account_id` field inside matches the target account_id.
- Root cause: Reminder filename matching doesn't guarantee correct account ownership. Directory search may rank by line-match position rather than semantic relevance; a file from a different account may be returned first. Agent skips this validation.
- Solution: After reading any reminder file, assert `reminder.account_id == target_account_id` before computing changes. If mismatch, continue searching for the correct file instead of modifying the wrong record.

## Exploration Stall — Write Deferred Indefinitely
- Condition: Agent reads all required files and computes the correct new value but issues 6–14 explore steps before executing `Req_Write`.
- Root cause: Agent re-reads already-visited files or re-queries search instead of committing the computed write, usually due to unresolved internal uncertainty about which file is canonical. May also manifest as attempts to read non-existent auxiliary documents (e.g. `/docs/follow-up-audit.json`) before proceeding.
- Solution: After reading both the account file and the matching reminder file, immediately write both updates in a single pass. Do not re-read either file unless the write explicitly fails. If an auxiliary reference file is not found, proceed with information already gathered rather than stalling.

## Repeated Identical Write Call Without Progress
- Condition: Agent calls `Req_Write` with the same path and payload 3 or more times consecutively without the write succeeding.
- Root cause: Agent does not inspect the write result and loops on the same failing call, possibly because a prior read left the file handle in an unexpected state.
- Solution: Check the return value of every `Req_Write`. On failure, read the error, adjust arguments or path, and retry once. On a second failure, surface the error rather than looping.

## Diff Scope Violation — Unrelated Fields Modified
- Condition: Task instructs "keep the diff focused" but agent updates fields beyond `due_on` and `next_follow_up_on`.
- Root cause: Agent applies a broad account-update template that touches all writable fields instead of patching only the specified date fields.
- Solution: Identify the minimal set of fields the task names, patch only those, and leave all other fields in their existing state.

## Ghost Reference Read — Non-Existent Auxiliary File
- Condition: Agent attempts to read a file such as `/docs/follow-up-audit.json` (or similar audit/reference document) that does not exist in the vault, receiving `NOT_FOUND`, and repeats the attempt or stalls instead of proceeding.
- Root cause: Agent assumes a canonical reference document exists to guide the operation; when it is absent the agent loops on the failed read rather than falling back to information already in hand.
- Solution: On the first `NOT_FOUND` for any auxiliary reference file, do not retry the same path. Proceed immediately using the account and reminder files already read. Auxiliary docs are optional; their absence must not block writes.
