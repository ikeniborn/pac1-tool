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

## Output format (JSON only)
{"reasoning": "<diagnosis of what went wrong>", "conclusion": "<one-sentence summary>", "rule_content": "<markdown rule text>"}