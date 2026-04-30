<!-- wiki:meta
category: errors/capture
quality: nascent
fragment_count: 1
fragment_ids: [t01_20260430T133430Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
**Sequence t01** — Capture attempt (dead end)

```
1. LIST /01_capture/influential/
   → 5 files confirmed on disk
   
2. LIST /02_distill/cards/
   → 5 card files + _card-template.md confirmed
   
3. LIST /02_distill/threads/
   → 2 threads + _thread-template.md confirmed
```

**What happened:** All three list operations succeeded and verified content existed. The task then stalled — no deletion (capture-to-remove) was executed. Outcome: OUTCOME_NONE_CLARIFICATION

**Pattern observed:** Lists alone cannot satisfy a "remove captured X" directive. A successful capture sequence requires either:
- a MOVE or DELETE operation after listing, or
- explicit confirmation that the listed items are the intended targets before proceeding

**Dead end reason:** Task was evaluated before the capture/deletion step could be initiated. The clarification gate prevented forward progress.

## Key pitfalls
- **Ambiguous scope terms**: Vague identifiers like "captured cards" or "processed threads" can resolve to multiple directories or file sets, causing the agent to list locations without executing. The term "captured" is undefined—is it a file property, a path convention, or a naming pattern? Agents must request explicit path confirmation before bulk operations.

- **Listing without action**: The current step log shows the agent listed `/01_capture/influential/`, `/02_distill/cards/`, and `/02_distill/threads/` but did not proceed. This indicates the agent recognized ambiguity and halted, but the lack of a clarification request left the task dead-ended.

- **Inferred vs. explicit destinations**: When a task references items by semantic role ("remove all captured cards") rather than explicit paths, the agent may infer multiple possible target directories. Without disambiguation, the agent either acts on the wrong location or performs no action at all.

- **Partial vs. complete removal**: "Remove all captured cards" may intend only user-created cards, excluding templates (e.g., `_card-template.md`). Template files present in the same directory may be erroneously targeted or protected depending on how the agent interprets scope.

## Shortcuts
- **t01 — Dead end on destructive capture ops**: Task requested removal of captured cards and threads, but only LIST operations were performed. Outcome `OUTCOME_NONE_CLARIFICATION` suggests either no authorization for destructive actions or insufficient spec to proceed. Capture agents listing directories does not imply write/delete capability — distinguish READ operations from WRITE operations in task resolution.
