# Design: Five Bug Fixes — 2026-05-04

## Context

Five blocking issues identified from 5-run analysis (docs/run_analysis_2026-05-04.md).
Overall score: 16% (4/25). Root causes: broken DSPy feedback loop, bad temporal reasoning,
CRM misclassification, evaluator rejection loop.

---

## Bug 1: _StepFact не сериализуется в dict

**Root cause**: `executor_agent.py:78` passes `list[_StepFact]` (stdlib dataclass) to
`ExecutionResult.step_facts: list[dict]`. Pydantic v2 raises `ValidationError` every task,
every run. Consequence: DSPy examples never accumulate.

**Fix (A — minimal)**:

File: `agent/agents/executor_agent.py:78`

```python
import dataclasses
_raw = stats.get("step_facts", [])
step_facts=[dataclasses.asdict(sf) if dataclasses.is_dataclass(sf) else sf for sf in _raw],
```

`dataclasses.is_dataclass()` guard prevents double-conversion if a dict is already present.

---

## Bug 2: postrun optimize падает без traceback

**Root cause**: three sub-issues:
1. `postrun.py` uses `python` (may not be in PATH); should use `sys.executable`
2. Error message only shows `exc.stderr`; optimize script writes errors to stdout
3. `optimize_prompts.py` calls `sys.exit(1)` when < threshold examples — treats "no data yet"
   as a hard failure, causing postrun to abort every early run

**Fix (B)**:

File: `agent/postrun.py:80–95`
- Replace `"python"` with `sys.executable`
- Show both stdout and stderr in the error log
- Change `sys.exit(1)` → `log.warning(...)` (optimize is best-effort, not required)

File: `scripts/optimize_prompts.py`
- Find all `sys.exit(1)` in "no examples / below threshold" branches
- Replace with `print(...)` + `return` (graceful skip)
- Only `sys.exit(1)` on unexpected errors (import failures, etc.)

---

## Bug 3: t41/t42 temporal — ESTIMATED_TODAY wrong

**Root cause**: `_TEMPORAL` prompt block (STEP 0) applies a hardcoded `gap = +5 days` from
VAULT_DATE. Vault is randomized each run with gaps 1–9 days. Fixed gap is wrong ~80% of runs.

**Fix (B — multi-signal triangulation)**:

File: `agent/prompt.py` → `_TEMPORAL` block, STEP 0 section.

Replace fixed-gap recipe with:

```
**STEP 0 — TRIANGULATE TODAY (multi-signal)**

DO NOT apply a fixed gap. Instead:

1. Collect ≥3 date anchors from the vault:
   - YYYY-MM-DD__ prefixes in /inbox/, /01_capture/ filenames
   - `updated_on`, `last_contact_on`, `closed_on` fields in JSON files
   - `due_on`, `next_follow_up_on` fields (future-anchored: subtract 3–7 days)

2. For each anchor D, compute implied_today:
   - Past-anchored (filename prefix, last_*_on, closed_on): implied_today = D + offset
     where offset = estimated lag between event and "today" (typically 1–9 days).
     If only one signal available, use offset = 5 as default.
   - Future-anchored (due_on, next_follow_up_on): implied_today = D − 3
     (field records a future date; today is ~3 days before it)

3. Take the MEDIAN of all implied_today values as ESTIMATED_TODAY.
   If signals spread > 14 days apart: discard outliers, re-median.

4. ESTIMATED_TODAY must fall within [VAULT_DATE, VAULT_DATE + 14 days].
   If not: OUTCOME_NONE_CLARIFICATION.

State derivation: "anchors=[D1+g1=T1, D2+g2=T2, ...], median=ESTIMATED_TODAY"
```

Trade-off: requires 2–3 extra read/list steps per temporal task. Eliminates systematic
date error for all vault randomizations.

---

## Bug 4: t13 CRM reschedule misclassified

**Root cause**: `crm` has no `fast_path` in `data/task_types.json`. LLM classifier routes
"reschedule/reconnect" to `preject` (external system). Runs 1–2: UNSUPPORTED; runs 4–5: CLARIFICATION.

**Fix (B)**:

File: `data/task_types.json` → `crm` entry:

```json
"fast_path": {
  "pattern": "\\b(reschedule|reconnect|rebook|re-?schedule)\\b.{0,60}\\b(follow.?up|reminder|account|contact)\\b|\\b(follow.?up|reminder)\\b.{0,60}\\b(reschedule|reconnect|rebook)\\b",
  "flags": ["IGNORECASE", "DOTALL"],
  "confidence": "high"
}
```

Also update `description` field to add anti-pattern:
`"NOT preject: reschedule/reconnect without external URL/tool = crm"`

This covers the exact t13 task text: "Nordlicht Health asked to reconnect in two weeks.
Reschedule the follow-up accordingly."

---

## Bug 5: Evaluator rejection loop — required_evidence

**Root cause**: Two issues:
1. Contract evaluator LLM generates descriptive strings in `required_evidence`
   (e.g. `"Final listing of /contacts/ showing all contacts"`) instead of bare paths
2. The check `ref.lower() in e.lower()` requires the exact grounding_ref path to appear
   as a substring of the description. Agent path `/contacts/alice.json` is NOT a substring
   of `"listing of /contacts/ directory"` → false rejection every time

**Fix (B — systemic)**:

**Part 1** — Contract negotiation prompts in `data/prompts/default/evaluator_contract.md`
(and per-type variants: `crm/`, `lookup/`, `inbox/`, etc. where `required_evidence` is used).

Add to the JSON schema description in each file:
```
required_evidence: bare vault paths only. Examples: ["/contacts/", "/reminders/acct_003.json"]
No prose descriptions. Empty list [] if no specific reads required.
```

**Part 2** — Rejection message in `agent/evaluator.py:461–464`:

```python
_issue = (
    f"Required reads missing from grounding_refs. "
    f"Before re-submitting, add these paths to grounding_refs: {missing}. "
    f"Re-read them if needed."
)
```

Remove "Contract required_evidence" phrasing — agent has no knowledge of "contract".
Direct actionable instruction instead.

---

## Files Changed

| File | Bug | Change |
|------|-----|--------|
| `agent/agents/executor_agent.py` | 1 | `dataclasses.asdict()` conversion |
| `agent/postrun.py` | 2 | `sys.executable`, stdout+stderr, non-fatal |
| `scripts/optimize_prompts.py` | 2 | graceful skip on no-examples |
| `agent/prompt.py` | 3 | multi-signal STEP 0 in `_TEMPORAL` |
| `data/task_types.json` | 4 | `crm.fast_path` + description anti-pattern |
| `agent/evaluator.py` | 5 | bare-paths instruction + clearer rejection message |

## Success Criteria

1. No Pydantic ValidationError in logs → `data/dspy_examples.jsonl` grows after each run
2. No `[postrun] optimize failed` → optimizer either succeeds or logs warning and continues
3. t41/t42 temporal: agent shows multi-anchor derivation in `current_state`
4. t13 CRM: classified as `crm` (not `preject`) via fast_path
5. Evaluator rejection count drops from 2/task to 0 for well-executed CRM/lookup tasks
