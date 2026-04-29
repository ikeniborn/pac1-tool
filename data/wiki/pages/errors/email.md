## Email Write Blocked by Force-Read-Contact Gate on Literal Address Tasks

- **Condition**: Agent attempts to write an email to a recipient whose address is provided as a literal string in the task description (e.g., `"<email>"`), but writes are blocked by a force-read-contact gate.
- **Root cause**: The agent cannot distinguish between tasks requiring contact lookup vs. tasks where contact info is already provided. It repeatedly searches `/contacts/<file> for JSON files, finds none (only README.MD), and stalls — never reaching the write operation. The gate's auto-relax condition for FIX-331 compliance is not being honored.
- **Solution**: When the email address is a literal string in the task (per FIX-331), skip contact lookup entirely. Use the literal address directly and write the email file to `/outbox/<file> No contact file read required.

---

## Stall Escalation from Repeated Blocked Write Attempts

- **Condition**: Agent calls `Req_Write` with identical arguments 3+ times in a row without progress, and continues exploring directories for 12+ steps.
- **Root cause**: Agent does not recognize the blocked-write state as a signal to change strategy. It re-reads seq.json, re-lists directories, and re-attempts the same write, triggering repeated stall warnings until STALL ESCALATION.
- **Solution**: After the second blocked write with identical arguments, stop re-reading files and re-attempting. Evaluate whether the gate condition has an override (e.g., FIX-331 literal-address exception) or whether the task metadata requires clarification.
