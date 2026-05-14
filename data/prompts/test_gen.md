# Test Generation Phase

You generate acceptance tests for a catalogue lookup task. Tests run as Python functions in an isolated subprocess (stdlib only).

/no_think

## Input

- `TASK` — the user's catalogue lookup question
- `DB_SCHEMA` — the database schema
- `AGENTS_MD` — vault rules (outcome types, message format)

## What to generate

**`test_sql(results: list[str]) -> None`**
Each element in `results` is a CSV string (first line = column headers, rest = data rows).
Assert:
- Required columns are present in the header (e.g., `sku`, `path`, or `count`).
- Results are non-empty when the task implies products exist. (Skip this check for zero-count tasks — empty results are valid.)
- Numeric values are plausible (e.g., COUNT ≥ 0).

**`test_answer(sql_results: list[str], answer: dict) -> None`**
`answer` keys: `outcome`, `message`, `grounding_refs`, `reasoning`, `completed_steps`.
Assert:
- `answer['outcome']` equals the expected outcome string (e.g., `'OUTCOME_OK'`).
- `answer['message']` is non-empty.
- `answer['grounding_refs']` is non-empty when `outcome == 'OUTCOME_OK'` and task implies products found. (Empty grounding_refs is allowed for zero-count / aggregate-only answers.)
- `answer['message']` contains key product-related facts from the task (brand, type, etc.) when outcome is OK.

## Rules for test code

- Single function per test. No class.
- Use only Python stdlib. Put any needed imports inside the function body.
- Signal failure via `assert` (raises `AssertionError`) or `raise ValueError(...)`.
- Tests must be deterministic.
- Empty `results` list is valid for zero-count tasks — do not assert non-empty unconditionally.

## Output format

Output PURE JSON only. First character must be `{`.

```json
{
  "reasoning": "<analysis: expected outcome, required columns, emptiness rules>",
  "sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    header = results[0].split('\\n')[0].lower()\n    assert 'sku' in header or 'count' in header, f'missing sku/count column: {header}'\n",
  "answer_tests": "def test_answer(sql_results, answer):\n    assert answer['outcome'] == 'OUTCOME_OK', f\"wrong outcome: {answer['outcome']}\"\n    assert answer['message'], 'message is empty'\n    assert answer['grounding_refs'], 'grounding_refs empty for OK outcome'\n"
}
```
