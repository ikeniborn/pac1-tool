## Name Order Ambiguity in Contact Lookups
- Condition: Query uses "LastName FirstName" format when contact records store names as "FirstName LastName"
- Root cause: Name token order mismatch prevents exact string matching, causing searches to return no direct matches
- Solution: When a name search returns no matches, automatically try reversed token order before reporting failure or asking for clarification

---

## Read Operation Timeout on Single File
- Condition: Attempting to read a single file (e.g., telegram.txt) causes the read to time out repeatedly
- Root cause: File may be excessively large, corrupt, or the read path may be blocked
- Solution: After one timeout, do not retry the same file immediately; flag the file as unreadable and report partial results if any were obtained in earlier step

---

## Inefficient Sequential File Scan Without Filtering
- Condition: Agent reads every account file one-by-one to find those matching a manager name, triggering stall warnings at step 6
- Root cause: No use of search or batch filter; brute-force iteration through all files despite having a clear filter criterion (account_manager field)
- Solution: Use the search operation with a query targeting the account_manager field instead of reading files individually; search once, then read only matching results

---

## Duplicate Contact Name Ambiguity
- Condition: Multiple contacts share similar surnames (e.g., "Braun Markus" vs "Braun Clara"), causing lookup targets to be ambiguous
- Root cause: Name-only queries cannot resolve which of several same-surname contacts is the intended target
- Solution: When multiple contacts share a surname, surface both candidates and ask for clarification before proceeding

---

## Empty Search Query Causes Invalid Argument Error
- Condition: Agent submits a search operation with a blank or whitespace-only query pattern
- Root cause: Search API rejects empty query strings with INVALID_ARGUMENT error; the operation fails rather than returning empty results
- Solution: Always construct search queries with at least one meaningful token; if query terms are unavailable, use list/read operations instead of empty searches

---

## List Operation Timeout on Large Directory
- Condition: Listing a directory containing large or problematic files (e.g., an oversized Telegram.txt) causes the list operation itself to time out
- Root cause: The list operation attempts to enumerate metadata for all files, which can block when individual files are inaccessible or corrupt
- Solution: When list times out on a directory, report the failure and note which specific file(s) may be causing the block; do not retry the same list operation repeatedly
