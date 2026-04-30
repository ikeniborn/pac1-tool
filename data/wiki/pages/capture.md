<!-- wiki:meta
category: capture
quality: developing
fragment_count: 5
fragment_ids: [t09_20260430T133048Z, t33_20260430T140107Z, t08_20260430T163154Z, t09_20260430T163117Z, t33_20260430T165435Z]
last_synthesized: 2026-04-30
aspects_covered: workflow_steps,pitfalls,shortcuts
-->

## Workflow steps
```markdown
## Proven Sequences for Capturing Content from Source into Vault Paths

### Capture Denial Patterns

**Security-denied source capture attempts**  
When attempting to capture content from restricted web sources, the agent encounters `OUTCOME_DENIED_SECURITY`. Known blocked sources:

- `news.ycombinator.com` — HN discussions  
- `substack.com` — newsletter content  

**Standard denial workflow**  
1. Task specifies `task_type: capture` targeting restricted domain  
2. Agent evaluates source against security policy  
3. Outcome returns `OUTCOME_DENIED_SECURITY`  
4. No content written to vault path  

**Implication for vault path design**  
Exclude direct web scraping from `website` protocol domains in capture task definitions. Use intermediary processing or pre-approved content aggregation methods instead.
```

## Key pitfalls
- **Wrong target path**: Capture attempts can be denied when the target path falls outside the agent's permitted mutation scope. Evaluator FIX-415 blocked an attempted write to `/01_capture/influential/2026-04-04__runtime-safety-excerpt.md` because the mutation scope was empty, preventing unauthorized file writes regardless of source validity.
- **Source misidentification**: Capture tasks attempting to access external websites as content sources are denied per security policy (tasks t09, t33). Evaluators block attempts to capture from `news.ycombinator.com` and `substack.com`, as these sources fall outside permitted ingestion boundaries.
- **Partial captures**: Task fragments show content truncation where capture requests end mid-thought ("larg'" or "...from"), indicating the risk of incomplete data retrieval when tasks are interrupted or validation fails before full snippet acquisition.

## Shortcuts
Never attempt content capture from restricted domains (e.g., `docs.anthropic.com` is blocked — domain deny-list enforcement)
All capture operations require a non-empty `mutation_scope` defined in the evaluator contract — writes are silently blocked when this scope is empty (see FIX-415 contract violation)
Failure mode is `OUTCOME_DENIED_SECURITY` with no fallback — security denials do not fall through to alternative capture methods, they hard-stop the operation
