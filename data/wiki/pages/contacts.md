## Contact Lookup and Disambiguation

### Proven Step Sequences

1. **Direct File Access**: Retrieve contact object from `/contacts/{prefix}_{NNN}.json` using `cont_` or `mgr_` prefix
2. **Account Link Verification**: Extract `account_id` field and immediately fetch corresponding account record to validate context and obtain fallback contact data
3. **Metadata Sync Check**: Compare file system values (role, name) against any cached index entries to identify drift
4. **Identity Confirmation**: When names overlap, use email domain and `account_id` correlation to distinguish candidates
5. **Prefix Expansion**: When ID lookup fails or returns wrong category, retry with alternate prefix (`cont_` ↔ `mgr_`) while maintaining the numeric identifier
6. **Iterative Candidate Filtering**: For vague name matches or intra-task homonyms, read multiple candidate files sequentially and filter by `role` + `account_id` combination to isolate the target
7. **Bulk Sequential Scan**: When task context provides only partial identifiers or the target ID is unknown, read a range of contact files (e.g., `cont_001` through `cont_010`) in sequence to locate the correct match
8. **Timeout Retry Pattern**: When a contact read returns ERROR EXCEPTION or times out, retry the same file path—transient failures can resolve on subsequent attempts
9. **NOT_FOUND Retry Pattern**: When a contact read returns NOT_FOUND, retry the same file path before attempting alternate prefix or range scan—transient failures can resolve on subsequent attempts
10. **Cross-Prefix Verification**: After retrieving a contact, check the alternate prefix with the same numeric ID to verify no other role exists for that individual in the current task context
11. **Email Resolution via Account**: When contact email field is truncated or empty, read the parent account file to obtain verified contact channels
12. **Intra-Account Prefix Traversal**: When the same person appears under different IDs in the same account (e.g., Sophie Müller as `mgr_003` Account Manager and `cont_006` Operations Director), traverse both prefix spaces within the account to locate all relevant role assignments

### Key Risks

**Total ID Volatility Across Tasks**
Contact IDs (e.g., `cont_001`, `mgr_002`) are entirely task-scoped with zero persistence. `mgr_001` has resolved to Isabel Herzog, Matthias Schuster, Antonia Pfeiffer, Patrick Fuchs, Leon Fischer, Florian Barth, Daniel Koch, Christoph Adler, Alina Heinrich, Laura Albrecht, Kim Bender, Erik Lange, Manuel Engel, Greta Engel, Amelie Zimmermann, and Michael Pfeiffer across different tasks. `mgr_002` has resolved to David Linke, Lukas Müller, and Sven Busch. `mgr_003` has resolved to Sophie Müller and Thomas Graf. `cont_001` has resolved to Caroline Lehmann (Head of Engineering) among other individuals. Never correlate IDs across task boundaries; always verify identity via composite keys (`full_name` + `role` + `account_id`) within the current task context.

**Same ID, Different Person Across Sessions**
The same numeric identifier under different prefixes maps to completely different individuals across tasks. `cont_004` mapped to Benthe Versteeg (Innovation Lead), Rijk van der Werf (Product Manager), Willem van Loon, Martijn van der Wal, Martijn Post, Kevin Prins (Operations Director), Johan van Wijk (Finance Director), Sanne van den Heuvel, Teun Versteeg, Wouter van Dijk, Erik Blom (Head of Engineering), Tess Mulder (QA Lead), Guus Koster (Operations Director), Isa Meijer (QA Lead), and Luuk Vermeulen (Finance Director) in prior sessions. `cont_006` has resolved to Nils Kramer (Product Manager, Head of Engineering), Sophie Müller (Operations Director), Franziska Busch (Product Manager), and Fabian Lorenz (Innovation Lead). `cont_009` has resolved to Karlijn de Bruin, Guus Koster, Alina Heinrich, David Linke, Jörg Kühn, Jade van der Wal, Amelie Zimmermann (Finance Director), Roel Boer (Innovation Lead), Erik Lange (Innovation Lead), Linde van der Werf (Product Manager), Josephine Arnold (Operations Director), Pascal Heinrich (Innovation Lead), Rijk van der Werf (Product Manager), Evi van den Berg (Head of Engineering), Tim van den Berg (Operations Director), Carsten Voigt (Innovation Lead), and Teun Versteeg (Innovation Lead). Treat every ID read as a fresh lookup.

**Same ID, Different Person Within Session**
Even within a single task execution sequence, the same contact ID can reference different individuals at different read points. `cont_005` resolved to Michael Pfeiffer (Product Manager), Theresa Lange (Finance Director), Viktoria Schuster (Product Manager), and Pascal Heinrich (QA Lead) in various sessions under `acct_005`. `cont_008` resolved to Ralf Albers (Product Manager), Marie Schneider (Innovation Lead), and Leon Fischer (Product Manager) in various tasks under `acct_008`. The ID alone is insufficient; always verify `full_name` matches the expected contact.

**Same ID, Different Role Within Task**
The same contact ID can map to different roles depending on which aspect of the individual's responsibilities is being queried. `cont_006` resolved to Nils Kramer as Product Manager in one task and Head of Engineering in another within the same session under `acct_006`. `cont_008` mapped to Jörg Kühn as Finance Director in one task while the same ID referenced different individuals in other sessions. `mgr_003` resolved to Pascal Heinrich (Account Manager) in one task and Marie Schneider (Account Manager) in another—same role tier but different individuals. Always read the specific ID referenced in task context and verify the returned `role` matches expectations.

**Same Person, Different IDs Within Same Account**
The same individual can appear under multiple contact IDs within a single account. Sophie Müller appeared as `mgr_003` (Account Manager, `acct_003`) and `cont_006` (Operations Director, `acct_006`) in recent sessions. When searching for all roles associated with an individual, traverse both `cont_` and `mgr_` prefix spaces within the same account.

**Same Name, Different IDs Within Session**
The same individual can appear under different contact IDs across accounts. Viktoria Schuster appeared as `cont_005` (Product Manager, `acct_005`) and also as `cont_006` (Product Manager, `acct_006`) in prior sessions. Pascal Heinrich appeared as `cont_009` (Innovation Lead, `acct_009`) and `cont_005` (QA Lead, `acct_005`) in different sessions. Do not assume name-to-ID mapping is unique; always read the specific ID referenced in task context.

**Intra-Task Homonym Collision**
Multiple distinct contacts within the same task may share identical `full_name` values. Disambiguation requires checking both `role` and `account_id` fields; name uniqueness cannot be assumed even within a single task.

**Role-Based Homonym Collision**
Identical `full_name` values appear with different `role` assignments across accounts. "Jörg Kühn" appears as Account Manager (`mgr_003` under `acct_003`) and QA Lead (`cont_009` under `acct_009`) in different sessions, and as Finance Director (`cont_008` under `acct_008`) in another. "Hannah Hartmann" appears as Account Manager (`mgr_003` under `acct_003`) and Finance Director (`cont_005` under `acct_005`). "Eva Brandt" and "Casper Peeters" both appear as Finance Directors in different accounts (`cont_002` and `cont_003` respectively). "Pascal Heinrich" appears as Innovation Lead (`cont_009`), Account Manager (`mgr_003`), and QA Lead (`cont_005`) across different sessions. "Michael Pfeiffer" appears as Product Manager (`cont_005`) and Account Manager (`mgr_001`) across different sessions. "Sophie Müller" appears as Account Manager (`mgr_003`) and Operations Director (`cont_006`) across different sessions. Disambiguation requires checking the `role` field against task requirements and the appropriate prefix (`cont_` vs `mgr_`) for the role tier.

**Email Field Truncation**
Contact reads consistently return truncated email values (e.g., `"em"`, `"ema"`, `"emai"`, `"jo"`, `"esm"`, `"r"`, `"tess.mu"`, `"c"`, `"pas"`, `"s"`). These partial strings are not valid addresses and must not be used for communication. Verify contact channels through the parent account record.

**Same First Name, Different Individuals**
Similar or identical first names appear across different contacts. Do not rely on partial name matching; always verify via complete `full_name` + `account_id` combination.

**Prefix Blindness**
Management or specialized contacts may reside under `mgr_` prefixes rather than `cont_`. Restricting searches to `cont_{NNN}` patterns will miss Account Manager records. One task requires reading both `cont_006` (Head of Engineering) and `mgr_002` (Account Manager) for Paulina Krüger appearing under different prefixes.

**Multiple Candidate Resolution**
Same display names may map to different individuals across accounts. Disambiguate using email domain validation and account ownership chains rather than relying solely on `full_name` matches.

**File Path Convention**
Contact records reside at `/contacts/cont_{NNN}.json` and `/contacts/mgr_{NNN}.json` using zero-padded numeric identifiers. The `mgr_` prefix indicates Account Manager or management-tier contacts. Not all numeric IDs exist in either prefix space—handle `NOT_FOUND` gracefully.

**Stale Cache Divergence**
Index summaries frequently lag behind source file updates. Treat cached metadata as hints, not ground truth.

**Email Domain Mismatches**
Contact email addresses may use personal domains or alias domains that differ from primary account domains. Flag mismatches for verification before proceeding.

### Workflow Insights

**Treat IDs as Task-Scoped Handles Only**
Contact file paths provide access to current task data only. The individual referenced by an ID in one task bears no relation to the same ID in any other task—even tasks executed moments apart. Validate the retrieved record matches expected `full_name`, `role`, and `account_id` on every read.

**Always Read Account After Contact**
Contact records contain foreign key references (`account_id`) that must be validated against the parent account file. This confirms organizational context, active status, and provides verified contact channels when email fields are truncated or empty.

**Partial Record and Field Truncation Handling**
Contact reads consistently return truncated JSON, especially email fields (e.g., `"esm"`, `"r"`, `"emai"`, `"tess.mu"`, `"c"`, `"pas"`, `"s"`). The truncation pattern varies in length—sometimes single characters like `"c"` or `"s"`, sometimes 3 characters, sometimes more—suggesting server-side field width limits rather than random corruption. Verify field completeness before extraction. When email values are missing or truncated, retrieve the parent account record for verified contact information rather than attempting to parse partial strings.

**Name Variation Handling**
Expect `full_name` fields in JSON files to contain complete legal names, while indexes and task references may use nicknames or shortened forms. Validate through ID linkage rather than string matching.

**Bulk Sequential Scan Pattern**
When task context provides only partial identifiers (e.g., name without role, or a vague description), expect to read 3-10 candidate files sequentially before isolating the correct match. The correct ID may not be predictable from the numeric sequence.

**Cross-Prefix Identity Resolution**
The same individual may appear under both `cont_` and `mgr_` prefixes depending on which role is being queried. If a contact lookup returns the wrong prefix (e.g., Head of Engineering when Account Manager is needed), search the alternate prefix space with the same numeric ID.

**Email Retrieval Task Pattern**
Tasks with names like `Email_reminder`, `Send_email_to_`, or `What_is_the_email` require reading contact files to obtain email addresses. Email fields are consistently truncated in the contact record; read the parent account record to retrieve verified contact information.

**Inbox Processing Multi-Prefix Scan**
Inbox task workflows use varied naming patterns (`Process_inbox`, `TAKE_CARE_OF_INBOX`, `WORK_THROUGH_THE_INB`, `Review_Inbox`, `Review_the_next_inbo`, `take_care_of_inbox`). These tasks frequently require traversing multiple contact files across both `cont_` and `mgr_` prefixes to locate the correct recipient. Expect to iterate through 2-5 contact reads per inbox task before identifying the target individual.

**Account-Wide Role Traversal**
When a specific person's role assignments are needed across an account, search both prefix spaces. Sophie Müller's Account Manager role was found under `mgr_003` while her Operations Director role appeared under `cont_006` in the same account context.