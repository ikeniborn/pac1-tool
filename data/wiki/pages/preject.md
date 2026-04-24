## Task Type: preject (Calendar / Scheduling Requests)

### Status
Unsupported. The file-system agent has no calendar or invite-creation capability. All observed attempts terminate with `OUTCOME_NONE_UNSUPPORTED`.

### Observed Requests
- Create a calendar invite with John about starter repo cleanup review for tomorrow morning.
- Create a calendar invite with John about AI tooling review for tomorrow morning.
- Create a calendar invite with Maya about agent workflow retrospective for next Tuesday afternoon.
- Create a calendar invite with Maya about distill pipeline check-in for Friday at 14:00.
- Create a calendar invite with Priya about agent workflow retrospective for Friday at 14:00.

### Proven Step Sequences
None. No step sequence has ever produced `OUTCOME_OK` for this task type. The correct terminal behavior is to emit empty `DONE OPS` and `STEP FACTS` sections and return `OUTCOME_NONE_UNSUPPORTED`.

### Risks & Pitfalls
- Do **not** call `reporttaskcompletion` with empty/placeholder arguments — it returns `ERROR INVALID_ARGUMENT`.
- Do not attempt to simulate calendar actions via file-system ops; there is no mapping from invites (attendees, times, agendas) to available tools.
- Do not silently retry; the capability gap is structural, not transient.
- Do not fabricate calendar artifacts (e.g., `.ics` files) unless the user explicitly requests a file-based deliverable — the request is for an invite, not a file.

### Task-Type Insights & Shortcuts
- Recognize `preject` calendar-invite requests immediately by cues: "calendar invite", "schedule with <person>", "meeting/retrospective/review/check-in for <time>" (including specific clock times like "Friday at 14:00" and vague times like "tomorrow morning").
- Recurring subject patterns: "agent workflow retrospective", "<topic> review for tomorrow morning", and "<topic> check-in for <day> at <time>" recur with varying attendees/topics (e.g., starter repo cleanup, AI tooling, distill pipeline); still unsupported regardless of specificity.
- Short-circuit: return `OUTCOME_NONE_UNSUPPORTED` without invoking any ops.
- Leave `DONE OPS` and `STEP FACTS` empty rather than emitting failing calls.

## Verified refusal: t05 (<date>)
<!-- refusal: t05:OUTCOME_NONE_UNSUPPORTED -->

**Goal shape:** Schedule a calendar meeting with a named contact for a specific day and time

**Outcome:** OUTCOME_NONE_UNSUPPORTED

**Why refuse:** A calendar API tool (e.g. Google Calendar, Outlook) or MCP integration must be configured before this task can be completed

**Probes before refusal:**
(no discovery steps)

**Applies when:** preject
