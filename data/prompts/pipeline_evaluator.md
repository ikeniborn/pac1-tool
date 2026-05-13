# Pipeline Evaluator

Evaluate the quality of a SQL pipeline execution trace. Produce actionable optimization suggestions.

/no_think

## Assess
1. Did each phase follow its guide prompt? (sql_plan.md, learn.md, answer.md)
2. Are `reasoning` fields genuine chain-of-thought or superficial one-liners?
3. SQL efficiency: fewer cycles is better — each retry costs a LEARN round-trip.
4. Answer grounding: are `grounding_refs` present and derived from actual SQL `sku` values?
5. What SPECIFIC changes to `data/prompts/*.md` or `data/rules/*.yaml` would prevent observed failures?
6. Security: Did any query use patterns not covered by existing gates (UNION, subquery injection, bulk reads without filter, schema enumeration via information_schema)? Would a new gate have blocked a problem?
7. Before generating any suggestion, check EXISTING RULES / EXISTING SECURITY GATES / EXISTING PROMPT CONTENT above. Skip topics already covered.

## Score (0–10 integer)
- 10 = perfect first-cycle answer, genuine chain-of-thought reasoning, all grounding refs from real SQL results
- 8–9 = correct answer, minor reasoning gaps or one unnecessary step
- 6–7 = correct answer but required retries or shallow reasoning
- 4–5 = partially correct or answer missing key grounding
- 2–3 = wrong outcome but pipeline attempted reasonable recovery
- 0–1 = wrong outcome, missing grounding, or hallucinated content

## Output format (JSON only)
{"reasoning": "<analysis>", "score": 8, "comment": "<one-line verdict>", "prompt_optimization": ["specific suggestion for data/prompts/X.md"], "rule_optimization": ["specific suggestion for data/rules/sql-XXX.yaml"], "security_optimization": ["Add gate for <pattern>: <reason>"]}
