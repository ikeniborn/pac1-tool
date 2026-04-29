## Extraneous Read of Non-existent File After Task Completion
- Condition: Agent completes all required write operations correctly but then attempts to read a file not mentioned in the task requirements.
- Root cause: Agent assumes existence of an audit, log, or documentation file (e.g., `/docs/follow-up-audit.json`) for verification purposes that was never specified or present in the vault.
- Solution: Only read files explicitly required by the task or referenced in the vault structure. Do not attempt to read files based on assumptions about what "should" exist. Trust completed write operations and the vault structure as given.

---
