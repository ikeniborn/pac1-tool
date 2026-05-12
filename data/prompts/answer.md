# Answer Phase

You are formulating the final answer to a catalogue lookup task based on SQL query results.

/no_think

## Rules
- Output PURE JSON only. The very first character must be `{`.
- `reasoning` field MUST justify your answer from the SQL results — cite specific values.
- `message` follows the format rules in AGENTS.MD (include <YES>/<NO> for yes/no questions).
- `outcome` must accurately reflect task completion:
  - OUTCOME_OK — answered successfully (including "product not found" answers)
  - OUTCOME_NONE_CLARIFICATION — task too vague to answer even with SQL results
  - OUTCOME_NONE_UNSUPPORTED — query type not supported by the database
  - OUTCOME_DENIED_SECURITY — security violation detected
- `grounding_refs` MUST list `/proc/catalog/{sku}.json` for every SKU in the results. Construct path as `/proc/catalog/{sku}.json` using the `sku` column value.
- `completed_steps` — laconic list of steps taken (2–5 items).

## Output format (JSON only)
{"reasoning": "<justification from SQL results>", "message": "<answer text>", "outcome": "OUTCOME_OK", "grounding_refs": ["/proc/catalog/SKU.json"], "completed_steps": ["validated SQL syntax", "executed query", "found N results"]}