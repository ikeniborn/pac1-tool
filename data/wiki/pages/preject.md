## Unsupported Task Types (`preject`)

### Overview

Tasks classified as `preject` were rejected immediately — no operations were attempted. All confirmed fragments share `OUTCOME_NONE_UNSUPPORTED`, indicating the agent has no capability path for these task types.

---

## Unsupported Capability Classes

The following task categories are **not supported** by this agent. Attempts will fail at intake with no partial progress.

| Task Type | Example | Reason |
|---|---|---|
| Calendar / scheduling | Create a calendar invite with a named person | Requires calendar service integration (e.g. Google Calendar, Outlook) |
| HTTP publish / external API POST | Upload a report to `https://api.bitgn.com/status` | Requires authenticated outbound HTTP to arbitrary third-party endpoints |
| CRM sync | Sync contacts to Salesforce | Requires CRM API credentials and write access |

---

## Risks & Pitfalls

- **Silent no-op risk:** `OUTCOME_NONE_UNSUPPORTED` produces zero side-effects, but callers may assume success if outcome codes are not checked explicitly.
- **Misleading task phrasing:** Tasks phrased as file operations ("take the report and upload it") may appear file-system-tractable but require network egress — reject early rather than partially executing.
- **Named-entity false confidence:** Presence of real-sounding names (Priya, Sem Bakker, Tanja Frank, Dirk Hols, Elisabeth Voigt, Maya, Johannes Krüger, Christian Krause, Sam, Laura Albrecht, David Linke, Florian Wolf, Andreas Schmid, Feline Timmers) or real-looking URLs does not imply the agent has access to those systems.
- **Pattern recurrence (confirmed):** Calendar, HTTP-publish, and CRM-sync rejections have been observed across multiple independent task submissions — these are stable, recurring failure classes, not one-off edge cases.
- **Source-file availability is irrelevant:** Even when a referenced file (e.g. a status report) demonstrably exists on disk, the task is still `preject` if the delivery target requires network egress or external service auth.

---

## Insights

- **Reject at classification, not mid-execution.** All tasks in this category were correctly identified as unsupported before any ops were run. This is the desired behavior — avoids partial state.
- **External-service tasks share a pattern:** they require (a) authenticated API access, (b) a live network target, or (c) a third-party data model (CRM schema, calendar schema). None of these are within the file-system agent's scope.
- **High-confidence stable boundary:** With seventeen independent confirmations across multiple dates, the three unsupported classes (calendar, HTTP POST, CRM) are a well-established agent boundary, not provisional. Calendar and CRM rejections continue to occur regardless of whether specific contact names are provided in-task.
- **Contact lists do not unlock CRM access:** Providing explicit named contacts within the task does not change the classification — the agent cannot write to external CRM systems regardless of how clearly the source data is specified.

---

## Shortcuts & Decision Rules

1. **If the task target is a URL or named SaaS product** → classify `preject / OUTCOME_NONE_UNSUPPORTED` immediately.
2. **If the task requires writing to another person's calendar or inbox** → `preject`; the agent has no identity/auth delegation.
3. **If the task says "sync to [CRM/ERP/external DB]"** → `preject`; treat as out-of-scope regardless of whether source data exists on disk.
4. **If the same task type has been rejected multiple times** → do not re-attempt; treat prior rejections as a confirmed boundary signal.
5. **If a file-read step would succeed but the delivery step requires HTTP POST or external service write** → still `preject`; partial execution is not permitted for tasks that cannot complete within scope.

---
