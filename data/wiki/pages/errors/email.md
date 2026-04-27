## Contact Not Found — Inline Recipient

- Condition: Task specifies a recipient email address (e.g. `<email>`) not present in `/contacts`.
- Root cause: Agent searches `/contacts` for the address and finds no matching record; the write gate requires a verified vault contact before dispatching to `/outbox`.
- Solution: After 1–2 failed contact searches, proceed to write the outbox entry using the literal email address supplied in the task. Do not block on vault verification when the address is fully specified in the task.

---

## Contact Not Found — Organization Name Only

- Condition: Task names a recipient by organization (e.g. "Aperture AI Labs") with no email address; neither `/contacts` nor `/accounts` contains a matching record.
- Root cause: Organization appears only in notes (e.g. `/01_notes/aperture-ai-labs.md`) with no associated contact record holding an email field.
- Solution: After exhausting contact and account searches, surface a clarification request for the recipient email rather than stalling. Do not continue looping over the same searches.

---

## Outbox Write Stall — Repeated Identical Req_Write Calls

- Condition: Agent issues `Req_Write` to `/outbox/<file> with the same arguments 3+ times without progress.
- Root cause: Agent re-executes the write call on each loop iteration despite receiving no new information, indicating it is not detecting that the write already failed or was blocked.
- Solution: Track write attempts per argument set; after 2 consecutive identical failures, treat the operation as definitively blocked and either escalate or abort with an explanatory output.

---

## Exploration Stall — No File-System Action Taken

- Condition: Agent performs 6+ consecutive read/search/list operations without writing, deleting, moving, or creating any file.
- Root cause: Agent is looping over lookups waiting for a condition (e.g. contact found) that will never be satisfied, without a step-count exit condition.
- Solution: Impose a hard ceiling of 5 exploratory steps before taking a write action or halting. If the necessary precondition is unmet after that ceiling, write with available data or emit a structured failure; never continue pure exploration past the limit.

---

## Contacts README Matched Instead of Contact Record

- Condition: Search in `/contacts` returns `README.MD` rather than a contact record when looking up a name or email.
- Root cause: The search term matches incidental text in the README (e.g. a column header or example on line 17) rather than any real contact entry.
- Solution: Filter search results to exclude `README.MD` and other non-record files (`.md`, index files) when resolving contact lookups. Only `.json` records in `/contacts` should be treated as authoritative.

---

## Compound Stall — Interleaved Write and Exploration Loops

- Condition: Agent alternates between repeated identical `Req_Write` failures and extended no-action exploration runs (10+ total steps) within the same task, escalating stall counters on both dimensions simultaneously.
- Root cause: Two independent stall loops reinforce each other: each blocked write attempt resets the agent to exploration mode, which then re-triggers the write attempt without any new information, creating a cycle that neither branch can exit.
- Solution: Treat a combined stall budget across both dimensions (write retries + exploration steps) as a single shared counter capped at 10. On breach, emit a structured failure record to `/outbox` with available data and halt. Do not allow stall-type switching to reset either counter.

---

## Seq.json Updated Without Email File

- Condition: Agent successfully writes to `/outbox/<file> (incrementing the ID counter) without also writing the corresponding email content to `/outbox/<file>
- Root cause: Agent treats seq.json modification as a preliminary step or progress marker even when email dispatch is incomplete or fails—possibly to reserve an ID before recipient resolution succeeds.
- Solution: Defer all seq.json updates until immediately after `/outbox/<file> is confirmed successfully written. If recipient resolution fails or email composition is incomplete, do not modify seq.json.

---
