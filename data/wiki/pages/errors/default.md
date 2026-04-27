# Error Wiki — AI File-System Agent

## Stall Warning — Excessive Read Operations Before Action
- Condition: Agent performs 6+ sequential read, list, or search operations without executing any write, delete, or move operation
- Root cause: Agent gathers information exhaustively without establishing a clear decision point; defers action execution across multiple read steps
- Solution: Identify required action early in the task; commit to execution after establishing necessary facts; execute write/delete/move within the next step group to prevent stall warnings

## Unexecuted Inbox Action Request
- Condition: Inbox message contains explicit action directive (write email, send response, resend document, verify token, etc.); agent reads the message but task ends without executing that action
- Root cause: Agent treats inbox messages as information retrieval rather than action triggers; reads content but doesn't complete the action chain
- Solution: For each inbox message, extract the action request explicitly; execute that operation (compose email, initiate resend, verification response, etc.) within the same task before marking complete

## Incomplete Inbox Processing — Shallow Exploration
- Condition: Agent lists inbox directory contents but does not read individual message files; inbox processing task marked incomplete
- Root cause: Agent treats directory listing as completion of "process inbox" task; does not recognize that processing requires reading and handling message contents
- Solution: Inbox processing requires depth. After listing inbox, read at least the first message, identify its action requirement, and execute that action

## Ambiguous Inbox Task Without Explicit Action Mapping
- Condition: Task requests inbox processing (e.g., "PROCESS THE INBOX", "Process the incoming queue") without specifying (a) message scope or (b) expected action type per message
- Root cause: Task definition provides no explicit success criteria; action mapping is implicit or undefined, leaving agent unable to determine whether to process one message or all, and what operation to perform
- Solution: Task must explicitly specify message selection criteria and action type. Example: "Read all unread inbox messages and respond to each question with a brief answer." If task is vague, request clarification before processing begins

## File Read Timeout — Fallback Not Attempted
- Condition: Agent attempts to read a file that times out; file contains queryable/searchable data
- Root cause: Agent assumes read is the only viable operation for file content extraction; does not implement fallback to search when read timeout occurs
- Solution: When read operation times out, immediately switch to search operation on the same file to extract the required data; avoid retry attempts on the same read operation

---
