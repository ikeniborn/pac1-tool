```markdown
## Non-existent Folder Path Tried in Root Listing
- Condition: Agent lists root (`/`), observes folder names, then immediately tries to list sub-paths that don't exist (e.g., `/01_capture/influential` when the correct path is `/01_capture/influential/<subfolder>` or trying `/00_inbox` which has no counterpart in the vault structure)
- Root cause: Agent misinterprets vault directory naming conventions as literal path segments, or assumes inbox-related paths that only exist as display names
- Solution: Verify folder existence before listing sub-paths; use exact vault paths as observed from the root listing

## Temporal Estimation Rounding Causing None Match
- Condition: Agent estimates "today" as the most-recent vault file date + a fixed offset (e.g., +5 days), then uses that estimate to compute a historical date; the computed date falls between actual file dates, yielding no exact match
- Root cause: Fixed offset estimation lacks precision; computed target date does not correspond to any actual vault artifact date
- Solution: When computed target date has no exact vault match, request clarification from user rather than guessing nearest dates

## Stall Without Productive Action
- Condition: Agent takes 6+ sequential read/list operations without any write, delete, move, or create operation
- Root cause: Agent continues exploring without committing findings or making progress toward task completion
- Solution: After 3–4 listing operations, evaluate whether sufficient information is available to answer or take action; request clarification if data is insufficient rather than continuing to explore
