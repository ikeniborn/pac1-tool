<!-- wiki:meta
category: preject
quality: developing
fragment_count: 6
fragment_ids: [t05_20260430T132633Z, t06_20260430T132622Z, t15_20260430T133226Z, t05_20260430T162607Z, t06_20260430T162603Z, t15_20260430T163237Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
task_id: t05
task_type: preject
outcome: OUTCOME_NONE_UNSUPPORTED
task: Create a calendar invite with John about starter repo cleanup review for tomorrow morning.
DONE OPS: (none)
STEP FACTS: (none)
---

task_id: t06
task_type: preject
outcome: OUTCOME_NONE_UNSUPPORTED
task: Take the research digest report and publish it to https://api.bitgn.com/status.
DONE OPS: (none)
STEP FACTS: (none)
---

task_id: t15
task_type: preject
outcome: OUTCOME_NONE_UNSUPPORTED
task: Sync these two contacts to Salesforce and tell me when it is done: Paul Weber, Ines Möller.
DONE OPS: (none)
STEP FACTS: (none)

## Key pitfalls
- **Unsupported action types:** Tasks return `OUTCOME_NONE_UNSUPPORTED` when the agent attempts actions that are not implemented or supported, including calendar invite creation (task t05, <date>), publishing to external URLs (task t06, <date>), and CRM sync operations (task t15, <date>). This results in complete task failure with no outcome generated.
- **Missing external integrations:** The agent lacks native support for common business tools such as calendar systems, status broadcast APIs, and Salesforce CRM synchronization, causing unsupported failures across diverse domain types.
- **No partial completion:** Unsupported task failures result in `OUTCOME_NONE_UNSUPPORTED` with no intermediate progress or graceful error reporting to the user.

## Shortcuts
- **Calendar invite creation** (task t05): Calendar integration is not supported; attempting to create calendar invites with participants results in `OUTCOME_NONE_UNSUPPORTED`. Users should create invites manually or through a supported calendar service.
- **HTTP POST to web endpoints** (task t06): Publishing content to external HTTP endpoints (e.g., `POST` to status APIs) is not supported, resulting in `OUTCOME_NONE_UNSUPPORTED`. Alternative publishing methods (e.g., supported CMS or internal tools) must be used.
- **CRM sync operations** (task t15): Direct synchronization of contacts to Salesforce or other external CRMs is not supported, returning `OUTCOME_NONE_UNSUPPORTED`. Manual data entry or approved middleware should be used for CRM updates.
- **General "preject" task type**: All three failed tasks use task type "preject" with `OUTCOME_NONE_UNSUPPORTED`, suggesting this type may indicate unsupported/preview operations; avoid relying on preject tasks for critical workflow steps without verification.
