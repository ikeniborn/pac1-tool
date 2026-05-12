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
- Every LLM call follows the **SGR pattern** (Schema → Guide → Reasoning)
- `AGENTS.MD` from VM is the primary system prompt
- `data/rules.yaml` provides additional managed rules (injected as markdown)
- SQL is always validated before execution
- Errors trigger a LEARN phase that derives and saves a new rule
- Auto-generated rules require manual verification before future use
- A post-execution **Evaluator** analyses pipeline quality and produces optimization conclusions

---

## SGR Pattern

Every LLM call in the pipeline follows **Schema Guide Reasoning**:

| Layer | What it means | Implementation |
|-------|--------------|----------------|
| **Schema** | Structured Pydantic input/output at every step | Each phase has a dedicated `BaseModel` with typed fields |
| **Guide** | Phase instructions loaded from `data/prompts/<phase>.md` | File read at module import; injected as system prompt |
| **Reasoning** | Mandatory CoT field in every output | All output models contain `reasoning: str` as first field |

```
data/prompts/<phase>.md  [Guide]
        ↓
   call_llm_raw()  →  JSON response
        ↓
Pydantic(reasoning: str, ...)  [Schema + Reasoning]
```

---

## Pipeline State Machine

```
prephase:
  1. Read AGENTS.MD from VM → base system prompt
  2. Run /bin/sql .schema → DB schema/semantics
  3. Load data/rules.yaml (verified=true only) → inject as markdown blocks

phases (sequential LLM calls, each follows SGR):
  SQL_PLAN   [LLM] → SqlPlanOutput(reasoning, queries: list[str])
      ↓
  VALIDATE   [deterministic] → EXPLAIN each query via /bin/sql
      ↓ syntax error → LEARN → SQL_PLAN retry
  EXECUTE    [deterministic] → run queries, collect results
      ↓ empty result or error → LEARN → SQL_PLAN retry
  ANSWER     [LLM] → AnswerOutput(reasoning, message, outcome, grounding_refs, completed_steps)
      ↓
  dispatch vm.answer()  → benchmark scores the answer
      ↓
  EVALUATE   [LLM, MODEL_EVALUATOR, separate call]  → EvalOutput → data/eval_log.jsonl

LEARN [LLM]:
  input: failed SQL + error/empty result + task context
  output: LearnOutput(reasoning, conclusion: str, rule_content: str)
  action: save rule to rules.yaml (verified=false, source=auto)
          inject rule into current session context (in-memory only)
  then: retry SQL_PLAN (max 3 cycles total across all retries)
```

---

## System Prompt Composition

Order of sections injected into system prompt for each phase:

1. `AGENTS.MD` content (read from VM per task — primary authority)
2. Pipeline execution rules (from `data/rules.yaml`, `phase: sql_plan`, `verified: true`)
3. Security gate rules summary (from `data/rules.yaml`, `security_gates`)
4. Phase-specific guide (from `data/prompts/<phase>.md`)
5. In-session auto-rules (LEARN output, `verified: false`, active for current task only)

---

## Pydantic Models (`agent/models.py` additions)

All LLM-phase output models follow SGR — `reasoning` field is mandatory and first.

```python
class SqlPlanOutput(BaseModel):
    reasoning: str          # CoT: why these queries answer the task
    queries: list[str]      # ordered list of SQL strings to execute

class LearnOutput(BaseModel):
    reasoning: str          # CoT: diagnosis of what went wrong
    conclusion: str         # human-readable summary
    rule_content: str       # new rule text to inject

class AnswerOutput(BaseModel):
    reasoning: str          # CoT: justification of the answer
    message: str            # final answer text (follows AGENTS.MD format rules)
    outcome: Literal["OUTCOME_OK", "OUTCOME_NONE_CLARIFICATION",
                     "OUTCOME_NONE_UNSUPPORTED", "OUTCOME_DENIED_SECURITY"]
    grounding_refs: list[str]    # /proc/catalog/{sku}.json paths
    completed_steps: list[str]   # laconic summary of steps taken

class PipelineEvalOutput(BaseModel):
    reasoning: str               # CoT: analysis of instruction-following quality
    score: float                 # 0.0–1.0
    comment: str                 # brief verdict
    prompt_optimization: list[str]  # specific suggestions for data/prompts/*.md
    rule_optimization: list[str]    # specific suggestions for rules.yaml
```

---

## Prompts Storage (`data/prompts/`)

All prompts move from inline Python strings to files. `agent/prompt.py` becomes a loader.

```
data/prompts/
  # Existing blocks (migrated from prompt.py)
  core.md
  lookup.md
  email.md
  inbox.md
  catalogue.md
  # New SQL pipeline phases
  sql_plan.md          # Guide for SQL_PLAN phase
  learn.md             # Guide for LEARN phase
  answer.md            # Guide for ANSWER phase
  pipeline_evaluator.md  # Guide for EVALUATE phase
```

`agent/prompt.py` loads all files at module import. Block composition by task type is unchanged — `build_system_prompt(task_type)` returns the same assembled text, but sourced from files instead of string literals.

---

## Evaluator (`agent/evaluator.py`)

Full rewrite of legacy evaluator. Runs **after** `vm.answer()` returns the benchmark result.

### Input/Output

```python
@dataclass
class EvalInput:
    task_text: str
    agents_md: str               # from prephase
    db_schema: str               # from /bin/sql .schema
    sgr_trace: list[dict]        # per-phase: {phase, guide_prompt, reasoning, output}
    benchmark_score: float | None  # outcome from vm.answer() if available
```

Output: `PipelineEvalOutput` (defined in Pydantic Models section above).

### Behaviour

- Prompt: `data/prompts/pipeline_evaluator.md`
- Model: `MODEL_EVALUATOR` env var
- Toggleable: `EVAL_ENABLED=1` (default `0`)
- Fail-open: any exception → `None`, task not blocked
- Output saved to `data/eval_log.jsonl` (one JSON object per task)

### What the evaluator receives

The evaluator prompt instructs the model to assess:
- How well each phase followed its guide prompt
- Whether `reasoning` fields reflect genuine CoT or are superficial
- SQL efficiency (fewer cycles = better; each retry penalised)
- Answer grounding quality (refs present and relevant)
- Concrete, actionable suggestions for `data/prompts/*.md` and `data/rules.yaml`

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

## Env Vars

| Var | Default | Description |
|-----|---------|-------------|
| `EVAL_ENABLED` | `0` | `1` = run pipeline evaluator |
| `MODEL_EVALUATOR` | — | model for evaluator (required if `EVAL_ENABLED=1`) |

---

## Module Map

| Module | Change | Purpose |
|--------|--------|---------|
| `agent/pipeline.py` | **new** | SGR state machine runner — replaces `loop.py` for lookup tasks |
| `agent/sql_security.py` | **new** | Security gate evaluation against `security_gates` in rules.yaml |
| `agent/rules_loader.py` | **new** | Load (verified=true filter), append, save `data/rules.yaml` |
| `agent/evaluator.py` | **full rewrite** | Post-execution evaluator: `EvalInput` → `PipelineEvalOutput` → `data/eval_log.jsonl` |
| `agent/models.py` | **modify** | Add `SqlPlanOutput`, `LearnOutput`, `AnswerOutput`, `PipelineEvalOutput` |
| `agent/prephase.py` | **modify** | Always read `/bin/sql .schema` (remove dry_run guard) |
| `agent/prompt.py` | **modify** | Becomes file loader: reads `data/prompts/*.md` at import, assembles blocks as before |
| `agent/orchestrator.py` | **modify** | Route lookup tasks to `run_pipeline()`, others to `run_loop()` |
| `data/prompts/*.md` | **new** | All prompt blocks + phase guides |
| `data/rules.yaml` | **new** | Initial manual rules + security gates |
| `data/eval_log.jsonl` | **new** | Per-task evaluator output |
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
