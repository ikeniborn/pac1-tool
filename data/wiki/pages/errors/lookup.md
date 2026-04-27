## File Read Timeout / Exception

- **Condition:** Agent attempts to read a file (e.g., `/docs/channels/Telegram.txt`) and the operation either throws a generic exception or exceeds the read timeout.
- **Root cause:** The target file is inaccessible — either it does not exist, is locked, or the underlying I/O layer fails to respond within the allowed window. Retrying the identical call without change yields the same error.
- **Solution:** After the first timeout or exception, verify the file path exists via a directory listing or search before retrying. If the path is confirmed missing, report the resource as unavailable rather than retrying indefinitely.

---

## Search Result Mismatch (Wrong Record Returned)

- **Condition:** A keyword search returns a set of matching file references, but reading one of those files yields data that does not match the search term (e.g., searching for "Acme" returns `<account>.json`, but its `account_manager` field does not contain the searched name).
- **Root cause:** Search indexes on partial text matches across multiple fields; the hit may originate from a different field (e.g., `name`) than the one required to answer the query.
- **Solution:** After reading a candidate file, explicitly verify that the field relevant to the query contains the expected value before using it in the answer. Discard non-matching records and continue reading remaining candidates.

---

## Stall on Read-Only Loop

- **Condition:** Agent executes 6 or more consecutive read/search steps without performing any write, delete, move, or create operation on a task that ultimately requires only a lookup answer.
- **Root cause:** The agent re-reads already-visited files or searches with the same query instead of aggregating results and terminating. Search results are not cached, leading to repeated identical queries. No progress gate forces synthesis after a bounded number of reads.
- **Solution:** Cache search results; before executing a search, verify that the identical query has not already been performed and reuse cached results if available. After collecting all search-result candidates, read each once and accumulate matches; do not re-search or re-read. Once all candidate files are read, immediately synthesize and output the answer. Treat receipt of a stall warning as a hard signal to stop gathering and produce output.

---

## Name Token Order Mismatch (Search Miss)

- **Condition:** A search for a person's name (e.g., "Adler Svenja") returns no results, while the same name stored in the vault uses reversed token order ("Svenja Adler").
- **Root cause:** The agent issues the search query using the input token order (surname first) without considering that vault records may store names in a different canonical order (given name first). A strict substring match then fails.
- **Solution:** When a name search returns no matches, retry with tokens reversed before concluding the name is absent. Normalise query tokens to both orderings (e.g., "Adler Svenja" → also try "Svenja Adler") and union the results.

---
