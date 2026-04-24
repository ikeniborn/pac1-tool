## Empty Search Query Returns No Matches
- Condition: Agent issues a search operation with an empty or missing query string while trying to locate email templates, recipients, or prior correspondence.
- Root cause: Search backend requires a non-empty query term; an empty query cannot match anything and returns zero results, leaving the agent without the context it needed.
- Solution: Before invoking search, construct a concrete query from available task fields (recipient address, subject keywords, or sender). If no query term can be derived, skip the search and proceed with the information already in hand rather than issuing an empty call.

## Email Task Abandoned After Read-Only Probing
- Condition: Task requests composing and sending a brief email, but the agent only reads `/outbox/<file> (or similar counter) and performs no send/write operation, terminating with a clarification outcome.
- Root cause: Agent treats fully-specified email parameters (recipient, subject, body all provided) as ambiguous and stops to ask for clarification instead of executing the send.
- Solution: When recipient, subject, and body are all explicitly given in the task, proceed directly to compose and dispatch the email. Reserve clarification requests for cases where a required field is genuinely missing or contradictory.

## Outbox Sequence Read Without Write
- Condition: Agent reads `/outbox/<file> to obtain the next message id but never uses the id to create an outbox entry.
- Root cause: The read is performed as preparation for a send that is subsequently skipped, wasting the sequence lookup and leaving the task incomplete.
- Solution: Only read the outbox sequence file as part of a committed send flow. If the agent decides not to send, do not read the counter; if it reads the counter, follow through by writing the new outbox message with that id.

## Task Completion Reported Without Required Arguments
- Condition: Agent invokes the task-completion reporting operation with missing or malformed arguments, producing an INVALID_ARGUMENT error.
- Root cause: Completion call is issued as a fallback after the main task was abandoned, without populating the required outcome fields (e.g., task id, outcome type, artifact references).
- Solution: Only call the completion operation after the task's primary action has succeeded, and populate all required fields (task id, outcome, and any referenced artifacts) before invoking it.
