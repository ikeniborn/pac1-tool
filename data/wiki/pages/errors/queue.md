<!-- wiki:meta
category: errors/queue
quality: developing
fragment_count: 10
fragment_ids: [t20_20260504T193415Z, t29_20260504T194135Z, t37_20260504T194901Z, t20_20260504T203515Z, t29_20260504T203638Z, t20_20260504T212329Z, t23_20260504T222243Z, t37_20260504T223324Z, t23_20260504T232746Z, t37_20260505T003815Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
1. **Systematic Queue Processing**
   - Take the first pending item from the queue
   - Process each item completely before moving to the next
   - Work through all items until queue is empty
   - Mark each completed item as OUTCOME_OK

2. **Complete Resolution Pattern**
   - Identify the item type (invoice, account, general)
   - Execute resolution steps appropriate to item category
   - Verify resolution completeness
   - Update status to OUTCOME_OK

3. **Batch Inbox Resolution**
   - Scan entire incoming queue for item count
   - Prioritize by urgency if applicable
   - Process items sequentially
   - Confirm each reaches OUTCOME_OK status

4. **Security-Aware Processing**
   - Perform security validation before executing resolution steps
   - Check for OUTCOME_DENIED_SECURITY triggers early in workflow
   - Route security-flagged items through appropriate exception handling
   - Only proceed to resolution completion when security checks pass

**Key Success Indicators:**
- t20 variant (queue processing) achieved OUTCOME_OK validating the sequential completion pattern (<date>)
- t20 task: "Work Through The Next Inbox Item..." executed successfully with OUTCOME_OK
- t29 variant encountered OUTCOME_DENIED_SECURITY during REVIEW INBOX operation
- Consistent pattern: complete each item before moving to next (verified by t20)
- Invoice lookup and account resolution steps integrated into standard flow
- Security validation must precede resolution execution to prevent denial outcomes
- t37 (<date>) confirmed OUTCOME_OK for processing single inbox item via queue approach
- t23 (<date>) encountered OUTCOME_DENIED_SECURITY during queue processing, confirming security validation applies to all task types including queue operations

## Key pitfalls
(None — no task fragments contained information relevant to invoice attribution errors, wrong account_id resolution, filename-as-owner-proxy mistakes, or unreadable candidates.)

## Shortcuts
Queue task processing security requirement:
- Security denial outcome recorded: [t23] Handle The Inbox Queue... (<date>, OUTCOME_DENIED_SECURITY)
- Successful queue processing confirmed: [t37] Work Through The Incoming Queue (<date>, OUTCOME_OK)

Account resolution priority:
- Body-named company wins in account resolution

Recipient identity rules:
- Use exact From header matching for recipient verification
