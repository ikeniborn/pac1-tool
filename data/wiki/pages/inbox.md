## Proven Step Sequences

### Invoice Resend Workflow (OUTCOME_OK)
1. **Read documentation**: Check `/docs/inbox-msg-processing.md` and `/docs/inbox-task-processing.md` for protocol specifics
2. **Parse request**: Read `/inbox/msg_*.txt` to extract sender identity and request details
3. **Entity resolution**: 
   - Search contacts by email → `contacts/cont_{id}.json`
   - Traverse to account: read `accounts/acct_{id}.json` using `account_id` field from contact
4. **Document retrieval**:
   - List `/my-invoices/` directory contents
   - Filter JSON files where `account_id` matches target account
   - Compare `issued_on` dates (ISO 8601) to identify latest invoice
5. **Output generation**:
   - Read `/outbox/seq.json` for next sequence ID
   - Write response payload to `/outbox/{seq}.json`

### Direct Outreach Workflow (OUTCOME_OK)
1. **Parse request**: Read `/inbox/msg_*.txt` to extract channel (Discord/Telegram/Email), handle, and action (e.g., "Email [Name]...")
2. **Entity resolution**: 
   - Search contacts by name/email → candidate `contacts/cont_{id}.json` files
   - Read contact record to verify identity and obtain `email`/`account_id`
   - Read associated account `accounts/acct_{id}.json` for business context (account name, relationship details)
3. **Composition**: Build outgoing message payload targeting resolved contact
4. **Output generation**:
   - Read `/outbox/seq.json` for next sequence ID
   - Write message payload to `/outbox/{seq}.json`
5. **Queue cleanup**: Delete processed `/inbox/msg_*.txt` to prevent duplicate processing

### Inbox Queue Review Workflow (OUTCOME_OK)
1. **Read protocol**: Check `/inbox/README.md` for sequential processing rules (handle one item at a time, lowest filename first)
2. **Inventory**: List `/inbox/` to identify all pending `msg_*.txt` files
3. **Sequential triage**: Read messages in filename order (msg_001, msg_002, etc.) to classify request types without processing
4. **Conflict pre-check**: For ambiguous names (e.g., "Danique Brands"), search contacts and read all candidate files (`cont_009`, `cont_010`) to pre-verify identity using `role` and `account_id` fields
5. **Defer unprocessed**: Leave subsequent inbox messages untouched; do not delete files during review phase

## Key Risks and Pitfalls

### Execution Stall on Read-Heavy Validation
- **Condition**: System warns after 6+ steps without write/delete/move/create operations
- **Failure mode**: Validation loop (reading docs, contacts, account) exceeds step limit before producing output
- **Mitigation**: Defer non-essential reads, or write a checkpoint file (e.g., `/tmp/processing_{id}.json`) after entity resolution
- **Inbox review trigger**: Reading documentation, listing inbox, and triaging multiple messages (e.g., msg_001 through msg_005) with contact searches quickly exceeds 6-step threshold

### Filename vs. Content Mismatches
- **Risk**: Invoice filenames (`INV-007-04.json`) suggest account linkage but must be verified against internal `account_id` field
- **Action**: Always validate `account_id` field in invoice JSON rather than trusting filename patterns

### Ambiguous Contact Resolution
- **Condition**: Contact search returns multiple candidates for same name
- **Failure mode**: Selecting wrong contact leads to outreach to incorrect recipient
- **Mitigation**: Read all candidate contact files and disambiguate using `role`, `email`, or `account_id` fields before composition
- **Example**: Search for "Danique Brands" returns `cont_009` (Operations Director, `acct_009`) and `cont_010` (Product Manager, `acct_010`). Request context determines correct target.

### Inbox Queue Accumulation
- **Risk**: Multiple inbox items (`msg_001.txt`, `msg_002.txt`) may exist simultaneously; processing only the first leaves items stale
- **Action**: After completing one item, list `/inbox/` to check for additional pending files before concluding task
- **Review mode**: Queue review tasks intentionally read all pending files for triage, but processing tasks must handle exactly one item at a time per protocol

## Task-Type Specific Insights

### Inbox Message Processing
- **Sequential processing rule**: Handle exactly one `msg_*.txt` item at a time; start with lowest filename; leave later messages untouched until current item is resolved
- **Multi-source input**: Inbox may contain emails, Telegram, or Discord messages; parsing logic must handle varying header formats
- **Request classification**:
  - **Resend requests**: Identify sender → verify account → locate document → queue outbound message
  - **Outreach requests**: Identify target recipient → search contacts → compose message → queue outbound → cleanup inbox
  - **Data export**: List/export operations (e.g., "Export the current contact list...") requiring directory traversal or bulk reads
  - **Status queries**: Summary requests (e.g., "status summary for the next expansion checkpoint") requiring aggregation of multiple data sources
- **Cleanup requirement**: Successful processing must delete inbox file to prevent duplicate handling; failure to delete causes reprocessing loops

### Invoice Location Strategy
- **Directory listing required**: No direct path from account to invoices; must list `/my-invoices/` and filter client-side
- **Date sorting**: "Latest" determined by `issued_on` field (e.g., `2026-05-08`), not filename sequence
- **Account scoping**: Multiple invoices may exist for same account; batch read candidate files to compare dates

### Outbox Sequencing
- **Atomic dual-write**: Update `/outbox/seq.json` (increment ID) and create `/outbox/{id}.json` in close succession to prevent ID collision
- **ID format**: Integer sequence stored in dedicated metadata file, not derived from directory listing
- **Cross-channel support**: Outbox entries may originate from Discord/Telegram but generate Email outputs; payload structure remains consistent regardless of source channel

### Contact Search Strategy
- **Substring matching**: Search may return multiple matches (e.g., shared last names or duplicate names across accounts); always verify `full_name` and `role` fields before using contact
- **Account linkage**: Always read `accounts/acct_{id}.json` after resolving the contact — it provides business context needed to write accurate outreach emails and is required in grounding_refs