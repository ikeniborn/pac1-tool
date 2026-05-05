<!-- wiki:meta
category: errors/distill
quality: nascent
fragment_count: 1
fragment_ids: [t08_20260505T163305Z]
last_synthesized: 2026-05-05
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
- **Task type `distill`** (t08): Captures knowledge from completed tasks even when straightforward—e.g., "Delete that card" succeeded with OUTCOME_OK. Record the task and outcome; no complex reasoning needed.

## Key pitfalls
- **Incomplete analysis**: Agent may miss relevant files, relationships, or context when processing tasks, leading to incomplete or partial results
- **Wrong output format**: Generated output may not match the expected format (e.g., wrong JSON structure, missing delimiters, incorrect field ordering)
- **Missing required card fields**: When generating card objects, agent may omit mandatory fields or produce malformed card data that fails validation
- **Silent failures**: Agent may complete a task without reporting that analysis was incomplete or that output format deviated from specification
- **Context window limits**: Large file operations or batch tasks may be truncated, causing partial execution
- **Validation gaps**: Without explicit field validation, agent may output cards with missing or null required attributes
- **Dead-end tasks**: Successful task outcomes (OUTCOME_OK) may still represent dead ends where no useful output was produced, as in deletion tasks where no artifact remains

## Shortcuts
- **Direct imperatives succeed**: Short, unambiguous commands (e.g., "Delete that card") with clear objects of action tend to complete with OUTCOME_OK
- **Minimal context required**: Simple tasks don't need additional framing, agent context, or success criteria preambles
- **Single-objective focus**: Each task fragment works best with one clear objective rather than compound or conditional actions
- **Outcome transparency**: Always record OUTCOME_OK even for trivial successes; absence of failure entry signals smooth execution
- **Atomic task units**: Each task_id represents one testable unit of work — this enables precise tracking and regression detection
- **Verb precision in card titles**: Use specific action verbs ("Delete", "Copy", "Rename") rather than generic ones ("Manage", "Handle") for clarity
- **Soft budget discipline**: Keep distilled insights under 66 lines; merge similar patterns rather than expanding text
