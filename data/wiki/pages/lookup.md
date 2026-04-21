## Proven Step Sequences

### Lookup: Contact Email by Reversed Name (Suffix Matching)
1. If full name search returns no matches, try searching with individual name components
2. When `mgr_{N}.json` is found, `read` the manager file
3. Extract the `email` field and return immediately per minimal output rule
4. **Note**: Task names may present first/last name in reversed order (e.g., "Pfeiffer Antonia" maps to "Antonia Pfeiffer" in file)

### Lookup: Account Manager Email via Compound Software Profile
1. `list` `/accounts` or `search` with industry keyword (e.g., "software")
2. `read` candidate account files to verify against all task descriptors (e.g., "AI data-flow review")
3. If descriptor references an add-on or feature, `read` `/01_notes/{account-slug}.md` for context
4. Extract `account_manager` name from matched account file
5. `search` for manager name in `/contacts` to locate `mgr_{N}.json`
6. `read` the manager file
7. Extract the `email` field and return immediately per minimal output rule

### Lookup: Primary Contact by Regional Industry Descriptor
1. `list` `/accounts` or `search` with industry keyword (e.g., "retail")
2. `read` candidate account files to verify regional qualifier (e.g., "DACH")
3. Verify secondary descriptor (e.g., "weak internal sponsorship") via `/01_notes/` if needed
4. Extract `account_id` from matched account file
5. `read` corresponding contact file `cont_{N}.json`
6. Extract the `email` field and return immediately per minimal output rule

### Lookup: Legal Entity Name via Notes Bridge
1. `read` `/01_notes/{account-slug}.md` for account context
2. `search` within `/accounts` using account name keyword
3. `read` the account file to extract the `name` field
4. Return immediately per minimal output rule

### Lookup: Multiple Accounts by Manager Name (Manager File Limitation)
1. `search` for manager name in `/contacts` to locate `mgr_{N}.json`
2. `read` the manager file (note: only links to single account_id)
3. `search` for manager name in `/accounts` to identify all candidate files
4. `read` each candidate account file to verify `account_manager` field matches exactly
5. Collect `name` values, sort alphabetically, and format with specified delimiter

### Lookup: Account Manager Email by Regional Industry Compound
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts to match compound descriptors (e.g., "Austrian grid-modernization energy")
3. Identify matching account via industry field (e.g., "energy") and implied regional context
4. Extract `account_manager` name from matched account file
5. `search` for manager name in `/contacts` to locate manager file
6. `read` manager file and extract `email` field

### Lookup: Multi-Descriptor Account Resolution (Regional + Industry + Characteristic)
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts matching multiple descriptors (e.g., "Benelux" + "compliance-heavy" + "bank")
3. Cross-reference industry field ("finance" for banks)
4. Extract `account_id` from matched account file
5. `read` corresponding contact file `cont_{N}.json`
6. Extract `email` field and return immediately

### Lookup: Contact Email by Exact Name Match
1. `search` in `/contacts` using the name provided in task
2. `read` the matching contact file (e.g., `cont_{N}.json`)
3. Extract the `email` field directly from contact file
4. Return immediately per minimal output rule
5. **Note**: Direct name search may match regardless of name order presentation; verify match and retry with surname-only if needed

### Lookup: Account Manager Email by Account Name Search
1. `search` in `/accounts` using account name keyword (e.g., "Silverline")
2. `read` the matched account file to extract `account_manager` name
3. `search` for manager name in `/contacts` to locate manager file
4. `read` the manager file and extract `email` field
5. Return immediately per minimal output rule

### Lookup: Legal Entity Name by Compound Descriptor
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts matching regional keyword (e.g., "Benelux") and descriptor (e.g., "services")
3. Verify descriptor via account field matching or notes if needed
4. Extract `name` field from matched account file
5. Return immediately per minimal output rule

### Lookup: Primary Contact via Account Name Search
1. `search` in `/accounts` using the account name keyword (e.g., "Silverline")
2. `read` the matched account file to extract `account_id`
3. `read` the corresponding contact file (e.g., `cont_{N}.json`)
4. Extract `email` field and return immediately

### Lookup: Legal Entity Name by Country + Industry + Account Type
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts matching country qualifier (e.g., "German") and industry (e.g., "manufacturing")
3. Verify account type descriptor (e.g., "Acme") matches via `name` field
4. Return `name` field immediately per minimal output rule

### Lookup: Primary Contact via Compound Descriptor (Berlin Digital-Health)
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts to verify compound descriptors (e.g., "Berlin" + "digital-health" + "buyer focused on triage backlog")
3. Match account via industry field (e.g., "healthcare") and notes context if needed
4. Extract `account_id` from matched account file
5. `read` corresponding contact file `cont_{N}.json`
6. Extract `email` field and return immediately

### Lookup: Manager Multi-Account Enumeration (Manager File Mismatch)
1. `search` for manager name in `/contacts` to locate manager file
2. `read` manager file to verify exact `full_name` match (note: manager file may link to different account than expected)
3. `search` in `/accounts` using `account_manager` field for comprehensive match
4. `read` each candidate account file to verify `account_manager` field matches exactly
5. Collect `name` values from verified matches, sort alphabetically

### Lookup: Captured Article by Date Offset
1. `list` `/01_capture/influential` (or relevant capture directory)
2. Identify file names containing ISO dates (e.g., `2026-02-10__article-name.md`)
3. Calculate the target date by subtracting N days from current/task date
4. Match file date prefix to calculated target date
5. Return the matched file name immediately per minimal output rule

### Lookup: Software Account with Feature Descriptor (Industry Enumeration)
1. `list` `/accounts` to enumerate all account files
2. `read` candidate accounts to find industry field matching primary descriptor (e.g., "software")
3. If descriptor references a feature (e.g., "AI data-flow review"), `read` `/01_notes/{account-slug}.md` to verify context
4. Extract `name` field from matched account file
5. Return immediately per minimal output rule

### Lookup: Contact Email by Single Name Component
1. `search` in `/contacts` using full name → no matches
2. Retry `search` with first name or surname component only (e.g., "Franziska" instead of "Busch Franziska")
3. `read` the matching contact file to extract `email`
4. Return immediately per minimal output rule

## Key Risks and Pitfalls

- **Reversed Name Presentation**: Task names may present last name first (e.g., "Pfeiffer Antonia", "Barth Florian", "Albrecht Laura") while actual contact records use first name first (e.g., "Antonia Pfeiffer", "Florian Barth", "Laura Albrecht"). Always retry with individual name components.
- **Telegram File Read Timeout**: Files in `/docs/channels/Telegram.txt` may repeatedly timeout on `read`. Even `search` within the parent directory may fail. Search with empty pattern returns "invalid search pattern" error. This operation is fundamentally problematic for this file.
- **Multi-Stall Execution**: A single task can trigger multiple stall warnings without failing, but performance degrades with each stall. Stall warnings appear at 6 steps without write operations. Tasks can continue past warnings but should minimize redundant operations.
- **Notes File Dependency**: Compound descriptors (e.g., "AI data-flow review") may not appear in account file fields directly. Reading `/01_notes/{slug}.md` provides the bridge to understand task context.
- **Account Enumeration Priority**: When searching by manager name, manager files only link to one account. Must enumerate account files directly via `search` on `account_manager` field to find all managed accounts.
- **Regional Keyword Extraction**: Task phrasing may omit explicit regional keywords (e.g., "Austrian" without "Austria"). Use implied regional context from account characteristics to narrow candidates.
- **Name Prefix Variations**: Names with prefixes (e.g., "van der Werf", "van der Berg") may have different ordering between task input and file records. Search by surname component if full name match fails.
- **Search Pattern Requirements**: Empty search patterns (`search: `) return matches across all files, but `search: ?` returns "INVALID_ARGUMENT". Always provide a valid search term.
- **Connection Reset Errors**: Account files (e.g., `/accounts/acct_008.json`) can return "ERROR EXCEPTION" or "Connection reset by peer" on read. Retry the operation to recover.
- **Name Collision in Search Results**: Searching by manager name in `/contacts` may return partial matches (e.g., "Erik Lange" returns "Theresa Lange" as candidate). Always verify exact `full_name` match in manager file.
- **Account File Read Instability**: Some account files may fail multiple times before succeeding. Persist with retries when encountering timeout or connection errors.
- **Manager File Account ID Mismatch**: Manager files (`mgr_{N}.json`) contain `account_id` that may not correspond to the account the manager actually manages in other files. The `account_manager` field in account files is authoritative for multi-account queries.

## Task-Type Specific Insights (Lookup)

- **Regional Industry Descriptors**: "DACH" maps to German-speaking region (Germany/Austria/Switzerland). "Benelux" maps to Belgium/Netherlands/Luxembourg. "Dutch" explicitly maps to Netherlands. Combine regional + industry keywords (e.g., "retail") to narrow account candidates.
- **Multi-Descriptor Verification**: Tasks combining multiple qualifiers (e.g., "Austrian grid-modernization energy customer" or "Benelux compliance-heavy bank") require reading multiple account files to verify all descriptors match before proceeding.
- **Name Component Robustness**: Search with surname-only often succeeds where full name fails, even when task presents names in reversed order.
- **Manager File → Single Account Mapping**: Manager files (`mgr_{N}.json`) contain `account_id` linking to exactly one account. For multi-account manager queries, use `account_manager` field search in `/accounts/`, not manager file references.
- **Telegram Read Instability**: The Telegram channel file may fail on `read` operations (timeout/exception) and `search` operations (invalid argument). Accept this as a hard limitation.
- **Direct Account Enumeration for Compound Lookups**: When task combines multiple descriptors (regional + industry + account type), listing `/accounts` and reading candidates directly is more reliable than search alone.
- **Direct Account Name Search**: When account name is explicitly provided (e.g., "Silverline"), searching `/accounts` directly by name keyword often finds the account faster than enumerating all files.
- **Name Prefix Handling**: Search by surname component (e.g., "Werf" from "van der Werf") may succeed where full name with prefix fails.
- **Stall Warning Continuation**: Stall warnings at 6 steps without writes are advisory only. Tasks can continue past warnings but should minimize redundant operations to maintain performance.
- **Direct Contact Lookup**: For simple contact email lookups by full name, `search` in `/contacts` with the provided name often returns direct matches without needing account enumeration.
- **Connection Error Recovery**: When account file read returns connection reset errors, retrying the same read operation typically succeeds on subsequent attempts.
- **Capture Directory Date Matching**: Capture directories store files with ISO date prefixes (e.g., `2026-02-10__filename.md`). Calculate target date from task date offset and match by date prefix in filename.
- **Single Name Component Search**: When full name search returns no matches, try first name or surname alone. This works even with reversed name presentation.
- **Software Industry + Feature Descriptor**: Accounts with "software" industry may have specific features (e.g., "AI data-flow review") documented in `/01_notes/`. Use notes file as bridge when account fields don't directly contain descriptor.