# Structured SQL Pipeline Design

**Date:** 2026-05-12  
**Status:** Approved  
**Scope:** Replace `agent/loop.py` agentic loop with a deterministic phase pipeline for catalogue lookup tasks

---

## Problem

Current agentic loop (`loop.py`) is open-ended: the LLM decides tool sequence, may skip SQL validation, may read `/proc/catalog/` files directly, and has no mechanism for learning from failures. `prephase.py` only reads `/bin/sql` in `DRY_RUN` mode. The system prompt (`prompt.py`) is generic and does not use `AGENTS.MD` from the VM as primary authority.

---

## Solution

A phase-based state machine pipeline where:
- `AGENTS.MD` from VM is the primary system prompt
- `data/rules.yaml` provides additional managed rules (injected as markdown)
- SQL is always validated before execution
- Errors trigger a LEARN phase that derives and saves a new rule
- Auto-generated rules require manual verification before future use

---

## Pipeline State Machine

```
prephase:
  1. Read AGENTS.MD from VM → base system prompt
  2. Run /bin/sql .schema → DB schema/semantics
  3. Load data/rules.yaml (verified=true only) → inject as markdown blocks

phases (sequential LLM calls):
  SQL_PLAN   [LLM] → SqlPlanOutput(queries: list[str])
      ↓
  VALIDATE   [deterministic] → EXPLAIN each query via /bin/sql
      ↓ syntax error → LEARN → SQL_PLAN retry
  EXECUTE    [deterministic] → run queries, collect results
      ↓ empty result or error → LEARN → SQL_PLAN retry
  ANSWER     [LLM] → AnswerOutput(message, outcome, grounding_refs)
      ↓
  DONE (dispatch Answer RPC)

LEARN [LLM]:
  input: failed SQL + error/empty result + task context
  output: LearnOutput(conclusion: str, rule_content: str)
  action: save rule to rules.yaml (verified=false, source=auto)
          inject rule into current session context (in-memory only)
  then: retry SQL_PLAN (max 3 cycles total across all retries)
```

---

## System Prompt Composition

Order of sections injected into system prompt:

1. `AGENTS.MD` content (read from VM per task — primary authority)
2. Pipeline execution rules (from `data/rules.yaml`, `phase: sql_plan`, `verified: true`)
3. Security gate rules summary (from `data/rules.yaml`, `security_gates`)
4. In-session auto-rules (LEARN output, `verified: false`, active for current task only)

Rules are rendered as a `## Rules` markdown section after AGENTS.MD content.

---

## `data/rules.yaml` Schema

```yaml
pipeline_rules:
  - id: "sql-001"           # unique, stable ID
    phase: sql_plan         # which phase this applies to
    verified: true          # false = not loaded in future runs
    source: manual          # manual | auto
    content: |              # markdown, injected verbatim
      Never SELECT without a WHERE clause. Use product_properties
      for attribute filtering, not LIKE on name column.
    created: "2026-05-12"
    task_id: null           # set for auto rules (origin task)

security_gates:
  - id: "sec-001"
    pattern: "^\\s*(DROP|INSERT|UPDATE|DELETE|ALTER|CREATE)"
    action: block
    message: "DDL/DML prohibited"
  - id: "sec-002"
    pattern: "SELECT[\\s\\S]+FROM\\s+\\w+"  # post-parse check: no WHERE token
    action: block
    message: "Full table scan prohibited — add WHERE clause"
  - id: "sec-003"
    path_prefix: "/proc/catalog/"   # applied to Req_Read / Req_List path
    action: block
    message: "Use SQL only — direct catalog file reads prohibited"
```

Auto-rules appended by LEARN phase use `verified: false`, `source: auto`, `task_id: <current>`.

---

## Rule Verification Flow

```
LEARN saves rule → verified: false
  │
  ├── current task run: rule active in-memory → used for retry
  │
  └── future runs: filtered out (only verified=true loaded)
         │
         └── human review: set verified: true in rules.yaml → active globally
```

---

## Security Gates

Applied in `agent/sql_security.py` before every EXECUTE:

| Gate | What it blocks | Action |
|------|---------------|--------|
| DDL/DML | DROP, INSERT, UPDATE, DELETE, ALTER, CREATE | hard block → error to LEARN |
| Full scan | SELECT without WHERE on products/inventory | hard block → error to LEARN |
| Catalog file read | Req_Read/Req_List path starts with `/proc/catalog/` | hard block |
| Large result | Result > 500 rows | truncate + warn (no block) |

---

## New Pydantic Models (`agent/models.py` additions)

```python
class SqlPlanOutput(BaseModel):
    reasoning: str          # why these queries answer the task
    queries: list[str]      # ordered list of SQL strings to execute

class LearnOutput(BaseModel):
    conclusion: str         # diagnosis of what went wrong
    rule_content: str       # new rule text to inject

class AnswerOutput(BaseModel):
    message: str            # final answer text (follows AGENTS.MD format rules)
    outcome: Literal["OUTCOME_OK", "OUTCOME_NONE_CLARIFICATION",
                     "OUTCOME_NONE_UNSUPPORTED", "OUTCOME_DENIED_SECURITY"]
    grounding_refs: list[str]   # /proc/catalog/{sku}.json paths
    completed_steps: list[str]  # laconic summary of steps taken
```

---

## Module Map

| Module | Change | Purpose |
|--------|--------|---------|
| `agent/pipeline.py` | **new** | State machine runner — replaces `loop.py` for lookup tasks |
| `agent/sql_security.py` | **new** | Security gate evaluation against `security_gates` in rules.yaml |
| `agent/rules_loader.py` | **new** | Load (verified=true filter), append, save `data/rules.yaml` |
| `agent/models.py` | **modify** | Add `SqlPlanOutput`, `LearnOutput`, `AnswerOutput` |
| `agent/prephase.py` | **modify** | Always read `/bin/sql .schema` (remove dry_run guard) |
| `agent/prompt.py` | **modify** | `build_system_prompt(agents_md, rules)` — compose from AGENTS.MD + rules |
| `agent/orchestrator.py` | **modify** | Route lookup tasks to `run_pipeline()`, others to `run_loop()` |
| `data/rules.yaml` | **new** | Initial manual rules + security gates |
| `agent/loop.py` | **unchanged** | Still used for inbox/email/other task types |

---

## PrephaseResult Changes

`PrephaseResult` gains two new fields:

```python
@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    bin_sql_content: str = ""      # existing
    db_schema: str = ""            # NEW: output of /bin/sql .schema
```

`prephase.py` always runs `/bin/sql .schema` (unconditionally, not gated on `dry_run`).

---

## Retry Budget

- Max 3 SQL_PLAN → VALIDATE → EXECUTE → LEARN cycles per task
- Each LEARN produces at most 1 rule
- After 3 failed cycles: ANSWER with `OUTCOME_NONE_CLARIFICATION`

---

## What Does NOT Change

- `main.py` — unchanged
- `agent/dispatch.py` — LLM routing unchanged, reused by pipeline
- `agent/tracer.py` — tracing unchanged
- `agent/json_extract.py` — reused for LLM response parsing
- BitGN harness integration — unchanged
- `loop.py` behaviour for non-lookup task types
