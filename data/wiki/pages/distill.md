<!-- wiki:meta
category: distill
quality: nascent
fragment_count: 2
fragment_ids: [t08_20260504T211050Z, t08_20260505T001102Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- When instructed to "Delete that card" during distill operations, proceed directly without seeking clarification — the instruction is self-contained and unambiguous (task_id: t08, date: <date>)
- When a distill operation includes "Archive the thread" (even if instruction is truncated), treat it as a self-contained directive requiring no further clarification — the system may proceed with archival based on the available context (task_id: t08, date: <date>)

## Key pitfalls
**Incomplete Analysis**
- AI may fail to fully traverse nested directory structures, resulting in cards for files that were not fully analyzed or referenced files that are missing from the output
- Incomplete scanning can cause the agent to miss critical metadata (file permissions, ownership, timestamps) needed for accurate card generation
- Large directory trees risk being partially processed due to token/iteration limits before analysis completes

**Wrong Output Format**
- AI-generated JSON may deviate from the expected schema (incorrect field names, wrong data types, or malformed structure)
- Nested objects or arrays may be improperly constructed, causing parsing failures in downstream systems
- Output may include formatting errors (missing commas, unquoted keys) that invalidate the JSON payload

**Missing Required Card Fields**
- Generated cards may omit mandatory fields such as `file_path`, `size`, `timestamp`, or `checksum`, leading to validation errors
- The "Delete that card" task with `OUTCOME_NONE_CLARIFICATION` exemplifies this risk: when field requirements are ambiguous or undefined, the AI may produce incomplete cards that fail to meet specification
- Conditional fields that apply to certain file types may be silently omitted when the AI cannot determine file characteristics accurately

## Shortcuts
- Cards with outcome: OUTCOME_NONE_CLARIFICATION indicate tasks where no clarification was needed from the user — the instruction was self-contained and unambiguous
- Simple, direct task descriptions like 'Delete that card' work well when context is already established; no elaboration required
- When the outcome field is OUTCOME_NONE_CLARIFICATION, the card title should make the action explicit so it's clear without needing to read the full task body
- Date stamps on distill fragments (e.g., <date>) provide provenance for when the insight was captured from user interaction
- Brief task descriptions are appropriate when prior context makes them self-explanatory; verbose explanations are unnecessary for simple actions
- Distill tasks with no clarification needed are indicators of well-scoped work — the system understood the user's intent immediately
- Even incomplete task fragments can achieve OUTCOME_NONE_CLARIFICATION when the available context is sufficient to determine the intended action
