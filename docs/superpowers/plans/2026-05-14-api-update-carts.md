# API Update + Shopping Carts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync proto deprecation annotations with upstream, add `/bin/date`+`/bin/id` mandatory init calls to prephase, inject AGENT CONTEXT block into system prompt, and extend LLM prompt guidance for shopping cart queries.

**Architecture:** Prephase gains two new exec calls that populate `agent_id`/`current_date` fields on `PrephaseResult`; pipeline's `_build_static_system()` receives those fields and conditionally prepends an `# AGENT CONTEXT` block for `sql_plan`/`learn` phases; prompt files get new cart-specific sections.

**Tech Stack:** Python 3.12, Pydantic, protobuf (annotations only — no regeneration), uv/pytest.

---

## File Structure

| File | Change |
|------|--------|
| `proto/bitgn/vm/ecom/ecom.proto` | Add `deprecated = true` annotations |
| `agent/prephase.py` | Add `agent_id`/`current_date` to `PrephaseResult`, add `/bin/date`+`/bin/id` calls, expand `_SCHEMA_TABLES` |
| `agent/pipeline.py` | Add `agent_id`/`current_date` params to `_build_static_system()`, inject AGENT CONTEXT block, update 4 callers |
| `agent/schema_gate.py` | Verify unknown-table handling — likely no change needed |
| `tests/test_prephase.py` | Update field assertion test, add tests for new exec calls |
| `tests/test_pipeline.py` | Add tests for AGENT CONTEXT injection |
| `data/prompts/sql_plan.md` | Append cart query patterns + `/bin/checkout` guidance |
| `data/prompts/answer.md` | Append cart grounding_refs section |
| `data/prompts/resolve.md` | Add `cart_id` discovery pattern and `cart_id` to field enum |

---

### Task 1: Proto deprecation annotations

**Files:**
- Modify: `proto/bitgn/vm/ecom/ecom.proto`

- [ ] **Step 1: Write the failing test (proto is documentation-only — test is a grep sanity check)**

Run:
```bash
grep -c "deprecated" proto/bitgn/vm/ecom/ecom.proto
```
Expected: `0` (no existing deprecation annotations yet).

- [ ] **Step 2: Apply deprecation annotations**

Edit `proto/bitgn/vm/ecom/ecom.proto` — make these targeted changes:

**`Context` RPC** — add deprecated option + comment:
```protobuf
  rpc Context(ContextRequest) returns (ContextResponse) {
    option deprecated = true; // use Exec /bin/date
  }
```

**`ExecResponse`** — mark fields 2 and 5:
```protobuf
message ExecResponse {
  int32 exit_code = 1;
  // MIME type for stdout, e.g. text/plain, text/csv, application/json.
  string content_type = 2 [deprecated = true];
  string stdout = 3;
  string stderr = 4;
  bool truncated = 5 [deprecated = true];
}
```

**`WriteRequest`** — mark field 3:
```protobuf
  // Optional idempotency key for `/run/actions/*` writes.
  string idempotency_key = 3 [deprecated = true];
```

**`WriteResponse`** — mark fields 2, 3, 4:
```protobuf
message WriteResponse {
  string path = 1;
  string audit_path = 2 [deprecated = true];
  string action_id = 3 [deprecated = true];
  ActionStatus action_status = 4 [deprecated = true];
}
```

**`StatResponse`** — mark fields 5, 6, 7:
```protobuf
  string write_schema_content_type = 5 [deprecated = true];
  string write_schema = 6 [deprecated = true];
  string description = 7 [deprecated = true];
```

**`ActionStatus` enum** — add deprecation comment before the enum:
```protobuf
// Deprecated: action-handler pattern removed; enum values unused.
enum ActionStatus {
```

- [ ] **Step 3: Verify annotation count**

Run:
```bash
grep -c "deprecated" proto/bitgn/vm/ecom/ecom.proto
```
Expected: `11` (9 field annotations + 1 rpc option line + 1 enum comment line). Breakdown: ExecResponse×2 + WriteRequest×1 + WriteResponse×3 + StatResponse×3 = 9 fields. Confirm at least 10.

- [ ] **Step 4: Run tests to confirm no regressions**

Run: `uv run python -m pytest tests/ -v -x`
Expected: all pass (proto change has no runtime impact).

- [ ] **Step 5: Commit**

```bash
git add proto/bitgn/vm/ecom/ecom.proto
git commit -m "docs(proto): sync upstream deprecation annotations — Context RPC, ExecResponse, WriteRequest/Response, StatResponse, ActionStatus"
```

---

### Task 2: PrephaseResult new fields + `/bin/date` + `/bin/id` init calls

**Files:**
- Modify: `agent/prephase.py`
- Modify: `tests/test_prephase.py`

- [ ] **Step 1: Write failing tests**

Open `tests/test_prephase.py` and:
1. Replace the `test_prephase_result_fields` test (see below).
2. Delete the now-redundant `test_prephase_result_fields_updated` function entirely (it checks only `agents_md_index` and `schema_digest` — a subset of the new assertion).
3. Add three new tests at the end of the file.

```python
def test_prephase_result_fields():
    """PrephaseResult has exactly the expected fields including agent_id and current_date."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert fields == {
        "agents_md_content", "agents_md_path", "db_schema",
        "agents_md_index", "schema_digest", "agent_id", "current_date",
    }


def test_prephase_calls_bin_date_and_bin_id():
    """run_prephase() calls vm.exec with /bin/date and /bin/id after AGENTS.MD read."""
    from unittest.mock import MagicMock

    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS CONTENT"
    vm.read.return_value = agents_r

    date_r = MagicMock(); date_r.stdout = "2026-05-14"
    id_r = MagicMock(); id_r.stdout = "customer-42"

    def _exec(req):
        if req.path == "/bin/date":
            return date_r
        if req.path == "/bin/id":
            return id_r
        r = MagicMock(); r.stdout = ""
        return r

    vm.exec.side_effect = _exec
    result = run_prephase(vm, "find products")

    exec_paths = [c.args[0].path for c in vm.exec.call_args_list]
    assert "/bin/date" in exec_paths
    assert "/bin/id" in exec_paths
    assert result.current_date == "2026-05-14"
    assert result.agent_id == "customer-42"


def test_prephase_bin_date_failure_produces_empty_string():
    """If /bin/date or /bin/id raises, agent_id/current_date are empty strings — no crash."""
    from unittest.mock import MagicMock

    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS"
    vm.read.return_value = agents_r

    def _exec(req):
        if req.path in ("/bin/date", "/bin/id"):
            raise Exception("not found")
        r = MagicMock(); r.stdout = ""
        return r

    vm.exec.side_effect = _exec
    result = run_prephase(vm, "task")
    assert result.current_date == ""
    assert result.agent_id == ""


def test_prephase_schema_tables_includes_carts():
    """_SCHEMA_TABLES includes carts and cart_items."""
    from agent.prephase import _SCHEMA_TABLES
    assert "carts" in _SCHEMA_TABLES
    assert "cart_items" in _SCHEMA_TABLES
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run python -m pytest tests/test_prephase.py -v -k "test_prephase_result_fields or test_prephase_calls_bin or test_prephase_bin_date or test_prephase_schema_tables"`
Expected: FAIL — `test_prephase_result_fields` fails (missing fields), others fail (fields/calls absent).

- [ ] **Step 3: Implement changes in `agent/prephase.py`**

**Change 1** — expand `_SCHEMA_TABLES` (line 14):
```python
_SCHEMA_TABLES = ["products", "product_properties", "inventory", "kinds", "carts", "cart_items"]
```

**Change 2** — add two fields to `PrephaseResult` dataclass (after `schema_digest` field):
```python
@dataclass
class PrephaseResult:
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    agent_id: str = ""
    current_date: str = ""
```

**Change 3** — in `run_prephase()`, add exec calls after the AGENTS.MD read block and before the db_schema block. Insert after line 114 (`agents_md_index: dict = parse_agents_md(...)`):

```python
    # /bin/date — best-effort
    current_date = ""
    try:
        date_result = vm.exec(ExecRequest(path="/bin/date"))
        current_date = getattr(date_result, "stdout", "").strip()
        print(f"{CLI_BLUE}[prephase] /bin/date:{CLI_CLR} {CLI_GREEN}{current_date!r}{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/date failed: {e}{CLI_CLR}")

    # /bin/id — best-effort
    agent_id = ""
    try:
        id_result = vm.exec(ExecRequest(path="/bin/id"))
        agent_id = getattr(id_result, "stdout", "").strip()
        print(f"{CLI_BLUE}[prephase] /bin/id:{CLI_CLR} {CLI_GREEN}{agent_id!r}{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/id failed: {e}{CLI_CLR}")
```

**Change 4** — update `return PrephaseResult(...)` at the end of `run_prephase()` to include the new fields:

```python
    return PrephaseResult(
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
        agents_md_index=agents_md_index,
        schema_digest=schema_digest,
        agent_id=agent_id,
        current_date=current_date,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_prephase.py -v`
Expected: all pass.

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run python -m pytest tests/ -v -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "feat(prephase): add /bin/date + /bin/id mandatory init calls, new PrephaseResult fields, expand schema tables with carts/cart_items"
```

---

### Task 3: Pipeline AGENT CONTEXT block injection

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Add the following tests at the end of `tests/test_pipeline.py`:

```python
def test_build_static_system_agent_context_injected():
    """_build_static_system injects AGENT CONTEXT block for sql_plan phase when agent_id or current_date set."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-99",
            current_date="2026-05-14",
        )

    texts = [b["text"] for b in blocks]
    ctx_block = next((t for t in texts if "# AGENT CONTEXT" in t), None)
    assert ctx_block is not None
    assert "customer_id: cust-99" in ctx_block
    assert "date: 2026-05-14" in ctx_block


def test_build_static_system_agent_context_absent_when_both_empty():
    """No AGENT CONTEXT block when both agent_id and current_date are empty."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="",
            current_date="",
        )

    texts = [b["text"] for b in blocks]
    assert not any("# AGENT CONTEXT" in t for t in texts)


def test_build_static_system_agent_context_absent_for_answer_phase():
    """AGENT CONTEXT block NOT injected for answer phase even if fields set."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "answer",
            agents_md="",
            agents_md_index={},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-99",
            current_date="2026-05-14",
        )

    texts = [b["text"] for b in blocks]
    assert not any("# AGENT CONTEXT" in t for t in texts)


def test_build_static_system_agent_context_first_block():
    """AGENT CONTEXT block is placed before VAULT RULES (first in blocks list)."""
    import tempfile
    from pathlib import Path
    from agent.pipeline import _build_static_system
    from agent.rules_loader import RulesLoader

    with tempfile.TemporaryDirectory() as tmp:
        rules_loader = RulesLoader(Path(tmp))
        blocks = _build_static_system(
            "sql_plan",
            agents_md="## Brand Aliases\nheco = Heco",
            agents_md_index={"brand_aliases": ["heco = Heco"]},
            db_schema="",
            schema_digest={},
            rules_loader=rules_loader,
            security_gates=[],
            agent_id="cust-1",
            current_date="2026-05-14",
            task_text="find heco products",
        )

    texts = [b["text"] for b in blocks]
    ctx_idx = next(i for i, t in enumerate(texts) if "# AGENT CONTEXT" in t)
    vault_idx = next((i for i, t in enumerate(texts) if "# VAULT RULES" in t), len(texts))
    assert ctx_idx < vault_idx
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run python -m pytest tests/test_pipeline.py -v -k "agent_context"`
Expected: FAIL — `_build_static_system` doesn't accept `agent_id`/`current_date` yet.

- [ ] **Step 3: Implement changes in `agent/pipeline.py`**

**Change 1** — update `_build_static_system` signature to add two new keyword args (after `task_text: str = ""`):

```python
def _build_static_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    task_text: str = "",
    agent_id: str = "",
    current_date: str = "",
) -> list[dict]:
```

**Change 2** — add AGENT CONTEXT block as the very first block in the function body (insert right after `blocks: list[dict] = []`):

```python
    blocks: list[dict] = []

    if (agent_id or current_date) and phase in ("sql_plan", "learn"):
        ctx_lines = []
        if current_date:
            ctx_lines.append(f"date: {current_date}")
        if agent_id:
            ctx_lines.append(f"customer_id: {agent_id}")
        blocks.append({"type": "text", "text": "# AGENT CONTEXT\n" + "\n".join(ctx_lines)})
```

**Change 3** — update all four `_build_static_system()` call sites in `run_pipeline()` to pass the new fields.

Find the three calls at the start of `run_pipeline()` (around lines 414–427) and add `agent_id=pre.agent_id, current_date=pre.current_date` to each:

```python
    static_sql = _build_static_system(
        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
        agent_id=pre.agent_id, current_date=pre.current_date,
    )
    static_learn = _build_static_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        confirmed_values=confirmed_values, task_text=task_text,
        agent_id=pre.agent_id, current_date=pre.current_date,
    )
    static_answer = _build_static_system(
        "answer", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, security_gates,
        agent_id=pre.agent_id, current_date=pre.current_date,
    )
```

Note: there is also a second `static_sql` rebuild inside the loop (DISCOVERY-ONLY DETECTION block, around line 597). Update it too:
```python
                    static_sql = _build_static_system(
                        "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
                        pre.schema_digest, rules_loader, security_gates,
                        confirmed_values=confirmed_values, task_text=task_text,
                        agent_id=pre.agent_id, current_date=pre.current_date,
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_pipeline.py -v -k "agent_context"`
Expected: all 4 new tests pass.

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest tests/ -v -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): inject AGENT CONTEXT block (date + customer_id) into sql_plan/learn system prompt"
```

---

### Task 4: Verify schema_gate unknown-table handling

**Files:**
- Read: `agent/schema_gate.py` (no change expected)
- Modify: `tests/test_schema_gate.py` (add regression test)

- [ ] **Step 1: Confirm existing behavior**

Read `agent/schema_gate.py:46-58`. The key lines are:
```python
known = cols_by_table.get(real_table, set())
if known and col_name not in known:
    return f"unknown column: ..."
```

`known` is an empty set when `real_table` is not in `schema_digest`. Empty set is falsy → `if known` is False → column check skipped. **Behavior is already correct — no code change needed.**

- [ ] **Step 2: Write regression test**

Add to `tests/test_schema_gate.py`:

```python
def test_unknown_table_not_blocked():
    """Queries referencing tables absent from schema_digest are not blocked — EXPLAIN will catch them."""
    from agent.schema_gate import check_schema_compliance

    # schema_digest only knows 'products'; query references 'carts' which is unknown
    schema_digest = {
        "tables": {
            "products": {"columns": [{"name": "sku", "type": "TEXT"}, {"name": "path", "type": "TEXT"}]}
        }
    }
    q = "SELECT c.cart_id, ci.sku FROM carts c JOIN cart_items ci ON ci.cart_id = c.cart_id WHERE c.customer_id = 'x'"
    err = check_schema_compliance([q], schema_digest, {"customer_id": ["x"]}, "cart query")
    assert err is None, f"Unknown tables should not be blocked by schema gate, got: {err}"
```

- [ ] **Step 3: Run test to confirm it passes (behavior already correct)**

Run: `uv run python -m pytest tests/test_schema_gate.py -v -k "test_unknown_table_not_blocked"`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_schema_gate.py
git commit -m "test(schema_gate): add regression test — unknown tables must not be blocked"
```

---

### Task 5: sql_plan.md — cart query patterns

**Files:**
- Modify: `data/prompts/sql_plan.md`

- [ ] **Step 1: Append cart section to `data/prompts/sql_plan.md`**

Add the following at the very end of the file (after the last section):

```markdown
## Cart and Basket Queries

When task involves a buyer's cart or basket:

1. Use `customer_id` from `# AGENT CONTEXT` block to scope the query to current buyer.
2. Cart data is in `carts` and `cart_items` tables (names may vary — verify via `.schema`).
3. Join pattern: `carts → cart_items → products` to resolve product details.
4. `grounding_refs` for cart answers: use `/proc/catalog/{sku}.json` for each product SKU in cart.

Sample cart lookup:

```sql
SELECT ci.sku, ci.quantity, p.name, p.path
FROM carts c
JOIN cart_items ci ON ci.cart_id = c.cart_id
JOIN products p ON p.sku = ci.sku
WHERE c.customer_id = '<customer_id_from_agent_context>'
```

## /bin/checkout

`/bin/checkout` is a runtime tool, NOT a SQL query.
- Do NOT model checkout as SQL.
- If task requires checkout action: use exec tool with `path="/bin/checkout"`. Pass `cart_id` via `ExecRequest.args` field (verify field name in `ecom.proto` — likely `args: [cart_id]`).
- For preview-only: same exec call returns preview without finalizing.
- Pipeline does not have a checkout phase — checkout tasks will be handled based on AGENTS.MD guidance.
```

- [ ] **Step 2: Verify prompt loads without error**

Run:
```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('sql_plan'); assert 'Cart and Basket' in p; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add data/prompts/sql_plan.md
git commit -m "docs(prompts): add cart query patterns and /bin/checkout guidance to sql_plan"
```

---

### Task 6: answer.md — cart grounding_refs guidance

**Files:**
- Modify: `data/prompts/answer.md`

- [ ] **Step 1: Append cart section to `data/prompts/answer.md`**

Add at the very end of the file:

```markdown
## Cart Answers

- `grounding_refs` for cart queries: product paths from `cart_items` via `/proc/catalog/{sku}.json`
- Do NOT include cart_id or cart path itself in grounding_refs — only product SKU paths
- If task was a checkout exec (not SQL): `grounding_refs` = [] or product paths confirmed;
  reflect checkout result in `message`, not in `grounding_refs`
```

- [ ] **Step 2: Verify prompt loads**

Run:
```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('answer'); assert 'Cart Answers' in p; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add data/prompts/answer.md
git commit -m "docs(prompts): add cart grounding_refs guidance to answer phase"
```

---

### Task 7: resolve.md — cart_id discovery pattern

**Files:**
- Modify: `data/prompts/resolve.md`

- [ ] **Step 0: Verify resolve.md exists**

Run:
```bash
test -f data/prompts/resolve.md && echo "EXISTS — append" || echo "ABSENT — create"
```
Expected: `EXISTS — append` (file is known to exist; if absent, create it with the content from Steps 1–3 as a new prompt block).

- [ ] **Step 1: Add cart_id to Discovery query patterns section**

In `data/prompts/resolve.md`, locate the `## Discovery query patterns` section and append the cart_id pattern after the existing patterns:

```
Cart ID: `SELECT DISTINCT cart_id FROM carts WHERE customer_id = '<from_agent_context>' LIMIT 10`
```

The section should look like:
```markdown
## Discovery query patterns

Brand: `SELECT DISTINCT brand FROM products WHERE brand LIKE '%<term>%' LIMIT 10`
Model: `SELECT DISTINCT model FROM products WHERE model LIKE '%<term>%' LIMIT 10`
Kind: `SELECT DISTINCT name FROM kinds WHERE name LIKE '%<term>%' LIMIT 10`
Attr key: `SELECT DISTINCT key FROM product_properties WHERE key LIKE '%<term>%' LIMIT 10`
Attr value (text): `SELECT DISTINCT value_text FROM product_properties WHERE key = '<known_key>' AND value_text LIKE '%<term>%' LIMIT 10`
Cart ID: `SELECT DISTINCT cart_id FROM carts WHERE customer_id = '<from_agent_context>' LIMIT 10`
```

- [ ] **Step 2: Add `cart_id` to `field` enum description**

Find the line:
```
- `field` must be one of: `brand`, `model`, `kind`, `attr_key`, `attr_value`.
```

Replace with:
```
- `field` must be one of: `brand`, `model`, `kind`, `attr_key`, `attr_value`, `cart_id`.
```

- [ ] **Step 3: Add note that customer_id comes from AGENT CONTEXT**

Add after the `cart_id` discovery pattern (end of `## Discovery query patterns` section):

```markdown
Note: `customer_id` comes from `# AGENT CONTEXT` block (populated by `/bin/id` at init). Do NOT generate a discovery candidate for `customer_id` — it is already confirmed.
```

- [ ] **Step 4: Verify prompt loads**

Run:
```bash
uv run python -c "from agent.prompt import load_prompt; p = load_prompt('resolve'); assert 'cart_id' in p; assert 'customer_id' in p; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add data/prompts/resolve.md
git commit -m "docs(prompts): add cart_id discovery pattern and customer_id note to resolve phase"
```

---

### Task 8: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: all pass. Note any failures and fix before continuing.

- [ ] **Step 2: Verify prephase exec sequence in trace output**

Run:
```bash
uv run python -c "
from unittest.mock import MagicMock
from agent.prephase import run_prephase

vm = MagicMock()
agents_r = MagicMock(); agents_r.content = '## Brand\nbrand = test'
vm.read.return_value = agents_r

calls = []
def _exec(req):
    calls.append(req.path)
    r = MagicMock()
    r.stdout = 'test-value' if req.path in ('/bin/date', '/bin/id') else ''
    return r
vm.exec.side_effect = _exec

result = run_prephase(vm, 'find products')
assert '/bin/date' in calls, f'missing /bin/date in {calls}'
assert '/bin/id' in calls, f'missing /bin/id in {calls}'
assert result.current_date == 'test-value'
assert result.agent_id == 'test-value'
print('prephase exec sequence: OK')
print('calls:', calls[:5])
"
```
Expected: `prephase exec sequence: OK`

- [ ] **Step 3: Verify AGENT CONTEXT block absent when both fields empty**

Run:
```bash
uv run python -c "
import tempfile
from pathlib import Path
from agent.pipeline import _build_static_system
from agent.rules_loader import RulesLoader

with tempfile.TemporaryDirectory() as tmp:
    rl = RulesLoader(Path(tmp))
    blocks = _build_static_system('sql_plan', '', {}, '', {}, rl, [], agent_id='', current_date='')
    texts = [b['text'] for b in blocks]
    assert not any('AGENT CONTEXT' in t for t in texts), 'AGENT CONTEXT must be absent when fields empty'
    print('AGENT CONTEXT absent when empty: OK')

    blocks2 = _build_static_system('sql_plan', '', {}, '', {}, rl, [], agent_id='cust-1', current_date='2026-05-14')
    texts2 = [b['text'] for b in blocks2]
    assert any('AGENT CONTEXT' in t for t in texts2), 'AGENT CONTEXT must be present when fields set'
    print('AGENT CONTEXT present when set: OK')
"
```
Expected: both `OK`.

- [ ] **Step 4: Final commit if any loose changes**

```bash
git status
# If any unstaged files remain, stage and commit them.
```
