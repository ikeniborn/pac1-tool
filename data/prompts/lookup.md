## SQL anti-hallucination gate

BEFORE returning OUTCOME_NONE_CLARIFICATION:
you MUST have executed at least ONE SQL query via /bin/sql and observed the result.
Claims like "product not found" or "attribute unknown" without a preceding exec are hallucination
— the database IS accessible, /bin/sql WILL work.

**grounding_refs is MANDATORY** — include every `/proc/catalog/{sku}.json` that contributed to the answer.
