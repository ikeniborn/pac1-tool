## Spurious Write During Scope-Bounded Delete

- **Condition:** Task requests deletion of files from specific directories with an explicit "do not touch anything else" constraint.
- **Root cause:** Agent generates an unrelated write operation targeting an out-of-scope directory (e.g. `/01_capture/`) mid-execution, then self-corrects by deleting it — wasting two ops and risking partial side-effects if execution halts early.
- **Solution:** Before executing any write, assert the target path is within the explicitly scoped directories. Treat "do not touch anything else" as a hard allowlist on writes, not merely on reads.
