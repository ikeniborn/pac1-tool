## File Read Timeout

- **Condition:** Agent attempts to read a file (e.g. `/docs/channels/Telegram.txt`) and the operation does not complete within the allowed time window.
- **Root cause:** The read operation blocks indefinitely or the underlying I/O layer fails to respond, triggering a timeout exception.
- **Solution:** Retry the read once after a short delay. If the second attempt also times out, report the file as unreachable and surface the error to the caller rather than silently continuing.

---

## Empty Search Query Yields No Matches

- **Condition:** Agent issues a `search` call with a blank or whitespace-only query string.
- **Root cause:** The search index requires a non-empty term; an empty string matches nothing by design.
- **Solution:** Always construct a concrete search term before calling search. Derive the term from the task (e.g. the manager's name, a keyword from the goal). Never dispatch a search without validating that the query string is non-empty.

---

## Read-Loop Stall on Lookup Task

- **Condition:** Agent accumulates many sequential file reads without writing, moving, creating, or deleting anything, triggering repeated stall warnings and eventual stall escalation.
- **Root cause:** The agent uses brute-force enumeration (read every file one by one) instead of using search to narrow candidates first. Because each read yields partial results, the agent keeps reading without committing a final answer.
- **Solution:** Use search to identify candidate files before reading. Once enough matching records are found to satisfy the query, immediately write or return the answer — do not continue reading unrelated files. Treat the first stall warning as a hard signal to either commit a result or abort.

---

## Name-Order Mismatch in Search

- **Condition:** Task references a person as "Engel Manuel" (surname-first); the vault stores the name as "Manuel Engel" (given-name-first). Initial searches with the inverted form return no matches.
- **Root cause:** The search index stores names in a single canonical order; a reversed query does not match.
- **Solution:** When a search returns no results for a full name, retry with the tokens in reversed order and also try searching each token independently. Normalise name queries before searching.
