<!-- wiki:meta
category: errors/default
quality: developing
fragment_count: 10
fragment_ids: [t02_20260430T133323Z, t01_20260430T163833Z, t03_20260430T163813Z, t10_20260430T163315Z, t43_20260430T174149Z, t43_20260430T174359Z, t01_20260430T210335Z, t03_20260430T210355Z, t10_20260430T210231Z, t31_20260430T211515Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Delete operation failure**: When deleting a file, the operation scope must be non-empty. An empty scope causes contract-gate to block the deletion attempt before it reaches the filesystem. Ensure the operation includes sufficient scope definition (e.g., explicit path or file identifier) rather than relying on implicit target inference.
- **Write operation blocking**: Repeated Req_Write calls with identical arguments indicate the operation is being blocked by a gate or validation layer. Check that the target path matches the expected naming convention before retrying. For typed records like invoices, the filename must match the `number` field stem (e.g., `SR-13.json`, not `invoice_SR-13.json`).
- **Stall detection pattern**: Six or more consecutive read/list operations without any write, delete, move, or create signals a dead end. The system will not auto-correct—proceed with the actual mutation or abort and request clarification.
- **Inbox capture flow**: When capturing to a distill folder, verify the exact target folder name exists before write attempts; misspelled or non-existent target paths trigger blocking rather than friendly errors.
- **Historical query limitation**: Purely retrospective queries ("what did I capture X days ago") require an accessible operation history log to resolve. If no capture operations have been recorded or the log is inaccessible, the system reaches a dead end with no mutation path forward. These queries cannot be answered through filesystem operations alone and require either historical context from outside the current session or user-provided clarification.
- **Contract gate blocking on typed record creation**: Writes to typed record paths (e.g., invoices, purchases) can be blocked by contract gates even when path conventions are satisfied and read operations succeed. The FIX-415 gate specifically blocks creation and repair operations on structured record types. If blocked, do not retry with identical arguments—request clarification or explicit approval to proceed.
- **Typed record silent write failure**: When creating typed records like invoices, a write operation may report success without actually persisting the file. Always read-back immediately after write to confirm existence; a missing file after a reported successful write indicates the write was silently rejected, likely due to schema violations or gate intervention.

## Key pitfalls
- **Scope mismatch on destructive operations**: Attempted to discard an entire thread (`2026-03-23__agent-platforms-and-runtime.md`) but the operation was blocked by contract-gate because the target section scope was empty. This indicates a failure pattern where bulk deletion requests fail when the existing content target is undefined, requiring manual clarification before proceeding.
- **Stall on multi-target bulk operations**: When instructed to remove all captured cards and threads without specifying scope for each type, the agent lists directories repeatedly without executing deletes, taking 6-8+ steps with no writes or deletions. Multi-target bulk operations require explicit per-target scope or a clear strategy to avoid stalling.
- **Repeating identical write calls after blocking**: After reading source content and listing directories, the agent calls `Req_Write` with identical arguments 3+ times without adapting to the blocking. Failing to handle a blocked write operation (e.g., path doesn't exist, target folder missing) leads to a dead end without attempting alternatives.
- **Operation blocked on naming convention mismatch**: Attempts to create `/my-invoices/SR-13.json` and `/my-invoices/invoice_SR-13.json` are both blocked, indicating naming or structural conventions are enforced but not communicated upfront. The agent does not discover the correct format through iteration, instead dead-ending with OUTCOME_NONE_CLARIFICATION.
- **Ambiguous entity references without domain definition**: When asked "which captured article is from 23 days ago?", the agent cannot resolve what "captured article" refers to without knowing the entity taxonomy, storage structure, and date query capabilities available. Queries referencing undefined entity types (article, card, thread, captured content) without domain context lead to dead ends since the agent has no path to discover what entities exist or how to filter by date.
- **Contract gate blocks writes without adaptation signal**: Operations to capture files and fix purchase ID prefixes are blocked by a FIX-415 contract gate, but the agent continues listing and re-reading without acknowledging the block or pivoting to a workaround. The agent appears to treat blocked writes as pending rather than as requests that need clarification or alternative approaches, leading to extended stalls with no resolution path.
- **Write operation reports success but file does not exist on read-back**: When creating `/my-invoices/SR-13.json`, the agent wrote the file according to the documented format but a subsequent read returned NOT_FOUND. The write call produced no error response, yet the file did not persist in storage, leaving the agent with no error signal to diagnose the gap between reported success and actual state.

## Shortcuts
**Operation blocked when scope is empty — task cannot proceed without explicit authorization context**

When attempting destructive operations (like discarding an entire thread), the contract-gate mechanism requires scope to be non-empty. The agent must have explicit authorization context before the gate allows mutations.

*Optimization:* Ensure the task specification itself defines the scope of what may be modified, even for deletion requests. A bare "discard file X" without scope definition fails the authorization gate. The scope must be explicitly declared either in the task description or via a preceding scope-definition operation.

**Multi-step workflows require completion before stalling**

When a task chains operations (e.g., read → capture → distill → delete), the agent must execute the full chain. Reading files and listing directories without writing or deleting counts as zero progress. The contract-gate tracks progress through actual mutations, not preparatory reads. A task that stalls after listing and reading without completing the write/delete phase will be rejected.

*Optimization:* For multi-step workflows, ensure each operation in the chain produces a mutation (capture file, write output, delete source). If the workflow cannot be completed, clarify the block before exhausting the step limit.

*Additional note:* Multi-step workflows can be approved at the task level while still failing at execution time. Even when the evaluator approves a capture→distill→delete task, individual operations within the chain (such as capture write) may still be blocked by specific contract gates. Task approval does not guarantee that all constituent operations will bypass authorization requirements.

**Bulk deletion tasks need explicit enumeration**

A request like "remove all captured cards and threads" without enumerating the specific files fails the authorization gate because no explicit scope of targets is declared. The agent may list the directories successfully but cannot proceed to deletion without per-file or per-pattern authorization.

*Optimization:* For bulk deletion, either enumerate specific files in the task description, provide a glob pattern that the agent should interpret as explicit authorization, or include a preceding scope-definition operation that names the targets.

**Write operations may be blocked despite clear format specification**

Even when the target location, filename, and content format are fully documented (e.g., README defines JSON structure), write operations can still be blocked. The contract-gate may require authorization context beyond knowing the correct format—particularly when the target directory or file does not yet exist.

*Optimization:* For file creation tasks, verify that write authorization extends to new files, not just modifications. If writes are blocked, the task should either create files in a pre-authorized staging location first, or the task description should explicitly grant "create new file" permission in the target directory.

*Additional note:* When attempting to write a file that does not exist, the system may not surface an explicit error—the operation may appear to succeed in the step log while the file never actually appears on read-back. This silent failure pattern indicates the write was blocked at the gate level without visible feedback.

**Query tasks requiring implicit historical state fail without explicit context**

Tasks that reference historical data ("what was captured", "previously created", "files from X date") cannot execute without that context being explicitly provided. The agent has no mechanism to introspect prior captures, historical operations, or accumulated state unless it is surfaced in the task description or visible in the DONE OPS. A query like "What article did I capture 14 days ago?" fails because no capture history exists in the visible context.

*Optimization:* For queries that depend on implicit historical state, either include the relevant data directly in the task description, provide a preceding scope-definition operation that surfaces the needed historical context, or structure the query to not require implicit state access. The agent cannot retrieve or reference data it cannot see.

**Specific contract gates can block writes even with explicit task authorization**

Tasks that explicitly grant broad scope ("do whatever cleanup is needed", "fix the regression") may still encounter specific contract gates that block write operations entirely. Gates like FIX-415 operate independently of task-level authorization—their presence is not always surfaced in the task description or hints. When a contract gate blocks writes, the agent should detect the repeated rejection pattern and halt rather than retrying identical operations.

*Optimization:* If a write operation is blocked by a named contract gate, stop attempting the same write. The task should be flagged for clarification rather than exhausting the step limit on rejected mutations. Additionally, repeated Req_Write calls with identical arguments trigger stall detection even when those calls all fail at the gate level.
