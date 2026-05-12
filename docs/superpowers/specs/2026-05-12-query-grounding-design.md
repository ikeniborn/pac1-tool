# Query Grounding: Design Spec

**Date:** 2026-05-12  
**Scope:** Programmatic hardening of query formation in ecom1-agent pipeline  
**Approach:** Full LLM-based resolve phase + enriched context + schema-aware gates

---

## Problem

`AGENTS.MD` and `.schema` are loaded once in `prephase.py` and inserted as raw text blocks into system prompts. The LLM must cross-reference them independently — no programmatic guarantees. This produces three recurring failure classes:
1. Hallucinated literals — WHERE clauses with values that don't exist in the DB
2. Ignored AGENTS.MD vocabulary — brand aliases, kind synonyms not used
3. Cycle exhaustion — 3 cycles consumed by discovery + filter that could fit in 2

---

## Architecture

New execution flow per task:

```
prephase  (+ schema_digest + agents_md_index)
  ↓
resolve   (NEW: LLM → discovery SQL → confirmed_values)
  ↓
pipeline  (max 3 cycles):
  ├─ _build_system: includes CONFIRMED VALUES + task-relevant AGENTS.MD sections
  ├─ sql_plan → security gate → schema-aware gate → EXPLAIN → EXECUTE
  ├─ error → learn (+ agents_md_anchor, dedup against AGENTS.MD)
  └─ confirmed_values updated from DISTINCT results of each cycle
  ↓
answer
  ↓
evaluate  (+ programmatic agents_md_coverage + schema_grounding)
```

**New modules:**
- `agent/resolve.py` — resolve phase
- `agent/schema_gate.py` — schema-aware SQL validator
- `agent/agents_md_parser.py` — AGENTS.MD section parser

**Modified modules:**
- `agent/prephase.py` — adds `schema_digest` and `agents_md_index` to `PrephaseResult`
- `agent/pipeline.py` — calls resolve, schema gate, carries over `confirmed_values`
- `agent/models.py` — new fields on `SqlPlanOutput`, `LearnOutput`, `PipelineEvalOutput`; new `ResolveOutput` / `ResolveCandidate`
- `data/prompts/learn.md` — requires `agents_md_anchor` field
- `data/prompts/sql_plan.md` — updated to require `agents_md_refs` field; references CONFIRMED VALUES block
- `data/prompts/resolve.md` — new prompt

---

## Item 1 — AGENTS.MD Indexing

**File:** `agent/agents_md_parser.py`

Parse AGENTS.MD into named sections using markdown headings (`## section_name`).

```python
def parse_agents_md(content: str) -> dict[str, list[str]]:
    """Returns {section_name: [lines]} for each ## section."""
```

Sections expected (non-exhaustive): `brand_aliases`, `kind_synonyms`, `folder_roles`, attribute fixed-value tables.

**In `_build_system()` for `sql_plan`/`learn`/`answer` phases:**  
Replace raw `agents_md_content` block with:
- Task-relevant sections: sections whose lines contain keywords from `task_text` (case-insensitive intersection)
- Plus: a compact key index listing all section names

**In `SqlPlanOutput`:**
```python
class SqlPlanOutput(BaseModel):
    reasoning: str
    queries: list[str]
    agents_md_refs: list[str] = []  # AGENTS.MD section keys used
```

If `agents_md_refs` is empty AND task_text contains terms found in `agents_md_index` → treat as plan failure, send to LEARN with error `"agents_md_refs empty despite known vocabulary terms in task"`.

---

## Item 2 — Schema Digest

**In `prephase.py`:** after `.schema` fetch, run additional SQL queries to build `schema_digest`:

```python
# 1. Column metadata per table
PRAGMA table_info(products);
PRAGMA table_info(product_properties);
PRAGMA table_info(inventory);
PRAGMA table_info(kinds);

# 2. FK relationships
PRAGMA foreign_key_list(product_properties);
PRAGMA foreign_key_list(inventory);

# 3. Top property keys with cardinalities
SELECT key, COUNT(*) AS cnt,
       SUM(CASE WHEN value_text IS NOT NULL THEN 1 ELSE 0 END) AS text_cnt,
       SUM(CASE WHEN value_number IS NOT NULL THEN 1 ELSE 0 END) AS num_cnt
FROM product_properties
GROUP BY key ORDER BY cnt DESC LIMIT 20;
```

Compiled into `schema_digest: dict`:
```python
{
  "tables": {
    "products": {"columns": [{"name": "sku", "type": "TEXT", "notnull": 1}, ...]},
    "product_properties": {"columns": [...], "fk": [{"from": "sku", "to": "products.sku"}]},
    ...
  },
  "value_type_map": {"diameter_mm": "number", "screw_type": "text", ...},  # derived from cardinalities
  "top_keys": ["diameter_mm", "screw_type", ...]
}
```

**In `PrephaseResult`** (`@dataclass`, requires `from dataclasses import field`):
```python
agents_md_index: dict = field(default_factory=dict)
schema_digest: dict = field(default_factory=dict)
```

In `_build_system()`: inject `# SCHEMA DIGEST` block (compact table, not raw DDL) + raw DDL retained for reference.

---

## Item 3 — Resolve Phase

**File:** `agent/resolve.py`

Called once in `run_pipeline()` before the cycle loop. Gracefully degradable: if it fails or returns empty candidates, pipeline continues without `CONFIRMED VALUES`.

### Models

```python
class ResolveCandidate(BaseModel):
    term: str            # raw term from task_text
    field: str           # "brand" | "model" | "kind" | "attr_key" | "attr_value"
    discovery_query: str # SQL: SELECT DISTINCT <col> FROM <table> WHERE <col> ILIKE '%<term>%' LIMIT 10
    confirmed_value: str | None = None  # filled after execution

class ResolveOutput(BaseModel):
    reasoning: str
    candidates: list[ResolveCandidate]
```

### Flow

```python
def run_resolve(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:  # confirmed_values: {field: confirmed_value}
```

1. Build resolve system prompt from `resolve.md` + AGENTS.MD index + schema top_keys
2. Call LLM → `ResolveOutput`
3. Security-check each `discovery_query` (read-only gate: no DDL, must have ILIKE or DISTINCT)
4. Execute each `discovery_query` via `/bin/sql`
5. Set `candidate.confirmed_value` from result (first row, first column)
6. Return `confirmed_values: dict[str, list[str]]` keyed by `candidate.field` (e.g. `{"brand": ["Heco"], "model": ["TopFix GTU-YPJ"]}`)

`confirmed_values` uses field name as key throughout the entire pipeline (resolve + carryover). Multiple confirmed values for the same field accumulate as a list.

### Prompt `data/prompts/resolve.md`

- Task: extract unique identifiers from task_text (brands, models, kinds, numeric attribute values with units)
- For each: generate one ILIKE discovery query
- Only discovery queries (SELECT DISTINCT ... ILIKE) — no filter queries
- Output JSON: `{"reasoning": "...", "candidates": [{"term": "...", "field": "...", "discovery_query": "SELECT DISTINCT ..."}]}`

### CONFIRMED VALUES block in `_build_system()`

```
# CONFIRMED VALUES
brand "Heco" → confirmed: "Heco"
model "TopFix GTU-YPJ" → confirmed: "TopFix GTU-YPJ"
kind "screw" → confirmed db values: ["wood screw", "self-tapping screw"]
```

Passed to every cycle in `sql_plan` and `learn` phases.

---

## Item 4 — Schema-Aware Gate

**File:** `agent/schema_gate.py`

Called in `run_pipeline()` after `check_sql_queries()`, before EXPLAIN loop.

```python
def check_schema_compliance(
    queries: list[str],
    schema_digest: dict,
    confirmed_values: dict,
    task_text: str,
) -> str | None:
```

### Checks

**1. Unknown column**  
Parse SQL for `table.col` references and bare `col` in WHERE/SELECT. Cross-reference against `schema_digest["tables"]`. Unknown column → return `"unknown column: {col} (not in schema)"`.

**2. Unverified literal**  
Collect string literals from WHERE clauses. For each literal that appears verbatim in `task_text` (i.e., potentially copied from user input) and is absent from `confirmed_values` → return `"unverified literal: '{val}' — run discovery first"`.

**3. Double-key product_properties JOIN**  
Regex: detect `JOIN product_properties \w+ .*WHERE.*\w+\.key\s*=.*AND.*\w+\.key\s*=` → return `"double-key JOIN on product_properties — use separate EXISTS subqueries"`.

All violations route to `_run_learn()` with the error string.

---

## Item 5 — AGENTS.MD Anchor in LEARN

**`LearnOutput` updated:**
```python
class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str
    agents_md_anchor: str | None = None  # e.g. "brand_aliases > Heco"
```

**`learn.md` updated:** require `agents_md_anchor` — which AGENTS.MD section/entry was violated or ignored. Set to `null` if failure is unrelated to AGENTS.MD.

**Deduplication logic in `_run_learn()`:**  
If `learn_out.agents_md_anchor` is set AND that anchor key is present in `pre.agents_md_index`:
- Do NOT append to `session_rules`
- Instead append to `highlighted_vault_rules: list[str]` (new field in pipeline state)
- In `_build_system()`, `highlighted_vault_rules` renders as:
  ```
  # HIGHLIGHTED VAULT RULE
  [anchor text from agents_md_index]
  ```
  This elevates priority of the existing AGENTS.MD entry without duplicating content.

---

## Item 6 — Confirmed Values Carryover

**In `run_pipeline()`:**

```python
confirmed_values: dict = {}
```

Lifecycle:
1. **After resolve:** `confirmed_values.update(run_resolve(...))`
2. **After successful EXECUTE:** `_extract_discovery_results(queries, sql_results, confirmed_values)` — scans executed DISTINCT queries, extracts returned values
3. **Each cycle start:** `_build_system()` receives current `confirmed_values`, renders `# CONFIRMED VALUES` block

```python
def _extract_discovery_results(
    queries: list[str],
    results: list[str],
    confirmed_values: dict,
) -> None:
    """Update confirmed_values in-place from DISTINCT query results."""
```

Heuristic: if query contains `SELECT DISTINCT <col>`, parse `col` as the field key and add result rows to `confirmed_values[col]` (list, same format as resolve output).

---

## Item 7 — Evaluator Metrics

**`PipelineEvalOutput` updated:**
```python
class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    prompt_optimization: list[str]
    rule_optimization: list[str]
    security_optimization: list[str] = []
    agents_md_coverage: float = 0.0  # NEW: 0..1
    schema_grounding: float = 0.0    # NEW: 0..1
```

**Computed programmatically before LLM evaluator call (in `_run_evaluator_safe()`):**

```python
def _compute_eval_metrics(
    task_text: str,
    agents_md_index: dict,
    executed_queries: list[str],
    schema_digest: dict,
    sql_plan_outputs: list[SqlPlanOutput],
) -> dict:
    """Returns {agents_md_coverage: float, schema_grounding: float}"""
```

- `agents_md_coverage`: `len(index_terms_in_task ∩ refs_used_in_plans) / max(1, len(index_terms_in_task))`
- `schema_grounding`: parse all executed queries for `table.col`, count fraction found in `schema_digest`

Passed to LLM evaluator as pre-computed facts in the user message; evaluator is not asked to compute them.

---

## Data Flow Summary

```
task_text
  → prephase: read AGENTS.MD → agents_md_index
                read .schema + digest queries → schema_digest
  → resolve: LLM(task + index + top_keys) → candidates
             SQL(discovery_queries) → confirmed_values
  → cycle N:
      _build_system(
        task-relevant agents_md_sections,
        schema_digest,
        confirmed_values,        ← grows each cycle
        highlighted_vault_rules, ← from LEARN dedup
        session_rules,
      ) → system_prompt
      LLM → SqlPlanOutput(queries, agents_md_refs)
      check_sql_queries()
      check_schema_compliance()  ← NEW gate
      EXPLAIN
      EXECUTE
      _extract_discovery_results() → confirmed_values update
      error → _run_learn() → LearnOutput(agents_md_anchor)
                           → session_rules OR highlighted_vault_rules
  → answer
  → _compute_eval_metrics() → agents_md_coverage, schema_grounding
  → LLM evaluator → PipelineEvalOutput
  → eval_log.jsonl
```

---

## Out of Scope

- Changes to `sql_security.py` beyond existing pattern matching
- Modifications to `answer.md` or grounding ref logic
- DSPy optimization pipeline
- Multi-task parallelism behavior

---

## Open Questions

None — all sections approved by user.
