# Spec: Eval-Driven Rule Pipeline

**Date:** 2026-05-12  
**Scope:** Fix t03-class failures + clarify rule lifecycle  

---

## Problem

t03 scored 0.00 due to two compounding issues:

1. **SqlPlan cycle-budget bug:** Cycle 2 emitted only discovery queries (`DISTINCT model`, `DISTINCT key`) without a final verification query. The `last_empty` check passed (discovery results have data), so `success=True` triggered Answer phase with incomplete data.

2. **Answer misuse of OUTCOME_NONE_CLARIFICATION:** Answer phase received discovery-only SQL results, couldn't confirm attribute values, and emitted `OUTCOME_NONE_CLARIFICATION` with empty `grounding_refs` — wrong outcome for an incomplete lookup.

3. **Dead rule pipeline:** LEARN writes `sql-XXX-auto.yaml` with `verified: false`. `_build_system` uses `verified_only=True`. Auto-rules are never applied to subsequent runs — dead code. Session rules (`session_rules` list) work correctly for the current run.

---

## Design

### 1. Prompt fix: `data/prompts/sql_plan.md`

Add rule:

> **Final query obligation:** If your plan includes discovery queries (`SELECT DISTINCT model`, `SELECT DISTINCT key`), you MUST also include the final verification query as the last query in the same plan. A plan consisting only of discovery queries is incomplete. The pipeline has a limited cycle budget — every plan must advance toward a definitive answer.

### 2. Prompt fix: `data/prompts/answer.md`

Add rule:

> **Clarification guard:** `OUTCOME_NONE_CLARIFICATION` is valid ONLY when the task text itself is genuinely ambiguous and no SQL could resolve it. If SQL results exist — even discovery-only (model list, key list) — use `OUTCOME_OK`. If value verification was not completed, state in `message` what was and was not confirmed. Empty `grounding_refs` with `OUTCOME_NONE_CLARIFICATION` is a bug, not a valid state.

### 3. New rule file: `data/rules/sql-cycle-budget.yaml`

```yaml
id: sql-cycle-budget
phase: sql_plan
verified: true
source: manual
content: |
  When discovery queries (SELECT DISTINCT model, SELECT DISTINCT key) have
  confirmed model name and attribute key names, include the final verification
  query (with WHERE brand/model/EXISTS filters) as the LAST query in the same
  plan. Never end a plan with only discovery queries — that wastes a cycle.
created: "2026-05-12"
task_id: null
```

### 4. Verify existing rule: `data/rules/sql-010-auto.yaml`

Set `verified: true`. The rule is correct (validated by t03 run, evaluator confirmed). Currently unverified → not applied on subsequent runs.

### 5. Remove dead code: `_run_learn()` in `agent/pipeline.py`

Remove `rules_loader.append_rule(...)` call. Keep `session_rules.append(learn_out.rule_content)`.

**Why:** Auto-generated yaml rules are never applied (`verified_only=True` filter). Session rules work correctly for the current run without yaml persistence. Persisting unverified rules creates noise in `data/rules/`.

Before:
```python
if learn_out:
    rules_loader.append_rule(learn_out.rule_content, task_id=task_text[:100])
    session_rules.append(learn_out.rule_content)
```

After:
```python
if learn_out:
    session_rules.append(learn_out.rule_content)
```

---

## Rule Lifecycle (new)

```
Run pipeline
    ↓
LEARN phase → session_rules (in-memory, current run only)
    ↓
Evaluator → data/eval_log.jsonl
    {
      "rule_optimization": ["...actionable rule text..."]
    }
    ↓
scripts/propose_rules.py  ← NEW
    ↓
data/rules/sql-XXX-candidate.yaml (verified: false)
    ↓
Human reviews: set verified: true  (or delete)
    ↓
Applied on next run via get_rules_markdown(verified_only=True)
```

Evaluator is the authoritative source for persistent rules. LEARN is session-only.

### 6. New script: `scripts/propose_rules.py`

Reads `data/eval_log.jsonl`, calls `MODEL_EVALUATOR` to synthesize each `rule_optimization` item into a well-formed rule, writes candidate yaml files with `verified: false`.

**Interface:**
```bash
uv run python scripts/propose_rules.py          # process all unprocessed entries
uv run python scripts/propose_rules.py --dry-run # print candidates, don't write
```

**LLM synthesis step:** For each `rule_optimization` item, the script calls `MODEL_EVALUATOR` with:
- System prompt: instruction to convert a raw recommendation into a concise, actionable rule in the format used by `data/rules/*.yaml` — starts with "Never", "Always", or "Use"; one self-contained paragraph; includes an example if helpful
- User message: the raw `rule_optimization` text + existing rules (for dedup context)
- LLM returns the refined `content` field text only

The LLM improves phrasing, removes redundancy with existing rules, and ensures the rule is actionable. If the LLM determines the recommendation is already covered by existing rules, it returns `null` — script skips that item.

**Deduplication:** Existing `data/rules/*.yaml` content is passed to the LLM as context. Script also tracks processed entries in `data/.eval_rules_processed` (hash of `task_text + rule_optimization`) to skip on re-run.

**Output per item:**
```yaml
id: sql-XXX-candidate
phase: sql_plan
verified: false
source: eval
content: |
  <LLM-synthesized rule text>
created: "YYYY-MM-DD"
task_text: "<first 120 chars of task_text from eval_log entry>"
eval_score: 0.1
raw_recommendation: "<original rule_optimization text>"
```

**Model config:** reads `MODEL_EVALUATOR` and model config from `models.json` (same as evaluator). Requires `.env` with `MODEL_EVALUATOR` set.

**Verification workflow:**
```bash
# After a run with EVAL_ENABLED=1:
uv run python scripts/propose_rules.py

# Review generated candidates:
ls data/rules/*-candidate.yaml

# Approve: set verified: true, rename sql-XXX-candidate.yaml → sql-XXX.yaml
# Reject: delete the file
```

---

## Files Changed

| File | Change |
|------|--------|
| `data/prompts/sql_plan.md` | Add final query obligation rule |
| `data/prompts/answer.md` | Add clarification guard rule |
| `data/rules/sql-cycle-budget.yaml` | Create (verified: true) |
| `data/rules/sql-010-auto.yaml` | Set verified: true |
| `agent/pipeline.py` | Remove `rules_loader.append_rule()` from `_run_learn()` |
| `scripts/propose_rules.py` | Create — eval_log → candidate yaml rules |
| `data/.eval_rules_processed` | Create — dedup tracking file |

---

## Success Criteria

- t03 re-run: cycle 2 SqlPlan includes discovery + final verification query
- t03 score > 0.00
- `eval_log.jsonl` contains entry after t03 with `rule_optimization`
- No new `sql-XXX-auto.yaml` files created during runs
- `propose_rules.py --dry-run` prints candidates from existing `eval_log.jsonl`
- `propose_rules.py` writes candidate yamls, skips already-processed entries on re-run
