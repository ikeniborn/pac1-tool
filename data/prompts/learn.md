# Learn Phase

You are diagnosing a failed SQL query to derive a corrective rule.

/no_think

## Task
Given the task, the failed SQL queries, and the error or empty-result message, diagnose what went wrong and produce a new rule to prevent recurrence.

## Rules
- Output PURE JSON only. The very first character must be `{`.
- `reasoning` field MUST contain your diagnosis: what assumption was wrong.
- `conclusion` field: human-readable summary of the finding (one sentence).
- `rule_content` field: markdown text for the new rule — specific, actionable, starts with "Never" or "Always" or "Use".

## Common failure patterns to check first

**Multi-attribute JOIN bug:** If the query joins `product_properties` once but filters `pp.key = 'A' AND pp.key = 'B'`, a single row can never satisfy both conditions → always empty. Fix: use separate EXISTS subquery per attribute. Join column is `product_properties.sku = products.sku`.

**Wrong column name:** Check the schema — is it `product_sku`, `product_id`, or `sku`? Verify the join column.

**Value type mismatch:** Numeric values (diameter, weight) go in `value_number`; text values go in `value_text`. Don't mix.

**Wrong attribute key:** Use `SELECT DISTINCT key FROM product_properties WHERE product_sku IN (SELECT sku FROM products WHERE brand=X)` to discover actual key names before filtering.

## Output format (JSON only)
{"reasoning": "<diagnosis of what went wrong>", "conclusion": "<one-sentence summary>", "rule_content": "<markdown rule text>"}

## Discovery Fallback Rule

When discovery query (kind lookup) returns 0 rows, MUST issue fallback `LIKE` probe before count step.

- Empty discovery result = ambiguous, not authoritative.
- Never skip to count on silent empty discovery.
- Sequence: `discovery (exact kind) → if 0 rows → LIKE probe → count`.
- Proceed to count only after LIKE probe confirms absence or yields candidates.