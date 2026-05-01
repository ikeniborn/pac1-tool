<!-- wiki:meta
category: lookup
quality: developing
fragment_count: 14
fragment_ids: [t16_20260430T133739Z, t34_20260430T140103Z, t38_20260430T140152Z, t39_20260430T140342Z, t43_20260430T140718Z, t16_20260430T163802Z, t34_20260430T165555Z, t38_20260430T165841Z, t39_20260430T165835Z, t42_20260430T165844Z, t16_20260430T210642Z, t34_20260430T211342Z, t38_20260430T211531Z, t39_20260430T211537Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Query by Partial Name Match**

When the exact name is not known, use two progressive searches—the first with an empty query (triggering system suggestions) and the second with the known name component. Read the resulting file to extract the needed field.

- search:  → (no matches)
- search:  → contacts/<contact>.json:4
- read: /contacts/<file> → { … "email": "<email>" … }

**Query by Field Lookup with Attribute Filter**

To find a specific account record, search on the name and read the matching file. Use the primary_contact_id or account_manager field as a cross-reference, then look up the contact record for the final answer.

- search:  → accounts/<account>.json:3, accounts/<account>.json:4, accounts/README.MD:14, accounts/README.MD:15
- read: /accounts/<file> → { … "legal_name": "Nordlicht Health GmbH" … }

**Query Using List + Sequential Filter**

When searching fails, enumerate the directory with list and read each account file sequentially until finding one that matches the multi-attribute target (country, industry, compliance flag). Use the primary_contact_id to fetch the contact record.

- list: /accounts → <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, <account>.json, README.MD
- read: /accounts/<file> → Germany, not Dutch
- read: /accounts/<file> → Germany, not Dutch
- read: /accounts/<file> → Benelux, logistics, not banking
- read: /accounts/<file> → Netherlands, finance, "security_review_open" present → target found
- read: /contacts/<file> → { … "email": "<email>" … }

**Query for Related Entity via Cross-Reference**

Find an account record, extract the cross-reference field (account_manager), then search the contacts directory for the matching manager record to retrieve the email.

- search:  → accounts/<account>.json:14, accounts/<account>.json:14
- read: /accounts/<file> → { … "account_manager": "Hannah Hartmann" … }
- search:  → contacts/<manager>.json:4
- read: /contacts/<file> → { … "email": "<email>" … }

**Query for Recent Capture by Relative Date**

When a date-based lookup fails via search, list the capture subdirectory to view filenames that encode dates. Manually compare timestamps (filename or metadata) against the target interval. In this case, relative date query (37 days ago from <date> = approximately <date>) did not match any filename and clarification was needed.

- list: /01_capture/influential → <date>…, <date>…, <date>…, <date>…, <date>…
- no filename matched the target date range
- outcome: OUTCOME_NONE_CLARIFICATION (user asked which article, no exact match for 37 days prior to <date> = <date>)

**Query for Primary Contact via Account Lookup**

When asked for the primary contact's email for a specific account, search for the account by name, read the account record to extract the primary_contact_id, then read the corresponding contact file to retrieve the email.

- search:  → accounts/<account>.json:3, accounts/<account>.json:4
- read: /accounts/<file> → { … "primary_contact_id": "<contact>" … }
- read: /contacts/<file> → { … "email": "<email>" … }

**Query by Combined Attribute Search**

When searching with a combined query (e.g., country + industry + account type), the search may return multiple account files. Read each matching file to verify attributes until the target account is confirmed.

- search:  → accounts/<account>.json:3, accounts/<account>.json:4, accounts/<account>.json:14, accounts/<account>.json:3, accounts/<account>.json:4, accounts/<account>.json:14
- read: /accounts/<file> → { … "legal_name": "Acme Robotics GmbH", "industry": "manufacturing", "country": "Germany" … } → target found

**Query with Name Order Variation**

When searching by a person's name, the stored full_name may have name parts in reversed order. Perform the partial search anyway—the system may return the file even if the query string is not an exact subsequence of the stored name.

- search:  → (no matches)
- search:  → contacts/<contact>.json:4
- read: /contacts/<file> → { … "full_name": "Pascal Heinrich", "email": "<email>" … }

**Query by Partial Name Then Cross-Reference for Primary Contact**

When the primary contact for a specific account is needed, search for the account by descriptive query (e.g., region + industry), read multiple candidate files to identify the matching account by country/industry, extract the primary_contact_id, then read the contact file.

- search:  → accounts/<account>.json:14, accounts/<account>.json:14, accounts/README.MD:45
- read: /accounts/<file> → { … "industry": "retail", "country": "Germany" … } → not Dutch
- read: /accounts/<file> → { … "industry": "logistics", "country": "Netherlands", "primary_contact_id": "<contact>" … } → target found
- read: /contacts/<file> → { … "email": "<email>" … }

**Query for Account Manager via Account Then Manager Record**

When the account manager's email is needed, search for the account by name, read the account to extract the account_manager field, then search for the manager record and read the email.

- search:  → accounts/<account>.json:3, accounts/<account>.json:4
- read: /accounts/<file> → { … "account_manager": "Oliver König" … }
- search:  → contacts/<manager>.json:4
- read: /contacts/<file> → { … "email": "<email>" … }

## Key pitfalls
**False Matches:**
- Partial string matches can lead to reading wrong files. Searching for "Acme" returned results from both `accounts/<account>.json` (German Acme Robotics) and `accounts/<account>.json` (Dutch Acme Logistics), risking confusion between similarly-named accounts if subsequent reads are not precisely targeted.
- Vague queries yield wide result sets. Searching for "Acme" returned 6 matches across two accounts (`<account>`, `<account>`), making it difficult to determine which account is the intended German manufacturing entity without reading both files to check industry and country fields.
- Name ordering variations can cause false empty results before refinement. In task t16, the first search with `query="Heinrich Pascal"` returned no matches; only after searching with `query="Pascal Heinrich"` did the agent find the contact. Agents should attempt alternate name orderings (e.g., "Pascal Heinrich") or partial first/last name searches before concluding contacts are absent.

**Wrong Filters:**
- Failure to narrow search scope can cause excessive sequential reads. In task t38, the agent searched for "Dutch port-operations shipping account" which returned no direct matches, then searched broadly and received results spanning both accounts (`<account>`, `<account>`) plus documentation. The agent then read `<account>` (German retail) before discovering it was the wrong account and reading `<account>` (Dutch logistics) — instead of filtering directly for `country=Netherlands`, `industry=logistics`, and `notes` containing vessel-schedule terminology. This caused multiple unnecessary file reads before reaching the correct account.
- Not using available metadata fields for filtering wastes operations and increases error surface.
- Metadata fields provide direct filtering paths that bypass multiple reads. The `account_manager` field in account files points to the specific manager contact, but agents may instead search by name (task t39 required two searches: one to find the account, another to find the manager contact by searching for "Oliver König") rather than using `account_id` or `role=account_manager` for direct lookup.

**Premature NONE_CLARIFICATION:**
- Agents may abandon search after initial empty results without attempting date-range or contextual narrowing. In task t43, the agent searched three times with no matches, then listed `/01_capture/influential` and stalled, ultimately returning `NONE_CLARIFICATION` — but never calculated that "37 days ago" from <date> correlates to approximately <date>, then searched for or filtered captured files by that date window.
- Premature NONE_CLARIFICATION occurs when agents exhaust simple search patterns but skip: (a) date range calculation, (b) listing and filtering subdirectories, or (c) applying structural field filters before concluding data is absent.
- Date range calculations must be precise. In task t42, the agent searched for `captured~39 days ago` and received no matches. The correct calculation should yield a date window matching files from that period (e.g., `<date>` for "39 days ago" from April 30, 2026), but the search query's incorrect date calculation produced no results, demonstrating that flawed math during premature NONE_CLARIFICATION leads to unnecessary directory listing and stalled resolution.
- Name ordering variations can cause false empty results before refinement. In task t16, the first search with `query="Ines Möller"` returned no matches; only after searching with `query="Ines"` did the agent find the contact. Agents should attempt alternate name orderings (e.g., "Möller, Ines") or partial first/last name searches before concluding contacts are absent.

## Shortcuts
- **Direct search fallback**: When initial search terms return no matches, try searching for the person or entity name directly in the filesystem, which may locate the relevant file through different indexing. Example: "Dennis Bender" search failed initially but search with empty pattern found <contact>.json
- **Search for the person entity**: Before generic search, try searching for the full name or key entity — this often retrieves the containing file more reliably than searching for the attribute
- **Search account then read**: When looking for an account field (like legal_name), search for the account name first, then read the specific account file to extract the field. The search hit shows which file and line contains the match
- **List-then-filter strategy**: For multi-criteria lookups (Dutch banking + open security review), list the accounts directory first, then read account files sequentially to apply filters. Account files often include compliance_flags or status fields that encode security review state
- **Read associated contact file**: After matching an account, read the linked contact file (via primary_contact_id) to retrieve email or other contact fields
- **Two-step person resolution**: For agent/manager email lookups, first read the account file to find the person name, then search for that name to locate the manager contact file with email
- **Filename encoding limitations**: Note that capture files in /01_capture may use date prefixes (e.g., 2026-02-10__) which can be inspected for time-based queries, but date math is required to determine "37 days ago" relative to current context
- **Clarification needed for time-based lookups**: Queries referencing relative time periods ("captured X days ago") require temporal calculation that agents must handle explicitly or request user confirmation on
- **Empty pattern search for person lookup**: When person name search fails (e.g., "Möller Ines"), an empty pattern search can locate the contact file by matching against names indexed in contact files (found contacts/<manager>.json:4)
- **Search hits include line numbers for targeted reading**: Search results show specific file:line locations (e.g., contacts/<manager>.json:4) allowing direct extraction of fields from matching lines
- **Contact files indexed by role and tags**: Searching for "account manager" returns manager contact files, enabling two-step resolution where account lookup provides manager name, then person lookup finds manager's contact file
- **Name order variation in contact records**: Contact files store names in "FirstName LastName" format (e.g., "Pascal Heinrich") while queries may use "LastName FirstName" (e.g., "Heinrich Pascal") — both orderings can successfully locate the same contact file
- **Search-hit filtering by account attributes**: When a search returns multiple account candidates, read each file to inspect region, industry, or country fields to determine which matches the multi-attribute query (e.g., Dutch + port-operations + logistics filters out German retail accounts)
- **Account name search reliability**: Searching for an account name directly (e.g., "CanalPort") returns exact matches more consistently than searching for descriptors like "port-operations shipping"
- **Role-tagged contact files for direct resolution**: Contacts with roles like "account_manager" are tagged in their file, allowing search by role to locate the appropriate contact file for two-step email resolution
- **Account file fields encode multi-criteria matches**: Account files contain region, industry, country, and other fields that enable filtering when search returns multiple candidates — read account files to confirm the correct match before retrieving the linked contact

## Successful pattern: t16 (2026-04-30)
<!-- researcher: t16:cfac6c2c360f -->

**Goal shape:** What is the email address of Heinrich Pascal? Return only the email

**Final answer:** <email>

**Trajectory:**
1. search
2. search
3. read(/contacts/<file>)
4. search
5. search

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t34 (2026-04-30)
<!-- researcher: t34:ac1a7f8f7ef7 -->

**Goal shape:** What is the exact legal name of the Benelux vessel-schedule logistics customer CanalPort account? An

**Final answer:** CanalPort Shipping B.V.

**Trajectory:**
1. search
2. read(/accounts/<file>)

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t38 (2026-04-30)
<!-- researcher: t38:19b7a08c2414 -->

**Goal shape:** What is the email of the primary contact for the Dutch port-operations shipping account account? Ret

**Final answer:** <email>

**Trajectory:**
1. search
2. search
3. read(/accounts/<file>)
4. read(/accounts/<file>)
5. read(/contacts/<file>)

**Key insights:**
- (none)

**Applies when:** lookup

## Successful pattern: t39 (2026-04-30)
<!-- researcher: t39:167bf28f37f5 -->

**Goal shape:** What is the email address of the account manager for the Benelux vessel-schedule logistics customer

**Final answer:** <email>

**Trajectory:**
1. search
2. read(/accounts/<file>)
3. search
4. read(/contacts/<file>)

**Key insights:**
- (none)

**Applies when:** lookup

## Verified refusal: t43 (2026-04-30)
<!-- refusal: t43:OUTCOME_NONE_CLARIFICATION -->

**Goal shape:** can you tell me which article i captured 37 days ago

**Outcome:** OUTCOME_NONE_CLARIFICATION

**Why refuse:** You captured articles on <date> and <date>, but there is no article captured on <date> (37 days before <date>). The nearest captures are:

- **<date>:** How I Use Claude Code
- **2

**Probes before refusal:**
1. search
2. search
3. search
4. list(/01_capture)
5. search
6. search

**Applies when:** lookup

## Successful pattern: t42 (2026-04-30)
<!-- researcher: t42:4986e2022bc7 -->

**Goal shape:** quick one: which article did i capture 39 days ago

**Final answer:** The article you captured 39 days ago (targeting ~<date>) is **"How I Use Claude Code"** from <date> — just 2 days before the target date. The nearest alternative is "OpenAI: harness engineerin

**Trajectory:**
1. list(/01_capture/influential)
2. search

**Key insights:**
- (none)

**Applies when:** lookup
