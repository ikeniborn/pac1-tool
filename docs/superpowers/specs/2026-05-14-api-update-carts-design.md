# Design: API Update + Shopping Carts Support

**Date:** 2026-05-14  
**Scope:** Sync with upstream ecom API changes; add shopping cart domain support

## Context

Upstream `bitgn/sample-agents` ecom API changed:
1. `Context` RPC deprecated → replaced by `/bin/date` and `/bin/id` exec utilities
2. Several `WriteResponse`, `StatResponse`, `ExecResponse` fields deprecated (action-handler pattern removed)
3. New runtime utilities: `/bin/date`, `/bin/id`, `/bin/checkout`
4. New world entity: shopping carts (buyers can ask questions about their carts)

Source of truth:
- Upstream proto: `https://github.com/bitgn/sample-agents/blob/main/proto/bitgn/vm/ecom/ecom.proto`
- Reference agent: `https://github.com/bitgn/sample-agents/blob/main/ecom-py/agent.py`

Reference agent mandatory init sequence:
```python
must = [
    Req_Tree(level=2, root="/"),
    Req_Read(path="/AGENTS.MD"),
    Req_Exec(path="/bin/date"),
    Req_Exec(path="/bin/id"),
]
```

## Constraints

- `ecom_pb2.py` — do NOT regenerate (buf not installed; deprecated fields are metadata-only, wire format unchanged)
- `ecom_connect.py` — keep `context()` method (deprecated, unused, harmless)
- Pipeline architecture unchanged (SQL-based lookup pipeline)
- `/bin/checkout` is exec-only, not a SQL operation — document in prompt, do not extend pipeline

## Component 1: proto/bitgn/vm/ecom/ecom.proto

Sync with upstream. Changes are deprecation annotations only (no field numbers or types change):

- `Context` RPC: add `option deprecated = true` + comment "use Exec /bin/date"
- `ExecResponse`: mark `content_type` (field 2) and `truncated` (field 5) as deprecated
- `WriteRequest`: mark `idempotency_key` (field 3) as deprecated
- `WriteResponse`: mark `audit_path` (field 2), `action_id` (field 3), `action_status` (field 4) as deprecated
- `StatResponse`: mark `write_schema_content_type` (5), `write_schema` (6), `description` (7) as deprecated
- `ActionStatus` enum: add deprecation comment

**File:** `proto/bitgn/vm/ecom/ecom.proto`  
**Impact:** Documentation only. No runtime change.

## Component 2: agent/prephase.py — Mandatory Init Calls

### PrephaseResult — new fields
```python
@dataclass
class PrephaseResult:
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    agent_id: str = ""      # NEW: stdout from /bin/id
    current_date: str = ""  # NEW: stdout from /bin/date
```

### run_prephase() — init sequence
Add two exec calls at the start of `run_prephase()`, before AGENTS.MD read:
```python
# /bin/date
date_result = vm.exec(ExecRequest(path="/bin/date"))
current_date = getattr(date_result, "stdout", "").strip()

# /bin/id
id_result = vm.exec(ExecRequest(path="/bin/id"))
agent_id = getattr(id_result, "stdout", "").strip()
```
Both calls are best-effort (wrapped in try/except; failure → empty string).

### _SCHEMA_TABLES — add cart tables
```python
_SCHEMA_TABLES = ["products", "product_properties", "inventory", "kinds", "carts", "cart_items"]
```
If `carts`/`cart_items` don't exist on the server, `PRAGMA table_info(carts)` returns empty — `_build_schema_digest` silently skips. No crash.

## Component 3: agent/pipeline.py — AGENT CONTEXT block

### _build_static_system() signature change
Add two new keyword arguments:
```python
def _build_static_system(
    phase: str,
    ...,
    agent_id: str = "",
    current_date: str = "",
) -> list[dict]:
```

### New context block
For phases `sql_plan` and `learn`, inject before the VAULT RULES block:
```python
if (agent_id or current_date) and phase in ("sql_plan", "learn"):
    ctx_lines = []
    if current_date:
        ctx_lines.append(f"date: {current_date}")
    if agent_id:
        ctx_lines.append(f"id: {agent_id}")
    blocks.insert(0, {"type": "text", "text": "# AGENT CONTEXT\n" + "\n".join(ctx_lines)})
```

### Callers update
All three `_build_static_system()` calls in `run_pipeline()` pass `agent_id=pre.agent_id, current_date=pre.current_date`.

## Component 4: data/prompts/sql_plan.md — Cart Query Patterns

Add new section **"Cart and Basket Queries"** after existing inventory section:

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
- If task requires checkout action: use exec tool with `path="/bin/checkout"` and cart_id as argument.
- For preview-only: same exec call returns preview without finalizing.
- Pipeline does not have a checkout phase — checkout tasks will be handled based on AGENTS.MD guidance.
```

## Component 5: data/prompts/answer.md — Cart Grounding Refs

Add to **Grounding Refs** section:

```markdown
## Cart Answers

- `grounding_refs` for cart queries: product paths from `cart_items` via `/proc/catalog/{sku}.json`
- Do NOT include cart_id or cart path itself in grounding_refs — only product SKU paths
- If task was a checkout exec (not SQL): `grounding_refs` = [] or product paths confirmed; 
  reflect checkout result in `message`, not in `grounding_refs`
```

## Component 6: data/prompts/resolve.md — Cart Terms

In the `## Discovery query patterns` section, add:
```
Cart ID: `SELECT DISTINCT cart_id FROM carts WHERE customer_id = '<from_agent_context>' LIMIT 10`
```

In the `field` enum description, add `cart_id` alongside `brand`, `model`, `kind`, `attr_key`, `attr_value`.

Note: `customer_id` comes from `# AGENT CONTEXT` (not discovered via SQL). The resolve phase should NOT run discovery for customer_id.

## Component 7: agent/schema_gate.py — Unknown Tables

**Check:** Does `check_schema_compliance()` block queries referencing tables absent from `schema_digest`?

If yes → add logic: if table not in `schema_digest`, skip column validation for that table (unknown table = not a schema violation, columns will be validated at EXPLAIN stage).

**Verify:** Read `schema_gate.py:check_schema_compliance()` and confirm/fix behavior.

## Test Verification

After implementation, verify:
1. `uv run python -m pytest tests/ -v` passes
2. `prephase.py` calls `/bin/date` and `/bin/id` (check trace output)
3. System prompt for sql_plan phase contains `# AGENT CONTEXT` block
4. Cart tables appear in schema_digest if server has them

## File Changelist

| File | Change |
|------|--------|
| `proto/bitgn/vm/ecom/ecom.proto` | Add deprecated annotations |
| `agent/prephase.py` | Add `/bin/date`+`/bin/id` init, new PrephaseResult fields, expand `_SCHEMA_TABLES` |
| `agent/pipeline.py` | AGENT CONTEXT block in `_build_static_system()`, updated callers |
| `data/prompts/sql_plan.md` | Cart query patterns + /bin/checkout guidance |
| `data/prompts/answer.md` | Cart grounding_refs guidance |
| `data/prompts/resolve.md` | Cart discoverable terms |
| `agent/schema_gate.py` | Verify/fix unknown-table handling (may need no change) |

## Out of Scope

- pb2 regeneration (buf not available; deprecated fields don't affect wire format)
- Pipeline checkout phase (defer until actual task types are known)
- Cart schema assumptions beyond `carts`/`cart_items` (actual schema discovered via AGENTS.MD + .schema at runtime)
