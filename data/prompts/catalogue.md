
## Table name resolution

Do not hardcode table names. Consult the **SCHEMA DIGEST** block (provided above): every table is tagged with a semantic role — `role=products`, `role=kinds`, `role=properties`, or `role=other`. Substitute the actual digest name for the role placeholder when emitting queries.

## CATALOGUE STRATEGY

**HARD RULE**: Never use `list`, `find`, or `read` on `/proc/catalog/`. SQL ONLY via `/bin/sql`.

**Step order** (MAX_STEPS=5 — every step counts):
1. Check AGENTS.MD — if it defines exact values for the needed attribute, use them directly in SQL
2. If AGENTS.MD is silent on an attribute → `SELECT DISTINCT <attr> FROM <table with role=products> WHERE <narrowing conditions> LIMIT 50`
3. `EXPLAIN SELECT ...` — validate syntax before execution (catches typos at zero cost)
4. `SELECT ...` — retrieve the answer
5. `report_completion` immediately — do NOT read catalog files to confirm SQL results

**Question patterns**:
- `How many X?` → `SELECT COUNT(*) FROM <table with role=products> WHERE type='X'`
- `Do you have X?` → `SELECT 1 FROM <table with role=products> WHERE brand=? AND type=? LIMIT 1`

**Never assume attribute values** — verify from AGENTS.MD or DISTINCT first.

**SQL column mapping**: products table has separate columns: `brand`, `series`, `model`, `name`.
When the task mentions a product line name (e.g. "Rugged 3EY-11K"), search in `model` column, not `series`.

**NOT FOUND rule**: After 2 failed SQL attempts returning no rows, try one final broad query.
If still no match → `report_completion` with `<NO> Product not found in catalogue` and `grounding_refs=[]`.

**grounding_refs is MANDATORY** — include every file that contributed to the answer.
For catalogue items: grounding_refs must be `/proc/catalog/{sku}.json` using the SKU from SQL results.
Example: SQL returns `sku=PNT-2SB09GHC` → grounding_refs=["/proc/catalog/PNT-2SB09GHC.json"]
NEVER use the `path` column from SQL — always construct the path as `/proc/catalog/{sku}.json`.

When answering yes/no questions, include <YES> or <NO> in your response message.