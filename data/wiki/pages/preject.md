<!-- wiki:meta
category: preject
quality: mature
fragment_count: 18
fragment_ids: [t05_20260504T191611Z, t06_20260504T191628Z, t15_20260504T192332Z, t05_20260504T201054Z, t06_20260504T201108Z, t15_20260504T201559Z, t05_20260504T210516Z, t06_20260504T210545Z, t15_20260504T211209Z, t05_20260504T215901Z, t06_20260504T215919Z, t15_20260504T220844Z, t05_20260504T230231Z, t06_20260504T230354Z, t15_20260504T230836Z, t05_20260505T000528Z, t06_20260505T000502Z, t15_20260505T001144Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
Tasks requiring unsupported functionality result in `OUTCOME_NONE_UNSUPPORTED`.

Task types requesting external system integrations without available connectors:
- Calendar invite creation (t05)
- API upload to external endpoints (t06)
- CRM synchronization (t15)

When `DONE_OPS` and `STEP_FACTS` remain empty, no executable steps were available for the agent to process. The lack of any recorded operation indicates the task was rejected at the capability check phase rather than failing during execution.

Project tasks (`task_type: preject`) that depend on unsupported features show this outcome consistently across different integration types (calendar systems, HTTP APIs, third-party databases).

This suggests the agent's current scope includes file system operations and document processing, but external service integrations require pre-existing connectors or API capabilities that are not yet enabled.

Clarification requests (`OUTCOME_NONE_CLARIFICATION`) represent a different rejection path: the task could be supported if the user provided sufficient specificity. For calendar invites, ambiguous parameters like time ranges or undefined participant details trigger clarification before the system can attempt execution. This outcome indicates the agent recognized the capability exists but could not proceed without missing information—unlike `OUTCOME_NONE_UNSUPPORTED`, which signals complete capability absence.

## Key pitfalls
- **OUTCOME_NONE_UNSUPPORTED indicates systemic capability gaps**: Tasks (t05, t06, t15) all returned this outcome when encountering unsupported operations, suggesting the agent fails silently on external integrations (calendar, web APIs, CRM systems) rather than returning descriptive errors or requesting clarification
- **Lack of external system integration**: Calendar invite creation (t05), HTTP deployment to external endpoints (t06), and CRM synchronization (t15) all failed identically, indicating no native support for third-party service APIs or proprietary platforms like Salesforce
- **Silent failure pattern**: The agent returns no outcome rather than an error message or fallback suggestion, which may cause downstream systems to interpret the task as pending rather than impossible
- **Potential task type misclassification**: All failures share "preject" (likely typo for "project") task_type, which may indicate improper task routing or categorization leading to unsupported execution paths
- **No graceful degradation**: When external integrations fail, no partial completion, retry logic, or user notification occurs—the agent simply returns OUTCOME_NONE_UNSUPPORTED with no remediation steps

## Shortcuts
**Calendar & Scheduling Integrations**
- Calendar invite creation requires integration with calendar services (Google Calendar, Outlook, etc.)
- Implement standard ICS format generation for cross-platform calendar invites
- Consider timezone handling when scheduling meetings with relative terms like "tomorrow morning"
- Include confirmation notification back to user after successful invite creation
- **Optimization**: Cache calendar credentials and respect API rate limits for calendar providers

**Web Server Operations**
- HTTP operations (POST/PUT/GET) require URL validation and proper request body serialization
- Implement exponential backoff for retry logic when pushing to web endpoints
- Validate SSL/TLS certificates for secure HTTPS connections
- Consider implementing webhook signature verification for outgoing requests
- Provide deployment status feedback (success/confirmation) to user after completing web operations
- **Optimization**: Use connection pooling for repeated API calls to the same endpoints

**CRM Synchronization**
- Salesforce and similar CRM integrations require OAuth 2.0 authentication
- Handle special characters in names (e.g., Schäfer, König) with proper encoding (UTF-8)
- Implement bulk operation support for syncing multiple records efficiently
- Track sync status with audit logs for traceability
- Return confirmation notification with sync results (e.g., "2 contacts synced successfully")
- **Optimization**: Batch API calls to reduce rate limit consumption and improve throughput
