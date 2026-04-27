## Unsupported Task Types (`preject`)

### Overview

Tasks classified as `preject` are **pre-rejected** — they are structurally unsupported by the file-system agent before any steps are attempted. No operations are executed; the outcome is always `OUTCOME_NONE_UNSUPPORTED`.

---

## Proven Step Sequences

*No successful step sequences exist for `preject` tasks — by definition, execution never begins.*

---

## Unsupported Task Categories (Confirmed)

| Task Type | Example | Reason |
|---|---|---|
| **Calendar / scheduling** | Create a calendar invite with a contact for a specific time | Requires calendar service integration (e.g. Google Calendar, Outlook) — outside file-system scope |
| **HTTP deployment / API push** | Deploy a report to an external HTTPS endpoint | Requires authenticated HTTP client and network egress — not a file-system operation |
| **CRM sync** | Sync contacts to Salesforce | Requires third-party CRM API credentials and integration — outside agent capability |

---

## Key Risks and Pitfalls

- **Silent no-op risk:** A `preject` task produces no side-effects and no partial state. Callers must not assume any work was done or will be retried automatically.
- **Misrouting:** Tasks that *sound* file-related (e.g. "take the report and deploy it") may be rejected at pre-check because the *destination* is an external API, not a local path. The file-read step is never reached.
- **User expectation mismatch:** Tasks involving people (contacts, invites, CRM records) consistently fall outside scope — do not attempt workarounds via local file writes as proxies.

---

## Task-Type Insights and Shortcuts

- **Fast rejection signal:** Any task mentioning a URL (`https://…`), a named external service (Salesforce, Outlook, etc.), or scheduling with another person → classify as `preject` immediately; skip all planning.
- **No partial execution:** There is no value in executing the file-read portion of a deploy-style task if the write destination is unsupported. Reject whole-task, not step-by-step.
- **Logging recommendation:** Always record `OUTCOME_NONE_UNSUPPORTED` with the specific unsupported capability (network egress, calendar API, CRM API) to enable downstream routing to capable agents.

---
