
## Vault lookup

**Anti-hallucination gate**: BEFORE returning OUTCOME_NONE_CLARIFICATION
you MUST have executed at least ONE of (tree|find|search|list) against the
actual vault and observed the result. Claims like "directory not accessible",
"vault not mounted", "path not found" without a preceding list/find/tree call
are hallucination — the vault IS mounted, tools WILL work.

**grounding_refs is MANDATORY** — include every file you read that contributed to the answer.