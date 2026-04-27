## Date Arithmetic Miscalculation

- Condition: Agent is asked to compute a date offset (e.g., "+7 days", "in 1 week") from today.
- Root cause: Agent skips vault root discovery gate and attempts arithmetic without confirming the anchor date first.
- Solution: Always list vault root (`/`) as a discovery gate before performing date arithmetic; confirm the anchor date, then compute the offset.

## No-Match Clarification Failure

- Condition: Agent is asked to find a file matching an exact computed date (e.g., "21 days ago") and no file exists with that prefix.
- Root cause: Agent exhausts search paths and returns nothing instead of surfacing the absence as a concrete, actionable clarification to the user.
- Solution: When a targeted date search yields zero results, explicitly report the computed target date and the files that were found nearby, then ask the user to confirm the intended date or broaden the search window.

## Premature Search Termination on Date Miss

- Condition: A date-prefixed file is not found in the expected directory; agent stops after one `find` call.
- Root cause: Agent assumes the first failed search is definitive and does not check sibling directories or alternative capture paths.
- Solution: After a failed date-prefix search in one directory, enumerate sibling directories and retry before concluding no match exists.

## Ambiguous Offset Window — Multiple Candidates Unreported

- Condition: Agent is asked for a file captured N days ago and multiple files fall within a reasonable window of that target date.
- Root cause: Agent returns only the first match (or none) without acknowledging that several files are plausible candidates for the requested offset.
- Solution: When a date-offset search yields more than one candidate within the expected window, report all candidates and let the user confirm the intended file rather than selecting silently.
