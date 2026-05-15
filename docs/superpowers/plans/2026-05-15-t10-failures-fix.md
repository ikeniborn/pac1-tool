---
review:
  plan_hash: d9119ef63418acd0
  spec_hash: 4a3bf54ce37bee6c
  last_run: 2026-05-15
  phases:
    structure:     { status: passed }
    coverage:      { status: passed }
    dependencies:  { status: passed }
    verifiability: { status: passed }
    consistency:   { status: passed }
  findings:
    - id: F-001
      severity: WARNING
      phase: coverage
      section: "Task 11/12 + File Touch Map"
      text: "Plan modifies data/prompts/catalogue.md, but spec File Touch List (sec 2 + final table) lists only resolve.md, lookup.md, sql_plan.md, test_gen.md. Catalogue extension is consistent with defect #2 directive (remove hardcoded table names) but exceeds spec scope. Either add catalogue.md to spec touch list or drop from plan."
      verdict: fixed
      resolution: "Spec touch list extended to include data/prompts/catalogue.md (sec 2 + File Touch List table). spec_hash bumped to 4a3bf54ce37bee6c."
---

# t10 Pipeline Failures Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five interlinked defects that caused task `t10` to loop 9 cycles without producing an `ANSWER`, so a replay converges in ≤ 3 cycles with `<COUNT:3>`.

**Architecture:** Add semantic role tags to schema digest, refresh digest in-place after `sqlite_schema` discovery queries, drop hardcoded table names from prompts in favour of role hints, harden the schema gate with an unknown-table check plus a system-table exemption, and add a runtime guard against the `len(rows) > 1` antipattern on aggregate queries.

**Tech Stack:** Python 3, sqlglot, pytest, existing agent/* modules.

**Spec:** `docs/superpowers/specs/2026-05-15-t10-failures-design.md`

**Implementation note (deviation from spec § 2):** Spec lists `agent/prompt.py:build_system_prompt` as the injection point for SCHEMA DIGEST in the resolve phase. The actual builder for resolve's system prompt is `agent/resolve.py:_build_resolve_system` — `_build_static_system` in `pipeline.py` is only used for `sql_plan`/`learn`/`answer`. Plan modifies `resolve.py` directly. Schema-digest formatting is reused via the existing `_format_schema_digest` helper in `pipeline.py` (exported for resolve).

---

## File Touch Map

| File | Action |
|------|--------|
| `agent/prephase.py` | Add role tagging in `_build_schema_digest`; add `merge_schema_from_sqlite_results` |
| `agent/schema_gate.py` | Add Check 0 (unknown table); add system-table exemption in Check 2 |
| `agent/test_runner.py` | Add `_AGG_RE`/`_BAD_LEN_RE`; extend `_check_tdd_antipatterns`; add `sql_queries` arg to `run_tests` |
| `agent/pipeline.py` | Expose `_format_schema_digest`; pass `sql_queries` to `run_tests`; post-execute schema-refresh hook |
| `agent/resolve.py` | Inject SCHEMA DIGEST block in `_build_resolve_system` |
| `agent/trace.py` | New `log_schema_refresh` method |
| `data/prompts/test_gen.md` | Rewrite aggregate output example; ban aggregate `len > 1` in anti-patterns |
| `data/prompts/resolve.md` | Replace hardcoded `kinds`/`products` table names with role directives |
| `data/prompts/lookup.md` | Same |
| `data/prompts/sql_plan.md` | Same |
| `data/prompts/catalogue.md` | Same |
| `tests/test_prephase.py` | Role-tag tests; merge tests |
| `tests/test_schema_gate.py` | Unknown-table + system-table-exemption tests |
| `tests/test_test_runner.py` | Aggregate-antipattern force-fail tests |
| `tests/test_pipeline.py` | Schema-refresh-after-sqlite-query test |

---

## Task 1: Schema digest semantic roles

**Files:**
- Modify: `agent/prephase.py` (function `_build_schema_digest`, ~lines 54-91)
- Test: `tests/test_prephase.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_prephase.py`:

```python
def test_build_schema_digest_assigns_role_products():
    from agent.prephase import _infer_role
    cols = [{"name": "sku", "type": "TEXT"}, {"name": "kind_id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}]
    assert _infer_role(cols) == "products"


def test_build_schema_digest_assigns_role_kinds():
    from agent.prephase import _infer_role
    cols = [{"name": "id", "type": "INTEGER"}, {"name": "category_id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}]
    assert _infer_role(cols) == "kinds"


def test_build_schema_digest_assigns_role_properties():
    from agent.prephase import _infer_role
    cols = [{"name": "sku", "type": "TEXT"}, {"name": "key", "type": "TEXT"}, {"name": "value_text", "type": "TEXT"}]
    assert _infer_role(cols) == "properties"


def test_build_schema_digest_assigns_role_other():
    from agent.prephase import _infer_role
    cols = [{"name": "id", "type": "INTEGER"}, {"name": "label", "type": "TEXT"}]
    assert _infer_role(cols) == "other"
```

- [ ] **Step 2: Run tests, verify failure**

Run: `uv run pytest tests/test_prephase.py::test_build_schema_digest_assigns_role_products -v`
Expected: FAIL — `_infer_role` not defined.

- [ ] **Step 3: Implement `_infer_role` and integrate**

In `agent/prephase.py`, after the `_parse_csv_rows` helper add:

```python
def _infer_role(cols: list[dict]) -> str:
    names = {c["name"].lower() for c in cols if "name" in c}
    if {"sku", "kind_id"}.issubset(names):
        return "products"
    if {"key", "value_text"}.issubset(names):
        return "properties"
    if {"category_id", "name"}.issubset(names) and "sku" not in names:
        return "kinds"
    return "other"
```

Then in `_build_schema_digest`, replace the `entry: dict = {"columns": cols}` line with:

```python
        entry: dict = {"columns": cols, "role": _infer_role(cols)}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_prephase.py -v -k role`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "feat(prephase): tag schema digest tables with semantic role"
```

---

## Task 2: `_format_schema_digest` exposes role; helper exported for resolve

**Files:**
- Modify: `agent/pipeline.py` (function `_format_schema_digest`)
- Test: `tests/test_prephase.py`

- [ ] **Step 1: Locate current formatter**

Run: `grep -n "_format_schema_digest" agent/pipeline.py`
Expected output: definition line plus call sites at ~237.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_prephase.py`:

```python
def test_format_schema_digest_includes_role():
    from agent.pipeline import _format_schema_digest
    digest = {
        "tables": {
            "product_kinds": {
                "columns": [{"name": "id", "type": "INTEGER"}, {"name": "category_id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}],
                "role": "kinds",
            }
        },
        "top_keys": [],
        "value_type_map": {},
    }
    out = _format_schema_digest(digest)
    assert "product_kinds" in out
    assert "role=kinds" in out
```

- [ ] **Step 3: Run test, verify failure**

Run: `uv run pytest tests/test_prephase.py::test_format_schema_digest_includes_role -v`
Expected: FAIL — `role=kinds` not in output.

- [ ] **Step 4: Update formatter**

Open `agent/pipeline.py`, find the `_format_schema_digest` function. Inside the per-table loop where the table header is composed, append `role` when present. Example patch (adapt to actual current code — locate the line that emits the table header like `f"{table}: ..."`):

```python
        role = info.get("role")
        suffix = f" [role={role}]" if role and role != "other" else ""
        # ... where the original header was: f"{table}:"
        # change to:
        header = f"{table}{suffix}:"
```

If the existing function builds output differently (e.g. multi-line block per table), append `[role=<value>]` to the first header line only.

- [ ] **Step 5: Run test, verify pass**

Run: `uv run pytest tests/test_prephase.py::test_format_schema_digest_includes_role -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_prephase.py
git commit -m "feat(pipeline): expose role tag in SCHEMA DIGEST format"
```

---

## Task 3: Inject SCHEMA DIGEST in resolve phase

**Files:**
- Modify: `agent/resolve.py` (function `_build_resolve_system`, lines 60-71)
- Test: `tests/test_resolve.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resolve.py`:

```python
def test_resolve_system_includes_schema_digest():
    from agent.resolve import _build_resolve_system
    from agent.prephase import PrephaseResult
    pre = PrephaseResult(
        agents_md_index={"PRODUCTS": ["intro"]},
        schema_digest={
            "tables": {
                "product_kinds": {
                    "columns": [{"name": "id", "type": "INTEGER"}, {"name": "category_id", "type": "INTEGER"}, {"name": "name", "type": "TEXT"}],
                    "role": "kinds",
                }
            },
            "top_keys": ["voltage"],
            "value_type_map": {"voltage": "text"},
        },
    )
    system = _build_resolve_system(pre)
    assert "SCHEMA DIGEST" in system
    assert "product_kinds" in system
    assert "role=kinds" in system
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest tests/test_resolve.py::test_resolve_system_includes_schema_digest -v`
Expected: FAIL — `SCHEMA DIGEST` missing.

- [ ] **Step 3: Add digest block**

Edit `agent/resolve.py`. Add import near the top:

```python
from .pipeline import _format_schema_digest
```

Update `_build_resolve_system`:

```python
def _build_resolve_system(pre: PrephaseResult) -> str:
    parts: list[str] = []
    if pre.agents_md_index:
        index_lines = "\n".join(f"- {k}" for k in pre.agents_md_index)
        parts.append(f"# AGENTS.MD INDEX\n{index_lines}")
    if pre.schema_digest and pre.schema_digest.get("tables"):
        parts.append(f"# SCHEMA DIGEST\n{_format_schema_digest(pre.schema_digest)}")
    top_keys = pre.schema_digest.get("top_keys", [])
    if top_keys:
        parts.append("# TOP PROPERTY KEYS\n" + "\n".join(f"- {k}" for k in top_keys))
    guide = load_prompt("resolve")
    if guide:
        parts.append(guide)
    return "\n\n".join(parts)
```

If a circular import surfaces (`resolve` → `pipeline` → `resolve`), move `_format_schema_digest` into `prephase.py` and import from there in both `resolve.py` and `pipeline.py`. Verify via:

```bash
uv run python -c "import agent.resolve; import agent.pipeline"
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest tests/test_resolve.py::test_resolve_system_includes_schema_digest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/resolve.py tests/test_resolve.py
git commit -m "feat(resolve): include SCHEMA DIGEST block in resolve system prompt"
```

---

## Task 4: Schema gate Check 0 — unknown table

**Files:**
- Modify: `agent/schema_gate.py`
- Test: `tests/test_schema_gate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_gate.py`:

```python
def test_unknown_table_rejected():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(["SELECT * FROM nonexistent_table"], digest, {}, "")
    assert err is not None
    assert "unknown table" in err.lower()
    assert "nonexistent_table" in err


def test_known_table_passes_check_0():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(["SELECT sku FROM products"], digest, {}, "")
    assert err is None


def test_empty_digest_skips_check_0():
    from agent.schema_gate import check_schema_compliance
    err = check_schema_compliance(["SELECT * FROM whatever"], {}, {}, "")
    assert err is None or "unknown table" not in err.lower()


def test_sqlite_schema_passes_check_0():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(
        ["SELECT name FROM sqlite_schema WHERE type='table'"],
        digest, {}, "",
    )
    assert err is None or "unknown table" not in err.lower()
```

- [ ] **Step 2: Run tests, verify failure**

Run: `uv run pytest tests/test_schema_gate.py -v -k "unknown_table or check_0 or sqlite_schema_passes"`
Expected: at least `test_unknown_table_rejected` FAIL.

- [ ] **Step 3: Implement Check 0**

Edit `agent/schema_gate.py`. Add module-level constant near the top:

```python
SYSTEM_TABLES = {"sqlite_schema", "sqlite_master"}
```

In `_check_query`, immediately after `alias_map = _build_alias_map(parsed)` add Check 0 before Check 1:

```python
    # Check 0: unknown table (requires non-empty digest)
    known_tables = set(schema_digest.get("tables", {}).keys())
    if known_tables:
        known_lower = {t.lower() for t in known_tables} | SYSTEM_TABLES
        for node in parsed.walk():
            if isinstance(node, exp.Table):
                name = (node.name or "").lower()
                if not name:
                    continue
                if name in known_lower:
                    continue
                if name.startswith("pragma_"):
                    continue
                return f"unknown table: '{name}' (not in schema digest)"
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_schema_gate.py -v`
Expected: all green (new tests pass, existing tests still pass).

- [ ] **Step 5: Commit**

```bash
git add agent/schema_gate.py tests/test_schema_gate.py
git commit -m "feat(schema_gate): reject queries that reference unknown tables (Check 0)"
```

---

## Task 5: Schema gate Check 2 — system-table exemption

**Files:**
- Modify: `agent/schema_gate.py` (Check 2 block in `_check_query`)
- Test: `tests/test_schema_gate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema_gate.py`:

```python
def test_sqlite_schema_exempt_from_literal_check():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(
        ["SELECT name FROM sqlite_schema WHERE name IN ('products', 'kinds')"],
        digest, {}, "products kinds",
    )
    assert err is None


def test_sqlite_master_exempt_from_literal_check():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(
        ["SELECT sql FROM sqlite_master WHERE name = 'products'"],
        digest, {}, "products",
    )
    assert err is None


def test_pragma_table_info_exempt():
    from agent.schema_gate import check_schema_compliance
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    err = check_schema_compliance(
        ["SELECT * FROM pragma_table_info('products')"],
        digest, {}, "products",
    )
    assert err is None or "unverified literal" not in err.lower()
```

- [ ] **Step 2: Run tests, verify failure**

Run: `uv run pytest tests/test_schema_gate.py -v -k "exempt"`
Expected: at least one FAIL on the literal-check exemption.

- [ ] **Step 3: Add exemption**

Edit `agent/schema_gate.py` `_check_query`. Just before the `# Check 2: unverified literal` loop, add:

```python
    # System-table exemption: literals in sqlite_schema/sqlite_master/pragma_* queries
    # are table-name identifiers (DDL discovery), not data values.
    referenced_tables = {
        (node.name or "").lower()
        for node in parsed.walk()
        if isinstance(node, exp.Table)
    }
    if any(t in SYSTEM_TABLES or t.startswith("pragma_") for t in referenced_tables):
        return None  # skip remaining literal/JOIN checks for system-table queries
```

Note: `return None` short-circuits Check 2 *and* Check 3, which is the desired behaviour (DDL discovery does not touch `product_properties`).

- [ ] **Step 4: Run all schema_gate tests**

Run: `uv run pytest tests/test_schema_gate.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add agent/schema_gate.py tests/test_schema_gate.py
git commit -m "feat(schema_gate): exempt sqlite_schema/sqlite_master/pragma_* from literal check"
```

---

## Task 6: TDD runtime guard — aggregate `len > 1` antipattern

**Files:**
- Modify: `agent/test_runner.py`
- Test: `tests/test_test_runner.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_test_runner.py`:

```python
def test_aggregate_antipattern_force_fail():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert len(rows) > 1\n"
    )
    sql_queries = ["SELECT COUNT(*) FROM products WHERE kind_id = 7"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["count\n3"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is False
    assert "antipattern" in err.lower()
    assert any("antipattern" in w.lower() for w in warns)


def test_non_aggregate_len_check_allowed():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert len(rows) > 1\n"
    )
    sql_queries = ["SELECT sku FROM products WHERE kind_id = 7"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["sku\nA1\nA2"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is True
    assert not any("antipattern" in w.lower() for w in warns)


def test_aggregate_without_bad_len_passes():
    from agent.test_runner import run_tests
    code = (
        "def test_sql(results):\n"
        "    rows = results[-1].split('\\n')\n"
        "    assert int(rows[-1].strip()) >= 0\n"
    )
    sql_queries = ["SELECT COUNT(*) FROM products"]
    passed, err, warns = run_tests(
        code, "test_sql", {"results": ["count\n3"]},
        task_text="", sql_queries=sql_queries,
    )
    assert passed is True
```

- [ ] **Step 2: Run tests, verify failure**

Run: `uv run pytest tests/test_test_runner.py -v -k "aggregate or non_aggregate"`
Expected: FAIL — `run_tests` does not accept `sql_queries`.

- [ ] **Step 3: Extend `_check_tdd_antipatterns` and `run_tests` signature**

Edit `agent/test_runner.py`. Add regexes near other regex constants:

```python
_AGG_RE = re.compile(r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(", re.IGNORECASE)
_BAD_LEN_RE = re.compile(r"len\s*\(\s*(?:rows|results)\s*\)\s*>\s*1")
```

Update `_check_tdd_antipatterns`:

```python
def _check_tdd_antipatterns(
    test_code: str,
    task_text: str = "",
    sql_queries: list[str] | None = None,
) -> list[str]:
    warnings = []
    if task_text:
        for lit in _ANSWER_ASSERT_RE.findall(test_code):
            if lit in task_text:
                warnings.append(f"hardcoded task literal in answer assert: '{lit}'")
    for col in _HEADER_ASSERT_RE.findall(test_code):
        warnings.append(
            f"hardcoded string in sql header assert: '{col}' — "
            "for aggregates use row/type check; for named columns this warning may be a false-positive"
        )
    if sql_queries and _BAD_LEN_RE.search(test_code):
        if any(_AGG_RE.search(q) for q in sql_queries):
            warnings.append(
                "aggregate query + len > 1 antipattern — use rows == 1 + integer parse"
            )
    return warnings
```

Update `run_tests`:

```python
def run_tests(
    test_code: str,
    fn_name: str,
    context: dict,
    task_text: str = "",
    sql_queries: list[str] | None = None,
) -> tuple[bool, str, list[str]]:
    """Run test_code in isolated subprocess. Returns (passed, error_message, warnings)."""
    warnings = _check_tdd_antipatterns(test_code, task_text, sql_queries)
    for w in warnings:
        if "antipattern" in w.lower():
            return False, w, warnings
    # ... unchanged subprocess block follows
```

Insert the early-return block immediately after the `warnings = ...` line, before the existing `script = (...)` assignment.

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_test_runner.py -v`
Expected: all green (existing tests untouched — they don't pass `sql_queries`).

- [ ] **Step 5: Commit**

```bash
git add agent/test_runner.py tests/test_test_runner.py
git commit -m "feat(test_runner): force-fail aggregate-query + len(rows)>1 antipattern"
```

---

## Task 7: Pipeline passes `sql_queries` to `run_tests`

**Files:**
- Modify: `agent/pipeline.py` (the `run_tests` callsite around line 634)

- [ ] **Step 1: Locate callsite**

Run: `grep -n "run_tests(" agent/pipeline.py`
Expected: one or two callsites around lines 634 and an `answer_tests` site further down.

- [ ] **Step 2: Update the sql_tests callsite**

In `agent/pipeline.py`, find:

```python
                if _TDD_ENABLED and test_gen_out:
                    sql_passed, sql_err, sql_warns = run_tests(
                        test_gen_out.sql_tests, "test_sql", {"results": sql_results},
                        task_text=task_text,
                    )
```

Replace with:

```python
                if _TDD_ENABLED and test_gen_out:
                    sql_passed, sql_err, sql_warns = run_tests(
                        test_gen_out.sql_tests, "test_sql", {"results": sql_results},
                        task_text=task_text,
                        sql_queries=queries,
                    )
```

Leave the `answer_tests` callsite unchanged (no aggregate-result check there).

- [ ] **Step 3: Run pipeline TDD tests**

Run: `uv run pytest tests/test_pipeline_tdd.py -v`
Expected: PASS (no behaviour change for non-aggregate cases).

- [ ] **Step 4: Commit**

```bash
git add agent/pipeline.py
git commit -m "feat(pipeline): pass sql_queries to run_tests for antipattern detection"
```

---

## Task 8: `merge_schema_from_sqlite_results` helper

**Files:**
- Modify: `agent/prephase.py`
- Test: `tests/test_prephase.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prephase.py`:

```python
def test_merge_schema_from_create_table():
    from agent.prephase import merge_schema_from_sqlite_results
    digest = {"tables": {}, "top_keys": [], "value_type_map": {}}
    csv_text = (
        "name,sql\n"
        '"product_kinds","CREATE TABLE product_kinds (id INTEGER PRIMARY KEY, category_id INTEGER, name TEXT)"\n'
    )
    added = merge_schema_from_sqlite_results(digest, [csv_text])
    assert "product_kinds" in added
    assert "product_kinds" in digest["tables"]
    cols = {c["name"] for c in digest["tables"]["product_kinds"]["columns"]}
    assert {"id", "category_id", "name"}.issubset(cols)
    assert digest["tables"]["product_kinds"]["role"] == "kinds"


def test_merge_idempotent():
    from agent.prephase import merge_schema_from_sqlite_results
    digest = {"tables": {}, "top_keys": [], "value_type_map": {}}
    csv_text = (
        "name,sql\n"
        '"product_kinds","CREATE TABLE product_kinds (id INTEGER, category_id INTEGER, name TEXT)"\n'
    )
    merge_schema_from_sqlite_results(digest, [csv_text])
    added2 = merge_schema_from_sqlite_results(digest, [csv_text])
    assert added2 == []
    assert len(digest["tables"]["product_kinds"]["columns"]) == 3


def test_merge_skips_unparseable_sql():
    from agent.prephase import merge_schema_from_sqlite_results
    digest = {"tables": {}, "top_keys": [], "value_type_map": {}}
    csv_text = "name,sql\n\"weird\",\"NOT A VALID CREATE STATEMENT\"\n"
    added = merge_schema_from_sqlite_results(digest, [csv_text])
    assert added == []
    assert "weird" not in digest["tables"]


def test_merge_ignores_non_create_rows():
    from agent.prephase import merge_schema_from_sqlite_results
    digest = {"tables": {}, "top_keys": [], "value_type_map": {}}
    csv_text = (
        "name,sql\n"
        '"idx_x","CREATE INDEX idx_x ON products(sku)"\n'
    )
    added = merge_schema_from_sqlite_results(digest, [csv_text])
    assert added == []
```

- [ ] **Step 2: Run tests, verify failure**

Run: `uv run pytest tests/test_prephase.py -v -k merge`
Expected: FAIL — function missing.

- [ ] **Step 3: Implement the helper**

Add to `agent/prephase.py` (after `_build_schema_digest`):

```python
import sqlglot
import sqlglot.expressions as _sg_exp


def merge_schema_from_sqlite_results(
    schema_digest: dict, csv_results: list[str]
) -> list[str]:
    """Merge CREATE TABLE rows from sqlite_schema CSV output into schema_digest.

    Returns list of newly added table names. Mutates schema_digest in place.
    Parse failures on individual rows are skipped silently.
    """
    added: list[str] = []
    tables = schema_digest.setdefault("tables", {})
    for csv_text in csv_results:
        rows = _parse_csv_rows(csv_text)
        for row in rows:
            sql = (row.get("sql") or "").strip()
            if not sql.upper().startswith("CREATE TABLE"):
                continue
            try:
                parsed = sqlglot.parse_one(sql, dialect="sqlite")
            except Exception:
                continue
            table_node = parsed.find(_sg_exp.Table)
            if table_node is None or not table_node.name:
                continue
            table_name = table_node.name
            if table_name in tables:
                continue
            cols: list[dict] = []
            for col_def in parsed.find_all(_sg_exp.ColumnDef):
                col_name = col_def.name
                col_type_node = col_def.args.get("kind")
                col_type = col_type_node.sql(dialect="sqlite") if col_type_node else ""
                if col_name:
                    cols.append({"name": col_name, "type": col_type})
            if not cols:
                continue
            tables[table_name] = {"columns": cols, "role": _infer_role(cols)}
            added.append(table_name)
    return added
```

(Move the `import sqlglot` lines to the top of the file with the other imports for cleanliness.)

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_prephase.py -v -k merge`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "feat(prephase): add merge_schema_from_sqlite_results for in-cycle schema refresh"
```

---

## Task 9: Trace event `schema_refresh`

**Files:**
- Modify: `agent/trace.py`
- Test: `tests/test_trace.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_trace.py`:

```python
def test_log_schema_refresh(tmp_path):
    from agent.trace import TraceLogger
    import json
    p = tmp_path / "trace.jsonl"
    t = TraceLogger(p, "task_x")
    t.log_schema_refresh(cycle=2, added_tables=["product_kinds", "carts"])
    t._fh.flush()
    lines = [json.loads(ln) for ln in p.read_text().splitlines() if ln]
    refresh = [ln for ln in lines if ln.get("type") == "schema_refresh"]
    assert len(refresh) == 1
    assert refresh[0]["cycle"] == 2
    assert refresh[0]["added_tables"] == ["product_kinds", "carts"]
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest tests/test_trace.py::test_log_schema_refresh -v`
Expected: FAIL — method missing.

- [ ] **Step 3: Implement the method**

In `agent/trace.py` inside `class TraceLogger`, add:

```python
    def log_schema_refresh(self, cycle: int, added_tables: list[str]) -> None:
        self._write({
            "type": "schema_refresh",
            "cycle": cycle,
            "added_tables": list(added_tables),
        })
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest tests/test_trace.py::test_log_schema_refresh -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/trace.py tests/test_trace.py
git commit -m "feat(trace): add schema_refresh event"
```

---

## Task 10: Pipeline post-execute schema refresh hook

**Files:**
- Modify: `agent/pipeline.py` (post-execute block, around lines 590-606)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pipeline.py`:

```python
def test_pipeline_refreshes_schema_after_sqlite_query():
    """After executing a sqlite_schema CREATE TABLE discovery, the digest gains the new table."""
    from agent.prephase import merge_schema_from_sqlite_results

    digest = {"tables": {}, "top_keys": [], "value_type_map": {}}
    csv_text = (
        "name,sql\n"
        '"product_kinds","CREATE TABLE product_kinds (id INTEGER, category_id INTEGER, name TEXT)"\n'
    )
    queries = ["SELECT name, sql FROM sqlite_schema WHERE type='table'"]
    results = [csv_text]

    import re
    _SQLITE_SCHEMA_RE = re.compile(r"\bsqlite_(?:schema|master)\b", re.IGNORECASE)
    for q, r in zip(queries, results):
        if _SQLITE_SCHEMA_RE.search(q) and r.strip():
            merge_schema_from_sqlite_results(digest, [r])

    assert "product_kinds" in digest["tables"]
    assert digest["tables"]["product_kinds"]["role"] == "kinds"
```

This test pins the *contract* the pipeline relies on. The pipeline integration is covered by the existing TDD pipeline tests after the wiring lands.

- [ ] **Step 2: Run test, verify pass (helper-only contract)**

Run: `uv run pytest tests/test_pipeline.py::test_pipeline_refreshes_schema_after_sqlite_query -v`
Expected: PASS (after Task 8).

- [ ] **Step 3: Wire the hook into the pipeline**

In `agent/pipeline.py`, near the other regex constants at module top, add:

```python
_SQLITE_SCHEMA_RE = re.compile(r"\bsqlite_(?:schema|master)\b", re.IGNORECASE)
```

Add import alongside other prephase imports:

```python
from .prephase import merge_schema_from_sqlite_results
```

In the execute block, immediately after the existing `last_empty = ...` and the empty/error branch (before `# ── CARRYOVER` near line 604), insert:

```python
                # ── SCHEMA REFRESH from sqlite_schema/sqlite_master discovery ──────────
                refresh_inputs = [
                    r for q, r in zip(queries, sql_results)
                    if _SQLITE_SCHEMA_RE.search(q) and _csv_has_data(r)
                ]
                if refresh_inputs:
                    added = merge_schema_from_sqlite_results(pre.schema_digest, refresh_inputs)
                    if added:
                        print(f"{CLI_BLUE}[pipeline] SCHEMA REFRESH: +{added}{CLI_CLR}")
                        if t := get_trace():
                            t.log_schema_refresh(cycle + 1, added)
```

Confirm `t` is captured in scope (existing pattern: `if t := get_trace():`).

- [ ] **Step 4: Sanity run existing pipeline tests**

Run: `uv run pytest tests/test_pipeline.py tests/test_pipeline_tdd.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): refresh schema digest from sqlite_schema discovery results"
```

---

## Task 11: Prompt updates — `test_gen.md`

**Files:**
- Modify: `data/prompts/test_gen.md`

- [ ] **Step 1: Rewrite aggregate output example and anti-patterns**

Open `data/prompts/test_gen.md`. Apply three changes:

**1.1** Replace the `sql_tests` field of the JSON output example (lines around 65) with an aggregate-aware version. The new example must show selecting `results[-1]` and parsing an integer, never `len(rows) > 1`:

```
  "sql_tests": "def test_sql(results):\n    assert results, 'SQL returned no results'\n    last = (results[-1] or '').strip()\n    assert last, 'last result empty'\n    rows = [r for r in last.split('\\n') if r.strip()]\n    # For aggregate (COUNT/SUM/AVG/MIN/MAX): expect 1 header + 1 data row\n    # For row queries: rows > 1. Pick the assertion appropriate for the SQL.\n    assert len(rows) >= 2, f'no data rows: {last[:200]}'\n    # If aggregate, also assert the data row parses as an integer:\n    # int(rows[-1].split(',')[0].strip())\n",
```

**1.2** In the `## Anti-patterns — never do this` section, add a new sub-section *before* the existing `BAD` example:

```markdown
**BAD** — `len(rows) > 1` for aggregate queries:
~~~python
# SQL was: SELECT COUNT(*) FROM products WHERE kind_id = 7
rows = results[-1].split('\n')
assert len(rows) > 1  # WRONG: COUNT(*) returns 1 header + 1 data row
~~~

**GOOD** — for aggregate queries assert one data row and integer-parse it:
~~~python
last = results[-1].strip()
rows = [r for r in last.split('\n') if r.strip()]
assert len(rows) == 2, f'aggregate must return exactly 1 data row: {last[:200]}'
n = int(rows[-1].split(',')[0].strip())
assert n >= 0, f'count must be non-negative: {n}'
~~~

Rule: For any SQL containing `COUNT(`, `SUM(`, `AVG(`, `MIN(`, `MAX(`, NEVER assert `len(rows) > 1` or `len(results) > 1` — the data row count is exactly 1.

```

**1.3** Under `## Rules for test code`, append one bullet:

```markdown
- `results` contains every executed query in cycle order. Pick the relevant element (typically `results[-1]`); do not assume `results[0]` is the data query.
```

- [ ] **Step 2: Verify prompt loader picks the change up**

Run: `uv run python -c "from agent.prompt import load_prompt; print('len(rows) > 1' in load_prompt('test_gen'))"`
Expected: prints `True` (the BAD example mentions the forbidden pattern verbatim).

- [ ] **Step 3: Commit**

```bash
git add data/prompts/test_gen.md
git commit -m "docs(prompts): ban aggregate len(rows)>1 antipattern; clarify results contract"
```

---

## Task 12: Prompt updates — `resolve.md`, `lookup.md`, `sql_plan.md`, `catalogue.md`

**Files:**
- Modify: `data/prompts/resolve.md`, `data/prompts/lookup.md`, `data/prompts/sql_plan.md`, `data/prompts/catalogue.md`

- [ ] **Step 1: `resolve.md`**

In `data/prompts/resolve.md` line 25, replace:

```
Kind: `SELECT DISTINCT name FROM kinds WHERE name LIKE '%<term>%' LIMIT 10`
```

with:

```
Kind: `SELECT DISTINCT name FROM <table with role=kinds> WHERE name LIKE '%<term>%' LIMIT 10`
```

Add a new paragraph immediately before the `## Discovery query shapes` (or equivalent) section:

```markdown
## Table name resolution

Do not hardcode table names. Consult the **SCHEMA DIGEST** block (provided above): every table is tagged with a semantic role — `role=products`, `role=kinds`, `role=properties`, or `role=other`. Substitute the actual digest name for the role placeholder when emitting queries.
```

- [ ] **Step 2: `sql_plan.md`**

In `data/prompts/sql_plan.md`:

- Add the same `## Table name resolution` paragraph (above) near the top of the file, just below the first heading.
- Line ~15: replace `SELECT DISTINCT <attr> FROM products WHERE ...` with `SELECT DISTINCT <attr> FROM <table with role=products> WHERE ...`
- Line ~110: replace `SELECT DISTINCT name FROM kinds WHERE name LIKE '%<term>%';` with `SELECT DISTINCT name FROM <table with role=kinds> WHERE name LIKE '%<term>%';`
- Examples on lines ~42, 70, 72, 87, 101: leave the *example* literals (`FROM products`) as-is — they are intentional illustrations of the projection rule. Add a single note just before the first example block:

```markdown
> Note: the examples below use the literal name `products` for readability. In real queries, substitute the actual table whose `role=products` in the SCHEMA DIGEST.
```

- [ ] **Step 3: `lookup.md`**

Open `data/prompts/lookup.md`. Grep already confirmed it has no `FROM kinds` or `FROM products` literals to rewrite — only the cross-cutting directive. Add the same `## Table name resolution` paragraph near the top.

- [ ] **Step 4: `catalogue.md`**

In `data/prompts/catalogue.md`:

- Line 8: change `SELECT DISTINCT <attr> FROM products WHERE ...` to `SELECT DISTINCT <attr> FROM <table with role=products> WHERE ...`
- Line 14: change `SELECT COUNT(*) FROM products WHERE type='X'` to `SELECT COUNT(*) FROM <table with role=products> WHERE type='X'`
- Line 15: change `SELECT 1 FROM products WHERE brand=? AND type=? LIMIT 1` to `SELECT 1 FROM <table with role=products> WHERE brand=? AND type=? LIMIT 1`

Then add the same `## Table name resolution` paragraph at the top.

- [ ] **Step 5: Verify no remaining `FROM kinds`**

Run: `grep -n "FROM kinds\b" data/prompts/*.md`
Expected: no matches (the only previous match in `resolve.md` and `sql_plan.md` is replaced).

- [ ] **Step 6: Commit**

```bash
git add data/prompts/resolve.md data/prompts/lookup.md data/prompts/sql_plan.md data/prompts/catalogue.md
git commit -m "docs(prompts): substitute role placeholders for hardcoded table names"
```

---

## Task 13: Full test suite + integration replay

**Files:** none modified.

- [ ] **Step 1: Full unit suite**

Run: `uv run pytest tests/ -v`
Expected: all tests green, no skips for the new tests.

- [ ] **Step 2: Integration replay of t10**

Confirm the model from the failing log is configured (qwen3.5-cloud via OpenRouter or local Ollama, per `models.json`).

Run:

```bash
MAX_STEPS=3 make task TASKS='t10'
```

Expected behaviour:
- `data/eval_log.jsonl` (or task output) contains `answer.message` equal to `<COUNT:3>` (case-insensitive substring match acceptable).
- `answer.outcome == 'OUTCOME_OK'`.
- Cycle count ≤ 3.

If the replay diverges, inspect the latest `logs/<timestamp>_qwen3.5-cloud/t10.jsonl` trace for:
- A `schema_refresh` event after the first `sqlite_schema` query.
- A schema-gate `unknown table` error if the LLM still emits `FROM kinds`.
- An `antipattern` TDD failure if the LLM still emits `len(rows) > 1` on a COUNT.

- [ ] **Step 3: Commit if replay introduced any data changes**

If `data/eval_log.jsonl` updated:

```bash
git add data/eval_log.jsonl
git commit -m "test: t10 replay log after pipeline-failure fixes"
```

Otherwise skip.

---

## Success Criteria

- All new unit tests pass.
- `uv run pytest tests/` green end to end.
- `make task TASKS='t10'` returns `<COUNT:3>` in ≤ 3 cycles with `OUTCOME_OK`.
- No new error categories in the t10 replay trace.
- No regressions across the existing benchmark task set (spot-check with `make task TASKS='t01,t02,t03'`).
