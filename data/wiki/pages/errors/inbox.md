## Idempotent Delete Failure (Not Found)
- Condition: A file has already been successfully deleted within the session, but the agent re-attempts deletion in a subsequent step.
- Root cause: The agent does not track deleted-file state locally, so it retries an operation that already succeeded.
- Solution: Check the session's operation log or verify file existence before re-attempting a delete. Maintain a short in-memory list of deleted paths during the session.

## Write to Non-Existent Parent Directory
- Condition: Agent attempts to write a file to a path where one or more parent directories do not exist (e.g., `/01_capture/hn/...` when `/01_capture/hn` has not been created).
- Root cause: The agent assumes a directory structure exists without first confirming or creating it.
- Solution: Before writing to any path, call `mkdir` for the parent directory (or `mkdir -p` equivalent) to ensure the full path exists.

## Stall Loop Without Progress
- Condition: Agent repeatedly calls the same operation (e.g., `Req_Write` or `list`) with identical arguments 3+ times without any state change or side effect.
- Root cause: The agent lacks awareness that its actions are producing no progress and continues retrying the same failing approach (e.g., reading files in a loop).
- Solution: After 2 failed identical attempts, halt the current approach and consult documentation, try an alternative strategy, or escalate. Track attempt counts per operation.
