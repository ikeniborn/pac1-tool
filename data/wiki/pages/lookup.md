## Proven Step Sequences

### Lookup: Customer Contact by Industry Criteria
1. `list /accounts` to enumerate account files
2. Iterate `read /accounts/acct_{N}.json` to locate target by `industry` (e.g., "finance" for banking) and/or name patterns (e.g., "Bank")
3. Note the `account_id` (e.g., "acct_004")
4. `read /contacts/cont_{N}.json` where `{N}` matches the account suffix (e.g., acct_004 → cont_004)
5. Extract the specific field requested (e.g., `email`) and return immediately

### Lookup: Account Name by Keyword
1. `search` for entity keyword (e.g., "Helios") to locate the account file (e.g., `/accounts/acct_008.json`)
2. `read` the identified account file
3. Extract the `name` field (legal entity name) and return immediately per minimal output rule

### Lookup: Multiple Accounts by Manager
1. `search` within `/accounts` for the manager name (surname or full name) to identify candidate files
2. `read` each candidate to verify the `account_manager` field matches exactly
3. Collect the `name` values, sort alphabetically, and format as specified (e.g., one per line)

## Key Risks and Pitfalls

- **Stall Detection**: Taking 6+ steps with only `list`/`read` operations triggers stall warnings. Batch target identification or minimize exploratory reads when possible.
- **File Segregation**: Contact details reside in `/contacts/`, not embedded in account files. Always cross-reference using the `account_id` → `cont_{id}.json` mapping.
- **Terminology Mismatch**: Search for `"industry": "finance"` when task specifies "banking", not literal "banking" strings.
- **Enumeration Stall**: Full directory `list` operations followed by sequential `read` cycles (e.g., listing `/accounts` then reading each file) rapidly trigger stalls. Prefer `search` to identify specific targets without listing entire directories.
- **Manager File Limitation**: Manager files in `/contacts/mgr_{N}.json` only map to a single `account_id`, but managers may oversee multiple accounts. For multi-account manager queries, search account files directly by the `account_manager` field.

## Task-Type Specific Insights (Lookup)

- **Dutch Customer Identification**: Look for Dutch name patterns (e.g., "van Dam", "van", "de") in `full_name` fields within contact records.
- **Account-Contact Mapping**: Contact files follow the pattern `cont_{number}.json` corresponding to `acct_{number}.json` (e.g., acct_004 links to cont_004 via `account_id` field).
- **Minimal Output Compliance**: When task specifies "Return only X", extract exactly that field and terminate; do not format additional context or metadata.
- **Name Tokenization**: Search matches name components regardless of order (e.g., "Hoffmann Mia" matches "Mia Hoffmann"), but field values (e.g., `account_manager`) require exact string verification.
- **Bulk Result Sorting**: For queries requiring sorted output (e.g., "alphabetically"), collect all values into a list, apply lexicographical sorting, then format with specified delimiters.
- **Direct Account Search**: Account files can be located via `search` using entity keywords (e.g., "Helios") rather than sequential `list`/`read` enumeration.