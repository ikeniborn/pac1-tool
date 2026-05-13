# Schema Gate sqlglot + SKU Auto-refs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two systemic bugs — SCHEMA gate false-positives blocking LIKE-based discovery (Bug B) and empty grounding_refs due to missing SKU projection (Bug A).

**Architecture:** Three independent changes: (1) rewrite `schema_gate.py` with sqlglot AST traversal for alias-aware column validation and LIKE-context literal exemption; (2) add `_extract_sku_refs()` to `pipeline.py` that auto-populates grounding_refs from SKU column in SQL results; (3) fix contradictory rules and add LIKE mandate in `sql_plan.md`.

**Tech Stack:** Python 3.12, sqlglot>=25.0, pytest, uv

---

## File Map

| File | Action | Notes |
|---|---|---|
| `agent/schema_gate.py` | Full rewrite | ~47 → ~90 lines; sqlglot AST replaces regex |
| `tests/test_schema_gate.py` | Extend | New tests: LIKE exempt, alias resolution, updated error messages |
| `agent/pipeline.py` | Modify | Add `_extract_sku_refs()`, update `_build_answer_user_msg` |
| `data/prompts/sql_plan.md` | Modify | Remove contradiction, add LIKE rule, add SKU projection rule |

---

## Task 1: Rewrite `schema_gate.py` with sqlglot AST

**Files:**
- Modify: `agent/schema_gate.py`

The current regex-based implementation has two bugs: (a) `col.table in known_tables` would block `p.sku` where `p` is alias for `products`, not the table name; (b) LIKE context not detected, so `LIKE '%Festool%'` would still block on `'Festool'` substring. The rewrite fixes both.

- [ ] **Step 1: Write failing tests for alias resolution and LIKE exemption**

Add to `tests/test_schema_gate.py` (append after existing tests):

```python
def test_aliased_query_passes():
    """p.sku uses alias p → products, must not be blocked."""
    q = "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco") is None


def test_aliased_unknown_column_detected():
    """p.color uses alias p → products, color not in schema → blocked."""
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco")
    assert err is not None
    assert "unknown column" in err
    assert "color" in err


def test_like_literal_not_blocked():
    """'Festool' in LIKE context → discovery query → not blocked."""
    q = "SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'"
    err = check_schema_compliance([q], _DIGEST, {}, "find Festool products")
    assert err is None


def test_like_message_on_exact_literal():
    """Exact literal from task_text → error message mentions LIKE."""
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Festool'"
    err = check_schema_compliance([q], _DIGEST, {}, "find Festool products")
    assert err is not None
    assert "LIKE" in err
    assert "Festool" in err


def test_exists_subquery_aliases_pass():
    """pp.sku, pp.key, pp2.sku, pp2.key use aliases for product_properties → valid."""
    q = (
        "SELECT p.sku FROM products p "
        "WHERE EXISTS (SELECT 1 FROM product_properties pp WHERE pp.sku = p.sku AND pp.key = 'color') "
        "AND EXISTS (SELECT 1 FROM product_properties pp2 WHERE pp2.sku = p.sku AND pp2.key = 'weight')"
    )
    assert check_schema_compliance([q], _DIGEST, {"color": ["red"], "weight": ["1kg"]}, "find red 1kg") is None
```

- [ ] **Step 2: Run new tests to confirm key tests fail**

```bash
uv run pytest tests/test_schema_gate.py::test_aliased_query_passes tests/test_schema_gate.py::test_aliased_unknown_column_detected tests/test_schema_gate.py::test_like_literal_not_blocked tests/test_schema_gate.py::test_like_message_on_exact_literal tests/test_schema_gate.py::test_exists_subquery_aliases_pass -v
```

Expected: at least 2 FAILED — `test_like_literal_not_blocked` and `test_like_message_on_exact_literal` must fail (current impl has no LIKE-context exemption and uses "run discovery first" message, not "LIKE"). The alias tests (`test_aliased_query_passes`, `test_aliased_unknown_column_detected`, `test_exists_subquery_aliases_pass`) may already PASS with the current regex impl (it checks col name across all tables) — that is fine; they document correct behavior and will remain passing after the rewrite.

- [ ] **Step 3: Rewrite `agent/schema_gate.py`**

```python
"""Schema-aware SQL validator: unknown columns, unverified literals, double-key JOINs."""
from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp


def _build_alias_map(parsed: exp.Expression) -> dict[str, str]:
    """Return {alias_lower: table_name_lower} from FROM and JOIN clauses."""
    alias_map: dict[str, str] = {}
    for node in parsed.walk():
        if isinstance(node, exp.Table):
            table_name = node.name.lower() if node.name else ""
            alias = node.alias.lower() if node.alias else ""
            if table_name:
                alias_map[table_name] = table_name  # table refs itself
                if alias:
                    alias_map[alias] = table_name
    return alias_map


def _known_cols_by_table(schema_digest: dict) -> dict[str, set[str]]:
    """Return {table_name_lower: {col_name_lower, ...}}."""
    result: dict[str, set[str]] = {}
    for table, info in schema_digest.get("tables", {}).items():
        cols = {c["name"].lower() for c in info.get("columns", [])}
        result[table.lower()] = cols
    return result


def _check_query(
    q: str,
    schema_digest: dict,
    all_confirmed: set[str],
    task_text: str,
) -> str | None:
    try:
        parsed = sqlglot.parse_one(q, dialect="sqlite")
    except Exception:
        return None  # parse failure → let DB catch syntax errors

    alias_map = _build_alias_map(parsed)
    cols_by_table = _known_cols_by_table(schema_digest)

    # Check 1: unknown qualified column references
    if cols_by_table:
        for node in parsed.walk():
            if isinstance(node, exp.Column):
                table_ref = node.table.lower() if node.table else ""
                col_name = node.name.lower() if node.name else ""
                if not table_ref:
                    continue  # unqualified column — skip
                real_table = alias_map.get(table_ref, "")
                if not real_table:
                    continue  # unknown alias — skip (DB will catch)
                known = cols_by_table.get(real_table, set())
                if known and col_name not in known:
                    return f"unknown column: {table_ref}.{col_name} (not in schema)"

    # Check 2: unverified literal — context-aware LIKE exemption
    for node in parsed.walk():
        if isinstance(node, exp.Literal) and node.is_string:
            val = node.this
            if val not in task_text:
                continue
            if val in all_confirmed:
                continue
            # Skip if parent is LIKE/ILike — discovery query
            parent = node.parent
            if isinstance(parent, (exp.Like, exp.ILike)):
                continue
            return f"unverified literal: '{val}' — use LIKE '%{val}%' for discovery first"

    # Check 3: double-key JOIN on product_properties
    for node in parsed.walk():
        if not isinstance(node, exp.Join):
            continue
        join_table_node = node.find(exp.Table)
        if not join_table_node:
            continue
        join_alias = join_table_node.alias.lower() if join_table_node.alias else ""
        join_table = alias_map.get(join_alias, alias_map.get(join_table_node.name.lower() if join_table_node.name else "", ""))
        if join_table != "product_properties":
            continue
        # Count key= conditions in WHERE scope
        key_eqs = [
            n for n in parsed.walk()
            if isinstance(n, exp.EQ)
            and isinstance(n.left, exp.Column)
            and n.left.name.lower() == "key"
        ]
        if len(key_eqs) > 1:
            return "double-key JOIN on product_properties — use separate EXISTS subqueries"

    return None


def check_schema_compliance(
    queries: list[str],
    schema_digest: dict,
    confirmed_values: dict,
    task_text: str,
) -> str | None:
    """Check queries against schema. Returns first error string or None if all pass."""
    all_confirmed: set[str] = set()
    for vals in confirmed_values.values():
        if isinstance(vals, list):
            all_confirmed.update(str(v) for v in vals)
        else:
            all_confirmed.add(str(vals))

    for q in queries:
        err = _check_query(q, schema_digest, all_confirmed, task_text)
        if err:
            return err
    return None
```

- [ ] **Step 4: Run all schema_gate tests**

```bash
uv run pytest tests/test_schema_gate.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add agent/schema_gate.py tests/test_schema_gate.py
git commit -m "feat: rewrite schema_gate with sqlglot AST — alias resolution + LIKE exemption"
```

---

## Task 2: Add `_extract_sku_refs()` to `pipeline.py`

**Files:**
- Modify: `agent/pipeline.py`

After successful EXECUTE, extract SKU values from result CSV headers, build `/proc/catalog/{sku}.json` paths, append as AUTO_REFS to the ANSWER user message. This ensures ANSWER phase has explicit refs to include in `grounding_refs`.

- [ ] **Step 1: Write failing test**

Create `tests/test_pipeline_sku_refs.py`:

```python
from agent.pipeline import _extract_sku_refs, _build_answer_user_msg


def test_extract_sku_refs_single_result():
    queries = ["SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"]
    results = ["sku,brand\nHCO-AAA111,Heco\nHCO-BBB222,Heco\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == ["/proc/catalog/HCO-AAA111.json", "/proc/catalog/HCO-BBB222.json"]


def test_extract_sku_refs_no_sku_column():
    queries = ["SELECT p.brand FROM products p"]
    results = ["brand\nHeco\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == []


def test_extract_sku_refs_empty_result():
    queries = ["SELECT p.sku FROM products p WHERE p.brand = 'X'"]
    results = ["sku\n"]
    refs = _extract_sku_refs(queries, results)
    assert refs == []


def test_extract_sku_refs_multiple_queries():
    queries = [
        "SELECT DISTINCT brand FROM products WHERE brand LIKE '%Heco%'",
        "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'",
    ]
    results = [
        "brand\nHeco\n",
        "sku,brand\nHCO-AAA111,Heco\n",
    ]
    refs = _extract_sku_refs(queries, results)
    assert refs == ["/proc/catalog/HCO-AAA111.json"]


def test_build_answer_user_msg_with_refs():
    msg = _build_answer_user_msg("find Heco", ["sku,brand\nHCO-AAA111,Heco\n"], ["/proc/catalog/HCO-AAA111.json"])
    assert "AUTO_REFS" in msg
    assert "/proc/catalog/HCO-AAA111.json" in msg


def test_build_answer_user_msg_no_refs():
    msg = _build_answer_user_msg("find Heco", ["brand\nHeco\n"], [])
    assert "AUTO_REFS" not in msg
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
uv run pytest tests/test_pipeline_sku_refs.py -v
```

Expected: ALL FAIL (`_extract_sku_refs` not defined, `_build_answer_user_msg` signature mismatch)

- [ ] **Step 3: Add `_extract_sku_refs` and update `_build_answer_user_msg` in `pipeline.py`**

Add after `_extract_discovery_results` function (ends at line 283 in current file). Insert the new function at line 284:

```python
def _extract_sku_refs(queries: list[str], results: list[str]) -> list[str]:
    """Extract /proc/catalog/{sku}.json paths from SQL results that contain a sku column."""
    refs: list[str] = []
    for result_txt in results:
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        headers = [h.strip().lower() for h in lines[0].split(",")]
        if "sku" not in headers:
            continue
        sku_idx = headers.index("sku")
        for row in lines[1:]:
            cols = row.split(",")
            if sku_idx < len(cols):
                sku = cols[sku_idx].strip().strip('"')
                if sku:
                    refs.append(f"/proc/catalog/{sku}.json")
    return refs
```

Update `_build_answer_user_msg` signature and body:

```python
def _build_answer_user_msg(task_text: str, sql_results: list[str], auto_refs: list[str]) -> str:
    base = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    if not auto_refs:
        return base
    refs_block = "\n".join(auto_refs)
    return (
        base
        + f"\n\nAUTO_REFS (from sku column in SQL results — MUST be included in grounding_refs):\n{refs_block}"
    )
```

- [ ] **Step 4: Update call site in `run_pipeline`**

Three surgical edits (all in `agent/pipeline.py`).

**Edit 1** — add `sku_refs` accumulator at line ~302, alongside `sql_results` and `executed_queries`:

```python
    last_error = ""
    sql_results: list[str] = []
    executed_queries: list[str] = []
    sku_refs: list[str] = []          # ← add this line
    sql_plan_outputs: list[SqlPlanOutput] = []
```

**Edit 2** — inside the CARRYOVER block (lines 449–454), after `_extract_discovery_results`:

```python
        # ── CARRYOVER: update confirmed_values from DISTINCT results ──────────
        executed_queries.extend(queries)
        _extract_discovery_results(queries, sql_results, confirmed_values)
        sku_refs.extend(_extract_sku_refs(queries, sql_results))  # accumulate across cycles

        success = True
        break
```

**Edit 3** — in the ANSWER block (line 469), update `_build_answer_user_msg` call only; leave the `_call_llm_phase` call below unchanged:

```python
        # ── ANSWER ────────────────────────────────────────────────────────────
        answer_user = _build_answer_user_msg(task_text, sql_results, sku_refs)
        answer_out, sgr_answer, tok = _call_llm_phase(
            static_answer, answer_user, model, cfg, AnswerOutput,
            phase="answer", cycle=cycle + 1,
        )
```

- [ ] **Step 5: Run new tests**

```bash
uv run pytest tests/test_pipeline_sku_refs.py -v
```

Expected: ALL PASS

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline_sku_refs.py
git commit -m "feat: auto-extract SKU grounding_refs from SQL results in pipeline"
```

---

## Task 3: Fix `data/prompts/sql_plan.md`

**Files:**
- Modify: `data/prompts/sql_plan.md`

Three targeted edits: (1) remove the "Final query obligation" section that contradicts "Discovery Query Isolation"; (2) add explicit LIKE rule for discovery queries; (3) add SKU projection mandate for final queries.

- [ ] **Step 1: Remove "Final query obligation" section**

Remove lines 38–41 entirely (the section header and body):

```
## Final query obligation

If your plan includes discovery queries (`SELECT DISTINCT model`, `SELECT DISTINCT key`), you MUST also include the final verification query as the last query in the same plan. A plan consisting only of discovery queries is incomplete. The pipeline has a limited cycle budget — every plan must advance toward a definitive answer.
```

- [ ] **Step 2: Add LIKE rule for discovery queries**

In the "## String Literals in WHERE Clauses" section, append after the existing rules:

```markdown
Discovery queries MUST use LIKE with wildcards on both sides — never exact match on unverified value:

```sql
-- CORRECT: use LIKE for discovery
SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'

-- WRONG: SCHEMA gate will block this if 'Festool' is not yet confirmed
WHERE brand = 'Festool'
```

The SCHEMA gate explicitly allows literals inside LIKE — it blocks them in `=` context when unconfirmed.
```

- [ ] **Step 3: Add SKU projection rule**

Append a new section after "## String Literals in WHERE Clauses":

```markdown
## SKU Projection in Final Query (REQUIRED)

The final query in any plan claiming product existence MUST include `p.sku` in SELECT:

```sql
-- REQUIRED: sku in SELECT so ANSWER phase can construct grounding_refs
SELECT p.sku, p.brand, p.model FROM products p WHERE ...
```

Without `p.sku`, the ANSWER phase cannot build `/proc/catalog/{sku}.json` paths.
```

- [ ] **Step 4: Verify the file reads coherently**

```bash
uv run python -c "
from agent.pipeline import _build_static_system
from agent.rules_loader import RulesLoader, _RULES_DIR
from agent.prompt import load_prompt
print(load_prompt('sql_plan')[:500])
"
```

Expected: output shows the updated prompt text without "Final query obligation" section.

- [ ] **Step 5: Commit**

```bash
git add data/prompts/sql_plan.md
git commit -m "fix: sql_plan.md — remove contradiction, add LIKE discovery rule, mandate sku projection"
```

---

## Task 4: Integration Smoke Test

**Files:** None changed — verify fixes work end-to-end.

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: ALL PASS

- [ ] **Step 2: Confirm sqlglot installed**

```bash
uv run python -c "import sqlglot; print(sqlglot.__version__)"
```

Expected: version string printed (no ImportError)

- [ ] **Step 3: Smoke test schema gate on LIKE query**

```bash
uv run python -c "
from agent.schema_gate import check_schema_compliance
digest = {'tables': {'products': {'columns': [{'name': 'sku'}, {'name': 'brand'}]}}}
q = \"SELECT DISTINCT brand FROM products WHERE brand LIKE '%Festool%'\"
err = check_schema_compliance([q], digest, {}, 'find Festool products')
print('LIKE blocked (BUG):', err) if err else print('LIKE allowed (OK)')
"
```

Expected: `LIKE allowed (OK)`

- [ ] **Step 4: Smoke test schema gate on alias query**

```bash
uv run python -c "
from agent.schema_gate import check_schema_compliance
digest = {'tables': {'products': {'columns': [{'name': 'sku'}, {'name': 'brand'}, {'name': 'model'}]}}}
q = \"SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'\"
err = check_schema_compliance([q], digest, {'brand': ['Heco']}, 'find Heco')
print('Alias blocked (BUG):', err) if err else print('Alias allowed (OK)')
"
```

Expected: `Alias allowed (OK)`

- [ ] **Step 5: Smoke test SKU ref extraction**

```bash
uv run python -c "
from agent.pipeline import _extract_sku_refs
result = 'sku,brand\nFST-2JPIIG2S,Festool\nFST-XYZABC1,Festool\n'
refs = _extract_sku_refs(['SELECT p.sku FROM products p'], [result])
print(refs)
"
```

Expected: `['/proc/catalog/FST-2JPIIG2S.json', '/proc/catalog/FST-XYZABC1.json']`

---

## Self-Review Notes

**Spec coverage:**
- §1 schema_gate sqlglot rewrite → Task 1 ✓
- §2 pipeline auto-extract SKU refs → Task 2 ✓ (accumulate inside cycle loop per spec)
- §3 sql_plan.md three fixes → Task 3 ✓
- Open question (stores path) → deferred; `_extract_sku_refs` only handles `sku` column, stores rely on prompt rules ✓

**Alias tests pre-pass:** `test_aliased_query_passes`, `test_aliased_unknown_column_detected`, `test_exists_subquery_aliases_pass` may pass with old regex impl (it checks col name across all tables, not per-table). They remain valid tests — they verify correct behavior that the new impl preserves.

**Double-key JOIN check robustness:** walks whole parsed AST for `key=` EQ nodes (not scoped to JOIN's ON clause). Works correctly for existing tests because product_properties is the only table with a `key` column. EXISTS subqueries don't generate `exp.Join` nodes → `test_separate_exists_passes` is not affected.
