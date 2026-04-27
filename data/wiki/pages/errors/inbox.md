## Inbox Task Produced No Output

- Condition: Agent processes an inbox review task but writes no outbox files and produces no actionable result.
- Root cause: Agent misidentifies a task as requiring clarification when it should act, or fails to parse inbox message content into discrete action items. Includes trivially answerable questions (e.g. "what is 2x2?") that are treated as ambiguous.
- Solution: Ensure inbox processing always maps each message to an explicit action or a documented denial; never exit with `OUTCOME_NONE_CLARIFICATION` without writing a structured response explaining what clarification is needed.

## Channel Trust Verification Skipped or Deferred

- Condition: Agent executes an action command before verifying the originating channel and handle are authorized, OR a privileged action (data export, bulk operation, state-changing command) is executed from an untrusted channel.
- Root cause: Trust-level verification is deferred or omitted; action logic runs before authorization logic. Channel and handle metadata is parsed after or not checked against the trusted list before proceeding.
- Solution: Channel and handle trust verification must be the first step after reading any inbox message, before parsing message intent. Maintain a canonical list of trusted channels and handles. All privileged operations must be gated on this verification. Deny and log any request from untrusted sources; write the denial to outbox for audit trail.

## Contact Lookup Fails Due to Partial Search Terms

- Condition: Agent searches for a contact by name or attribute using an empty or overly broad search string, returning unrelated records.
- Root cause: Search invoked with blank or insufficiently scoped query, causing noise matches across unrelated files.
- Solution: Always construct search queries from the specific fields available in the message (e.g., full name, account ID, email). Validate that at least one result field matches the expected contact before proceeding.

## Outbox File Written Without Canonical Sequence Registration

- Condition: Agent writes a response file (e.g., `84949.json`) directly to `/outbox/<file> but the sequence index (`seq.json`) is written independently and may diverge.
- Root cause: No atomic coupling between individual outbox message files and the sequence manifest; either write can succeed while the other fails.
- Solution: Always write the sequence manifest (`seq.json`) and all individual outbox files as a logical unit. Verify both writes succeed before marking the task complete; if either fails, do not consider the response sent.

## Response Written Outside Outbox Directory

- Condition: Agent processes an inbox message and writes its output to a non-canonical path (e.g., `/result.txt`) instead of `/outbox/<file> yet may still exit as though the task is complete.
- Root cause: Agent lacks or ignores the outbox path convention; no enforcement prevents output from being routed to arbitrary filesystem locations.
- Solution: All inbox-task responses must be written to `/outbox/<file> and registered in `seq.json`. A write to any other path does not constitute a valid outbox response; the task must be treated as incomplete until the canonical write succeeds.

## Agent Stall from Excessive Pre-Write Reads

- Condition: Agent accumulates six or more consecutive read/search steps without performing any write, delete, move, or create operation during an inbox task.
- Root cause: Agent over-researches before acting; there is no internal limit on consecutive non-mutating steps, so lookup loops can continue indefinitely.
- Solution: Once a contact is resolved and the required resource (e.g., invoice, record) is located, proceed immediately to write the outbox response. Treat five consecutive non-mutating steps as a self-imposed stall threshold: either write or explicitly document the blocking reason and halt. The stall warning system (triggered at step 6) allows recovery; resume execution with a write/delete operation.

---
