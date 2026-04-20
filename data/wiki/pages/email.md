## Proven Step Sequences

### Direct Email Composition (No Account Context)
1. **Query sequence**: Read `/outbox/seq.json` to obtain current message ID
2. **Compose payload**: Write email content including recipient, subject, and body to `/outbox/{id}.json`
3. **Commit sequence**: Update `/outbox/seq.json` to increment the consumed ID

### Account-Based Email Composition
1. **Locate account**: Identify target account file (e.g., `/accounts/acct_004.json`) via listing or direct reference
2. **Verify details**: Read account file to confirm organization name and status
3. **Resolve recipient**: Read corresponding contact file `/contacts/cont_{NNN}.json` where NNN matches account ID suffix (e.g., `acct_004` → `cont_004`)
4. **Gather context**: Read `/01_notes/{kebab-case-org-name}.md` for conversation history and account-specific details
5. **Execute storage**: Follow Direct Email Composition sequence using gathered metadata

### Account Discovery by Content
1. **List inventory**: List `/accounts` to obtain candidate filenames when target ID is unknown
2. **Iterate and match**: Read account files sequentially to match content criteria (industry, geography, organization name substring) until target located
3. **Proceed to composition**: Follow Account-Based Email Composition steps 3-5

## Key Risks and Pitfalls

- **Sequence read timing**: Defer reading `/outbox/seq.json` until immediately before writing the email file to minimize staleness window; perform all context gathering (account, contact, notes) prior to acquiring the ID
- **Incomplete atomic sequence**: Writing the email file without updating `seq.json` results in ID collision and data overwrite on subsequent writes; both writes must occur in the same logical operation
- **Path confusion**: Typo between `/outbox/` and `/outbound/` causes write failures or misplaced files
- **Contact/account ID mismatch**: Contact file IDs correspond to account IDs by exact numeric suffix (e.g., `acct_009` → `cont_009`, `acct_004` → `cont_004`); verify alignment before reading
- **Missing context files**: Notes in `/01_notes/` may not exist for all accounts; verify kebab-case path construction (e.g., "Blue Harbor Bank" → `blue-harbor-bank.md`) before attempting read
- **Enumeration stall risk**: Sequential reads of multiple `/accounts/*.json` files during discovery consume the 6-step research budget rapidly; avoid interleaving non-essential reads (e.g., early notes listing) during account scans

## Task-Type Specific Insights

- **ID management**: Sequential numeric IDs are centrally tracked in `/outbox/seq.json` as `{"id": <number>}`; use exact value without padding or prefixes
- **Storage isolation**: Each email is an isolated JSON file named by numeric ID in `/outbox/`; no directory nesting per message
- **Atomicity requirement**: Maintain strict ordering: read current ID → write email file → update sequence counter to ensure crash consistency and prevent duplicate filenames
- **Contact correlation**: Primary contacts follow strict `/contacts/cont_{NNN}.json` pattern where NNN matches the account ID suffix exactly
- **Notes naming convention**: Organization context files use lowercase kebab-case in `/01_notes/` derived from the organization name (e.g., "Aperture AI Labs" → `aperture-ai-labs.md`)
- **Context dependency chain**: Account-based emails require three-tier resolution: account file → contact file → notes file; missing any tier requires graceful degradation (compose without missing context rather than fail)
- **Direct vs. contextual composition**: Tasks specifying explicit email addresses (e.g., `sam@example.com`) bypass the account discovery chain entirely and use only the Direct Email Composition sequence