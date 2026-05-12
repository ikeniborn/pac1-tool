# Eval-Driven Optimization Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix t03 score (0.00); add `security_optimization` to evaluator; create `scripts/propose_optimizations.py` that synthesizes eval_log into rule/security/prompt candidates (all `verified: false`); remove dead LEARN-based auto-rule persistence.

**Architecture:** Single `verified` flag controls activation across all artifact types. `propose_optimizations.py` writes three types of candidates: `data/rules/sql-NNN.yaml` (verified: false), `data/security/sec-NNN.yaml` (verified: false), `data/prompts/optimized/*.md`. User sets `verified: true` to activate rules/security; copies `.md` files to `data/prompts/` to activate prompt patches. No code changes to `load_prompt`. `load_security_gates` filters `verified: false`.

**Tech Stack:** Python 3.12, PyYAML, python-dotenv, `agent.dispatch.call_llm_raw`, pytest

---

## File Map

| File | Action |
|------|--------|
| `agent/models.py` | Add `security_optimization: list[str]` to `PipelineEvalOutput` |
| `data/prompts/pipeline_evaluator.md` | Add security assessment section + `security_optimization` to output format |
| `agent/evaluator.py` | Log `security_optimization` to eval_log |
| `data/prompts/sql_plan.md` | Add final-query-obligation rule |
| `data/prompts/answer.md` | Add clarification-guard rule |
| `data/rules/sql-cycle-budget.yaml` | Create (verified: true, source: manual, no task_id) |
| `data/rules/sql-010-auto.yaml` | Set `verified: true`, remove `task_id` |
| `data/rules/sql-001..004-*.yaml` | Remove `task_id` field (legacy) |
| `agent/rules_loader.py` | Remove `append_rule` method (dead after pipeline.py fix) |
| `agent/pipeline.py` | Remove `rules_loader.append_rule(...)` from `_run_learn()` |
| `agent/sql_security.py` | Filter `verified: false` gates in `load_security_gates` |
| `scripts/__init__.py` | Create empty |
| `scripts/propose_optimizations.py` | Create — 3-channel eval_log synthesizer |
| `tests/test_evaluator.py` | Update: include `security_optimization` in mock responses |
| `tests/test_pipeline.py` | Add: LEARN does not call `append_rule` |
| `tests/test_sql_security.py` | Add: `verified: false` gate is skipped |
| `tests/test_propose_optimizations.py` | Create |

---

## Task 1: Extend PipelineEvalOutput + Evaluator

**Files:**
- Modify: `agent/models.py`
- Modify: `data/prompts/pipeline_evaluator.md`
- Modify: `agent/evaluator.py`
- Modify: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing test**

In `tests/test_evaluator.py`, replace `test_run_evaluator_writes_to_log`:

```python
def test_run_evaluator_writes_to_log(tmp_path):
    eval_json = json.dumps({
        "reasoning": "trace is good",
        "score": 0.9,
        "comment": "solid",
        "prompt_optimization": [],
        "rule_optimization": [],
        "security_optimization": ["Add gate for UNION SELECT injection"],
    })
    log_path = tmp_path / "eval_log.jsonl"
    with patch("agent.evaluator.call_llm_raw", return_value=eval_json), \
         patch("agent.evaluator._EVAL_LOG", log_path):
        result = run_evaluator(_make_eval_input(), model="test-model", cfg={})

    assert result is not None
    assert result.score == 0.9
    assert result.security_optimization == ["Add gate for UNION SELECT injection"]
    line = json.loads(log_path.read_text().strip())
    assert line["security_optimization"] == ["Add gate for UNION SELECT injection"]
```

- [ ] **Step 2: Run — verify FAIL**

```bash
uv run pytest tests/test_evaluator.py::test_run_evaluator_writes_to_log -v
```

Expected: `FAILED` — `PipelineEvalOutput` has no field `security_optimization`.

- [ ] **Step 3: Add field to PipelineEvalOutput**

In `agent/models.py`, change:

```python
class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    prompt_optimization: list[str]
    rule_optimization: list[str]
```

to:

```python
class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    prompt_optimization: list[str]
    rule_optimization: list[str]
    security_optimization: list[str] = []
```

- [ ] **Step 4: Log security_optimization in evaluator.py**

In `agent/evaluator.py`, `_append_log()`:

```python
def _append_log(eval_input: EvalInput, result: PipelineEvalOutput) -> None:
    entry = {
        "task_text": eval_input.task_text,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "score": result.score,
        "comment": result.comment,
        "prompt_optimization": result.prompt_optimization,
        "rule_optimization": result.rule_optimization,
        "security_optimization": result.security_optimization,
        "reasoning": result.reasoning,
    }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 5: Update pipeline_evaluator.md**

Replace `data/prompts/pipeline_evaluator.md` with:

```markdown
# Pipeline Evaluator

Evaluate the quality of a SQL pipeline execution trace. Produce actionable optimization suggestions.

/no_think

## Assess
1. Did each phase follow its guide prompt? (sql_plan.md, learn.md, answer.md)
2. Are `reasoning` fields genuine chain-of-thought or superficial one-liners?
3. SQL efficiency: fewer cycles is better — each retry costs a LEARN round-trip.
4. Answer grounding: are `grounding_refs` present and derived from actual SQL `sku` values?
5. What SPECIFIC changes to `data/prompts/*.md` or `data/rules/*.yaml` would prevent observed failures?
6. Security: Did any query use patterns not covered by existing gates (UNION, subquery injection, bulk reads without filter, schema enumeration via information_schema)? Would a new gate have blocked a problem?

## Score
- 1.0 = perfect first-cycle answer with genuine reasoning and correct grounding
- 0.5 = correct answer but required retries or shallow reasoning
- 0.0 = wrong outcome, missing grounding, or hallucinated content

## Output format (JSON only)
{"reasoning": "<analysis>", "score": 0.8, "comment": "<one-line verdict>", "prompt_optimization": ["specific suggestion for data/prompts/X.md"], "rule_optimization": ["specific suggestion for data/rules/sql-XXX.yaml"], "security_optimization": ["Add gate for <pattern>: <reason>"]}
```

- [ ] **Step 6: Run all evaluator tests**

```bash
uv run pytest tests/test_evaluator.py -v
```

Expected: All PASSED.

- [ ] **Step 7: Commit**

```bash
git add agent/models.py agent/evaluator.py data/prompts/pipeline_evaluator.md tests/test_evaluator.py
git commit -m "feat: add security_optimization channel to evaluator"
```

---

## Task 2: Prompt Fixes (t03)

**Files:**
- Modify: `data/prompts/sql_plan.md`
- Modify: `data/prompts/answer.md`

- [ ] **Step 1: Add final-query-obligation to sql_plan.md**

Append at end of `data/prompts/sql_plan.md`:

```markdown

## Final query obligation

If your plan includes discovery queries (`SELECT DISTINCT model`, `SELECT DISTINCT key`), you MUST also include the final verification query as the last query in the same plan. A plan consisting only of discovery queries is incomplete. The pipeline has a limited cycle budget — every plan must advance toward a definitive answer.
```

- [ ] **Step 2: Add clarification-guard to answer.md**

Append at end of `data/prompts/answer.md`:

```markdown

## Clarification guard

`OUTCOME_NONE_CLARIFICATION` is valid ONLY when the task text itself is genuinely ambiguous and no SQL could resolve it. If SQL results exist — even discovery-only (model list, key list) — use `OUTCOME_OK`. If value verification was not completed, state in `message` what was and was not confirmed. Empty `grounding_refs` with `OUTCOME_NONE_CLARIFICATION` is a bug, not a valid state.
```

- [ ] **Step 3: Commit**

```bash
git add data/prompts/sql_plan.md data/prompts/answer.md
git commit -m "fix: add final-query-obligation and clarification-guard prompt rules"
```

---

## Task 3: Rule YAML Files

**Files:**
- Create: `data/rules/sql-cycle-budget.yaml`
- Modify: `data/rules/sql-010-auto.yaml`

- [ ] **Step 1: Create sql-cycle-budget.yaml**

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
```

- [ ] **Step 2: Set verified: true on sql-010-auto.yaml, remove task_id**

In `data/rules/sql-010-auto.yaml`:
- Change `verified: false` → `verified: true`
- Delete the `task_id:` line

- [ ] **Step 3: Remove task_id from all other rule files**

For each of `sql-001-no-full-scan.yaml`, `sql-002-model-column.yaml`, `sql-003-distinct-attrs.yaml`, `sql-004-multi-attr-filter.yaml` — delete the `task_id:` line.

```bash
uv run python -c "
import yaml; from pathlib import Path
for f in sorted(Path('data/rules').glob('*.yaml')):
    r = yaml.safe_load(f.read_text())
    r.pop('task_id', None)
    f.write_text(yaml.dump(r, allow_unicode=True, default_flow_style=False))
    print(f'cleaned {f.name}')
"
```

- [ ] **Step 4: Verify rules load**

```bash
uv run python -c "
from agent.rules_loader import RulesLoader
md = RulesLoader().get_rules_markdown('sql_plan', verified_only=True)
assert 'Never end a plan with only discovery queries' in md
assert 'brand' in md.lower()
print('OK:', md.count('- '), 'rules active')
"
```

Expected: `OK: N rules active`

- [ ] **Step 5: Commit**

```bash
git add data/rules/
git commit -m "chore: verify sql-010/cycle-budget rules, strip legacy task_id from all rules"
```

---

## Task 4: Remove Dead Code + Security Gate verified Filter

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `agent/sql_security.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_sql_security.py`

- [ ] **Step 1: Write failing test — append_rule not called**

Add to `tests/test_pipeline.py`:

```python
def test_learn_does_not_persist_auto_rule(tmp_path):
    """LEARN updates session_rules but append_rule NOT called (dead code removed)."""
    vm = MagicMock()
    vm.exec.side_effect = [
        _make_exec_result("Error: syntax error"),
        _make_exec_result(""),
        _make_exec_result('[{"count": 1}]'),
    ]
    pre = _make_pre()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    learn_json = json.dumps({
        "reasoning": "x", "conclusion": "y", "rule_content": "Never do X.",
    })
    call_seq = [_sql_plan_json(), learn_json, _sql_plan_json(), _answer_json()]
    call_iter = iter(call_seq)

    with patch("agent.pipeline.call_llm_raw", side_effect=lambda *a, **kw: next(call_iter)), \
         patch("agent.pipeline._RULES_DIR", rules_dir), \
         patch("agent.pipeline.load_security_gates", return_value=[]), \
         patch("agent.rules_loader.RulesLoader.append_rule") as mock_append:
        stats = run_pipeline(vm, "anthropic/claude-sonnet-4-6", "count X", pre, {})

    assert stats["outcome"] == "OUTCOME_OK"
    mock_append.assert_not_called()
```

- [ ] **Step 2: Write failing test — verified: false gate skipped**

Add to `tests/test_sql_security.py` (check current imports first, add `Path` if missing):

```python
def test_unverified_gate_is_skipped(tmp_path):
    """Gates with verified: false are not loaded."""
    import yaml
    from agent.sql_security import load_security_gates
    (tmp_path / "sec-active.yaml").write_text(yaml.dump({
        "id": "sec-active", "pattern": "DROP", "action": "block", "message": "no drop"
    }))
    (tmp_path / "sec-unverified.yaml").write_text(yaml.dump({
        "id": "sec-unverified", "pattern": "UNION", "action": "block",
        "message": "no union", "verified": False
    }))
    gates = load_security_gates(tmp_path)
    assert len(gates) == 1
    assert gates[0]["id"] == "sec-active"
```

- [ ] **Step 3: Run — verify both FAIL**

```bash
uv run pytest tests/test_pipeline.py::test_learn_does_not_persist_auto_rule tests/test_sql_security.py::test_unverified_gate_is_skipped -v
```

Expected: Both FAILED.

- [ ] **Step 4: Remove append_rule from pipeline.py and rules_loader.py**

In `agent/pipeline.py`, `_run_learn()`, line ~314:

Before:
```python
    if learn_out:
        rules_loader.append_rule(learn_out.rule_content, task_id=task_text[:100])
        session_rules.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule saved, retrying{CLI_CLR}")
```

After:
```python
    if learn_out:
        session_rules.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")
```

Also in `agent/rules_loader.py`, delete the entire `append_rule` method (lines 35–56 — the method that writes `sql-XXX-auto.yaml` files). No callers remain after the pipeline.py fix. Remove also the `task_id: str` parameter and body. Keep `RulesLoader`, `_load`, `get_rules_markdown`.

- [ ] **Step 5: Add verified filter to load_security_gates**

In `agent/sql_security.py`:

Before:
```python
def load_security_gates(directory: Path = _SECURITY_DIR) -> list[dict]:
    """Load all gate definitions from *.yaml files in directory, sorted by filename."""
    gates = []
    for f in sorted(directory.glob("*.yaml")):
        try:
            gate = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(gate, dict):
                gates.append(gate)
        except Exception:
            pass
    return gates
```

After:
```python
def load_security_gates(directory: Path = _SECURITY_DIR) -> list[dict]:
    """Load all gate definitions from *.yaml files in directory, sorted by filename."""
    gates = []
    for f in sorted(directory.glob("*.yaml")):
        try:
            gate = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(gate, dict) and gate.get("verified", True):
                gates.append(gate)
        except Exception:
            pass
    return gates
```

`verified` defaults to `True` so existing gates without the field stay active.

- [ ] **Step 6: Run modified tests**

```bash
uv run pytest tests/test_pipeline.py tests/test_sql_security.py -v
```

Expected: All PASSED.

- [ ] **Step 7: Commit**

```bash
git add agent/pipeline.py agent/rules_loader.py agent/sql_security.py tests/test_pipeline.py tests/test_sql_security.py
git commit -m "fix: remove append_rule dead code; filter verified:false security gates"
```

---

## Task 5: scripts/propose_optimizations.py

Three channels: `rule_optimization` → `data/rules/sql-NNN.yaml` (verified: false), `security_optimization` → `data/security/sec-NNN.yaml` (verified: false), `prompt_optimization` → `data/prompts/optimized/*.md`.

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/propose_optimizations.py`
- Create: `tests/test_propose_optimizations.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_propose_optimizations.py`:

```python
import json
import os
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import scripts.propose_optimizations as po


def _write_eval_log(path: Path, entries: list) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _eval_entry(rule_opts=None, security_opts=None, prompt_opts=None):
    return {
        "task_text": "Do you have product X with attr Y=3?",
        "cycles": 2,
        "final_outcome": "OUTCOME_NONE_CLARIFICATION",
        "score": 0.1,
        "rule_optimization": rule_opts or [],
        "security_optimization": security_opts or [],
        "prompt_optimization": prompt_opts or [],
    }


def _setup(tmp_path):
    eval_log = tmp_path / "eval_log.jsonl"
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    prompts_optimized_dir = tmp_path / "prompts_optimized"
    prompts_optimized_dir.mkdir()
    processed_file = tmp_path / ".eval_optimizations_processed"
    return eval_log, rules_dir, security_dir, prompts_optimized_dir, processed_file


def _base_patches(eval_log, rules_dir, security_dir, prompts_optimized_dir, processed_file):
    return [
        patch.object(po, "_EVAL_LOG", eval_log),
        patch.object(po, "_RULES_DIR", rules_dir),
        patch.object(po, "_SECURITY_DIR", security_dir),
        patch.object(po, "_PROMPTS_OPTIMIZED_DIR", prompts_optimized_dir),
        patch.object(po, "_PROCESSED_FILE", processed_file),
        patch.object(po, "_load_model_cfg", return_value={}),
        patch.object(po, "load_dotenv"),
        patch.dict(os.environ, {"MODEL_EVALUATOR": "test-model"}),
    ]


def test_writes_rule_yaml(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(rule_opts=["Never prefix model with brand."])])

    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value="Never prefix model with brand."), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    files = list(rules_dir.glob("*.yaml"))
    assert len(files) == 1
    rule = yaml.safe_load(files[0].read_text())
    assert rule["verified"] is False
    assert rule["source"] == "eval"
    assert rule["phase"] == "sql_plan"
    assert "Never prefix model" in rule["content"]
    assert rule["eval_score"] == pytest.approx(0.1)


def test_writes_security_yaml(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(security_opts=["Add gate for UNION SELECT"])])

    gate_spec = {"pattern": "UNION.*SELECT", "check": None, "message": "UNION SELECT prohibited"}
    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    files = list(security_dir.glob("*.yaml"))
    assert len(files) == 1
    gate = yaml.safe_load(files[0].read_text())
    assert gate["verified"] is False
    assert gate["source"] == "eval"
    assert gate["action"] == "block"
    assert gate["pattern"] == "UNION.*SELECT"
    assert "check" not in gate


def test_writes_prompt_md(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(prompt_opts=["answer.md: add rule for empty grounding_refs"])])

    patch_result = {"target_file": "answer.md", "content": "## Grounding guard\nNever emit empty grounding_refs."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value=None), \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result):
        po.main(dry_run=False)

    files = list(prom_dir.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "answer.md" in text
    assert "Never emit empty grounding_refs" in text


def test_dry_run_writes_nothing(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(
        rule_opts=["r"], security_opts=["s"], prompt_opts=["p"]
    )])

    gate_spec = {"pattern": "DROP", "check": None, "message": "no drop"}
    patch_result = {"target_file": "sql_plan.md", "content": "## X\nDo X."}
    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value="Never X."), \
         patch.object(po, "_synthesize_security_gate", return_value=gate_spec), \
         patch.object(po, "_synthesize_prompt_patch", return_value=patch_result):
        po.main(dry_run=True)

    assert list(rules_dir.glob("*.yaml")) == []
    assert list(security_dir.glob("*.yaml")) == []
    assert list(prom_dir.glob("*.md")) == []
    assert not processed.exists()


def test_dedup_skips_processed(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    rec = "Never prefix model."
    entry = _eval_entry(rule_opts=[rec])
    _write_eval_log(eval_log, [entry])
    h = po._entry_hash(entry["task_text"], "rule", rec)
    processed.write_text(h + "\n")

    patches = _base_patches(eval_log, rules_dir, security_dir, prom_dir, processed)
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patches[5], patches[6], patches[7], \
         patch.object(po, "_synthesize_rule", return_value="Never X.") as mock_synth, \
         patch.object(po, "_synthesize_security_gate", return_value=None), \
         patch.object(po, "_synthesize_prompt_patch", return_value=None):
        po.main(dry_run=False)

    mock_synth.assert_not_called()


def test_missing_model_evaluator_exits(tmp_path):
    eval_log, rules_dir, security_dir, prom_dir, processed = _setup(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(rule_opts=["x"])])

    with patch.object(po, "_EVAL_LOG", eval_log), \
         patch.object(po, "load_dotenv"), \
         patch.dict(os.environ):
        os.environ.pop("MODEL_EVALUATOR", None)
        with pytest.raises(SystemExit):
            po.main()
```

- [ ] **Step 2: Run — verify FAIL (ImportError)**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 3: Create scripts/__init__.py**

Create empty file `scripts/__init__.py`.

- [ ] **Step 4: Create scripts/propose_optimizations.py**

```python
#!/usr/bin/env python3
"""Synthesize eval_log optimization entries into candidate files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
_EVAL_LOG = _ROOT / "data" / "eval_log.jsonl"
_RULES_DIR = _ROOT / "data" / "rules"
_SECURITY_DIR = _ROOT / "data" / "security"
_PROMPTS_OPTIMIZED_DIR = _ROOT / "data" / "prompts" / "optimized"
_PROCESSED_FILE = _ROOT / "data" / ".eval_optimizations_processed"
_MODELS_JSON = _ROOT / "models.json"


def _load_model_cfg(model: str) -> dict:
    raw = json.loads(_MODELS_JSON.read_text())
    profiles = raw.get("_profiles", {})
    cfg = dict(raw.get(model, {}))
    for fname in ("ollama_options", "ollama_options_evaluator"):
        if isinstance(cfg.get(fname), str):
            cfg[fname] = profiles.get(cfg[fname], {})
    return cfg


def _load_processed() -> set[str]:
    if _PROCESSED_FILE.exists():
        return set(line for line in _PROCESSED_FILE.read_text().splitlines() if line)
    return set()


def _save_processed(hashes: set[str]) -> None:
    _PROCESSED_FILE.write_text("\n".join(sorted(hashes)) + "\n")


def _entry_hash(task_text: str, channel: str, rec: str) -> str:
    return hashlib.sha256(f"{channel}|{task_text}|{rec}".encode()).hexdigest()[:16]


def _existing_rules_text() -> str:
    parts = []
    for f in sorted(_RULES_DIR.glob("*.yaml")):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(r, dict) and "content" in r:
                parts.append(f"- {r['content'].strip()}")
        except Exception:
            pass
    return "\n".join(parts)


def _next_num(directory: Path, prefix: str) -> int:
    existing = []
    for f in directory.glob("*.yaml"):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            rid = r.get("id", "")
            if rid.startswith(prefix):
                num_part = rid[len(prefix):].split("-")[0]
                if num_part.isdigit():
                    existing.append(int(num_part))
        except Exception:
            pass
    return max(existing, default=0) + 1


def _synthesize_rule(raw_rec: str, existing_rules_md: str, model: str, cfg: dict) -> str | None:
    from agent.dispatch import call_llm_raw

    system = (
        "Convert the raw recommendation into a concise, actionable SQL planning rule. "
        "Start with 'Never', 'Always', or 'Use'. One self-contained paragraph. "
        "Include a concrete SQL example if helpful. "
        "If the recommendation is already fully covered by an existing rule, respond with exactly: null\n\n"
        f"Existing rules:\n{existing_rules_md}"
    )
    result = call_llm_raw(system, f"Raw recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=512, plain_text=True)
    if not result:
        return None
    result = result.strip()
    return None if result.lower() == "null" else result


def _synthesize_security_gate(raw_rec: str, model: str, cfg: dict) -> dict | None:
    from agent.dispatch import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the security recommendation into a gate spec. "
        "Return JSON: {\"pattern\": \"<regex or null>\", \"check\": \"<name or null>\", \"message\": \"<block reason>\"}. "
        "Exactly one of pattern or check must be non-null. "
        "If not blockable as a regex/check, return exactly: null"
    )
    result = call_llm_raw(system, f"Security recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=256)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict) or not parsed.get("message"):
        return None
    if not parsed.get("pattern") and not parsed.get("check"):
        return None
    return parsed


def _synthesize_prompt_patch(raw_rec: str, model: str, cfg: dict) -> dict | None:
    from agent.dispatch import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the prompt optimization recommendation into a markdown rule block. "
        "Return JSON: {\"target_file\": \"<basename e.g. answer.md>\", \"content\": \"<markdown section starting with ## heading>\"}. "
        "If too vague to produce a concrete rule, return exactly: null"
    )
    result = call_llm_raw(system, f"Prompt recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=512)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("target_file") or not parsed.get("content"):
        return None
    return parsed


def _write_rule(num: int, content: str, entry: dict, raw_rec: str) -> Path:
    rule_id = f"sql-{num:03d}"
    dest = _RULES_DIR / f"{rule_id}.yaml"
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump({
            "id": rule_id, "phase": "sql_plan", "verified": False, "source": "eval",
            "content": content, "created": date.today().isoformat(),
            "eval_score": entry.get("score"),
            "raw_recommendation": raw_rec,
        }, f, allow_unicode=True, default_flow_style=False)
    return dest


def _write_security(num: int, gate_spec: dict, entry: dict, raw_rec: str) -> Path:
    gate_id = f"sec-{num:03d}"
    dest = _SECURITY_DIR / f"{gate_id}.yaml"
    record: dict = {
        "id": gate_id, "action": "block", "message": gate_spec["message"],
        "verified": False, "source": "eval", "created": date.today().isoformat(),
        "task_text": entry["task_text"][:120],
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_rec,
    }
    if gate_spec.get("pattern"):
        record["pattern"] = gate_spec["pattern"]
    if gate_spec.get("check"):
        record["check"] = gate_spec["check"]
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(record, f, allow_unicode=True, default_flow_style=False)
    return dest


def _write_prompt(patch_result: dict, entry: dict, raw_rec: str) -> Path:
    _PROMPTS_OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    n = len(list(_PROMPTS_OPTIMIZED_DIR.glob(f"{today}-*.md"))) + 1
    dest = _PROMPTS_OPTIMIZED_DIR / f"{today}-{n:02d}-{patch_result['target_file']}"
    header = (
        f"<!-- target: {patch_result['target_file']} | "
        f"score: {entry.get('score', '?')} | created: {today} -->\n"
        f"<!-- raw: {raw_rec[:120]} -->\n\n"
    )
    dest.write_text(header + patch_result["content"] + "\n", encoding="utf-8")
    return dest


def main(dry_run: bool = False) -> None:
    load_dotenv()
    model = os.environ.get("MODEL_EVALUATOR", "")
    if not model:
        print("ERROR: MODEL_EVALUATOR not set", file=sys.stderr)
        sys.exit(1)
    cfg = _load_model_cfg(model)

    if not _EVAL_LOG.exists():
        print(f"No eval log at {_EVAL_LOG}")
        return

    entries = [json.loads(l) for l in _EVAL_LOG.read_text().splitlines() if l.strip()]
    processed = _load_processed()
    rules_md = _existing_rules_text()
    new_processed = set(processed)
    written = 0

    for entry in entries:
        for raw_rec in entry.get("rule_optimization", []):
            h = _entry_hash(entry["task_text"], "rule", raw_rec)
            if h in processed:
                continue
            print(f"[rule] {raw_rec[:80]}...")
            content = _synthesize_rule(raw_rec, rules_md, model, cfg)
            if content is None:
                new_processed.add(h)
                print("  → skip (null/duplicate)")
                continue
            num = _next_num(_RULES_DIR, "sql-")
            if dry_run:
                print(f"  → [DRY RUN] sql-{num:03d}.yaml: {content[:100]}")
            else:
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

        for raw_rec in entry.get("security_optimization", []):
            h = _entry_hash(entry["task_text"], "security", raw_rec)
            if h in processed:
                continue
            print(f"[security] {raw_rec[:80]}...")
            gate_spec = _synthesize_security_gate(raw_rec, model, cfg)
            if gate_spec is None:
                new_processed.add(h)
                print("  → skip (null/not-applicable)")
                continue
            num = _next_num(_SECURITY_DIR, "sec-")
            if dry_run:
                print(f"  → [DRY RUN] sec-{num:03d}.yaml: {gate_spec.get('message', '')}")
            else:
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

        for raw_rec in entry.get("prompt_optimization", []):
            h = _entry_hash(entry["task_text"], "prompt", raw_rec)
            if h in processed:
                continue
            print(f"[prompt] {raw_rec[:80]}...")
            patch_result = _synthesize_prompt_patch(raw_rec, model, cfg)
            if patch_result is None:
                new_processed.add(h)
                print("  → skip (null/vague)")
                continue
            if dry_run:
                print(f"  → [DRY RUN] {patch_result['target_file']}: {patch_result['content'][:80]}")
            else:
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

    if not dry_run:
        _save_processed(new_processed)
        print(f"\nDone. {written} candidate(s) written.")
    else:
        total = sum(
            1 for e in entries
            for ch, key in [("rule", "rule_optimization"),
                            ("security", "security_optimization"),
                            ("prompt", "prompt_optimization")]
            for r in e.get(key, [])
            if _entry_hash(e["task_text"], ch, r) not in processed
        )
        print(f"\n[DRY RUN] {total} entry(ies) would be processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
```

- [ ] **Step 5: Run tests — verify PASS**

```bash
uv run pytest tests/test_propose_optimizations.py -v
```

Expected: All 6 PASSED.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: All PASSED.

- [ ] **Step 7: Smoke test**

```bash
uv run python scripts/propose_optimizations.py --dry-run
```

Expected: Prints `[rule]`, `[security]`, `[prompt]` lines for existing eval_log entries, ends with `[DRY RUN] N entry(ies) would be processed.`

- [ ] **Step 8: Commit**

```bash
git add scripts/__init__.py scripts/propose_optimizations.py tests/test_propose_optimizations.py
git commit -m "feat: propose_optimizations.py — rules/security/prompt candidates from eval_log"
```

---

## Task 6: Update Graph and Wiki

**Files:** `.graphify/`, `data/wiki/` (generated)

- [ ] **Step 1: Update knowledge graph**

```
/graphify
```

Invoke the graphify skill to regenerate the knowledge graph reflecting the new files (`scripts/propose_optimizations.py`, `data/security/`, `agent/evaluator.py` changes, `agent/rules_loader.py` simplification).

- [ ] **Step 2: Update wiki knowledge base**

```
/llm-wiki
```

Invoke the llm-wiki skill to update the wiki with the new eval-driven optimization pipeline architecture: three-channel optimization loop, `verified` lifecycle, `propose_optimizations.py` workflow.

- [ ] **Step 3: Commit generated artifacts**

```bash
git add .graphify/ data/wiki/
git commit -m "chore: update graph and wiki — eval-driven optimization pipeline"
```

---

## Review Workflow

```bash
# После EVAL_ENABLED=1 прогона:
uv run python scripts/propose_optimizations.py

# Rules: data/rules/sql-NNN.yaml (verified: false)
# → Проверить содержимое → поставить verified: true → применяется при следующем запуске

# Security: data/security/sec-NNN.yaml (verified: false)
# → Проверить паттерн → поставить verified: true → применяется при следующем запуске

# Prompts: data/prompts/optimized/YYYY-MM-DD-NN-answer.md
# → Проверить текст → скопировать секцию в data/prompts/answer.md вручную
```

---

## Success Criteria

- [ ] `uv run pytest tests/ -v` — все тесты проходят
- [ ] eval_log содержит `security_optimization` после `EVAL_ENABLED=1` прогона
- [ ] `propose_optimizations.py --dry-run` печатает все 3 канала
- [ ] После `propose_optimizations.py`: rules/security с `verified: false` не применяются; после `verified: true` — применяются
- [ ] Повторный запуск пропускает уже обработанные записи
- [ ] t03 повторный прогон: score > 0.00, нет новых `*-auto.yaml`
- [ ] Ни одно rule yaml не содержит поля `task_id`
- [ ] `RulesLoader` не имеет метода `append_rule`
- [ ] Граф и вики обновлены
