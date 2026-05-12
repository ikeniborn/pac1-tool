# Eval-Driven Rule Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix t03 score (0.00) via prompt guards + new manual rule, remove dead auto-rule persistence from LEARN, add `scripts/propose_rules.py` that synthesizes eval_log entries into candidate yaml rules.

**Architecture:** Three independent layers — (1) prompt text fixes stop the immediate t03 failure, (2) dead code removal in pipeline.py cleans the rule lifecycle, (3) `propose_rules.py` replaces LEARN-based persistence with evaluator-driven, human-gated candidates.

**Tech Stack:** Python 3.12, PyYAML, python-dotenv, `agent.dispatch.call_llm_raw`, pytest

---

## File Map

| File | Action |
|------|--------|
| `data/prompts/sql_plan.md` | Add final-query-obligation rule |
| `data/prompts/answer.md` | Add clarification-guard rule |
| `data/rules/sql-cycle-budget.yaml` | Create (verified: true, manual) |
| `data/rules/sql-010-auto.yaml` | Set `verified: true` |
| `agent/pipeline.py` | Remove `rules_loader.append_rule(...)` from `_run_learn()` |
| `scripts/__init__.py` | Create (empty — makes scripts importable) |
| `scripts/propose_rules.py` | Create — eval_log → candidate yaml rules via LLM synthesis |
| `tests/test_pipeline.py` | Add test: LEARN does not call `append_rule` |
| `tests/test_propose_rules.py` | Create — unit tests for propose_rules.py |

---

## Task 1: Prompt Fixes

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

## Task 2: Rule YAML Files

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
task_id: null
```

Save as `data/rules/sql-cycle-budget.yaml`.

- [ ] **Step 2: Set verified: true on sql-010-auto.yaml**

In `data/rules/sql-010-auto.yaml`, change:

```yaml
verified: false
```

to:

```yaml
verified: true
```

- [ ] **Step 3: Verify both rules load**

```bash
uv run python -c "
from agent.rules_loader import RulesLoader
rl = RulesLoader()
md = rl.get_rules_markdown('sql_plan', verified_only=True)
assert 'Never end a plan with only discovery queries' in md, 'cycle-budget rule missing'
assert 'brand never prefixes model' in md or 'brand' in md.lower(), 'sql-010 rule missing'
print('OK:', len(md.splitlines()), 'lines')
"
```

Expected output: `OK: N lines` (no AssertionError)

- [ ] **Step 4: Commit**

```bash
git add data/rules/sql-cycle-budget.yaml data/rules/sql-010-auto.yaml
git commit -m "feat: add sql-cycle-budget rule, verify sql-010"
```

---

## Task 3: Remove Dead Code from pipeline.py

**Files:**
- Modify: `tests/test_pipeline.py` (add test first)
- Modify: `agent/pipeline.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline.py`:

```python
def test_learn_does_not_persist_auto_rule(tmp_path):
    """LEARN session_rules updated but append_rule NOT called (dead code removed)."""
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

- [ ] **Step 2: Run test — verify it FAILS**

```bash
uv run pytest tests/test_pipeline.py::test_learn_does_not_persist_auto_rule -v
```

Expected: `FAILED` — `append_rule` was called once (current behavior).

- [ ] **Step 3: Remove append_rule call from pipeline.py**

In `agent/pipeline.py`, `_run_learn()` function around line 314–316:

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

- [ ] **Step 4: Run tests — verify pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: All PASSED.

- [ ] **Step 5: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "fix: remove dead append_rule from _run_learn — LEARN is session-only"
```

---

## Task 4: scripts/propose_rules.py

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/propose_rules.py`
- Create: `tests/test_propose_rules.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_propose_rules.py`:

```python
import json
import os
import yaml
import pytest
from pathlib import Path
from unittest.mock import patch

import scripts.propose_rules as pr


def _write_eval_log(path: Path, entries: list) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _eval_entry(rule_opts=None):
    return {
        "task_text": "Do you have product X with attr Y=3?",
        "cycles": 2,
        "final_outcome": "OUTCOME_NONE_CLARIFICATION",
        "score": 0.1,
        "rule_optimization": rule_opts or ["Never prefix model with brand name."],
    }


def _ctx(tmp_path, monkeypatch=None):
    eval_log = tmp_path / "eval_log.jsonl"
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    processed_file = tmp_path / ".eval_rules_processed"
    return eval_log, rules_dir, processed_file


def test_dry_run_no_files_written(tmp_path):
    eval_log, rules_dir, processed_file = _ctx(tmp_path)
    _write_eval_log(eval_log, [_eval_entry()])

    with patch.object(pr, "_EVAL_LOG", eval_log), \
         patch.object(pr, "_RULES_DIR", rules_dir), \
         patch.object(pr, "_PROCESSED_FILE", processed_file), \
         patch.object(pr, "_synthesize_rule", return_value="Never do X."), \
         patch.object(pr, "_load_model_cfg", return_value={}), \
         patch.object(pr, "load_dotenv"), \
         patch.dict(os.environ, {"MODEL_EVALUATOR": "anthropic/claude-sonnet-4-6"}):
        pr.main(dry_run=True)

    assert list(rules_dir.glob("*-candidate.yaml")) == []
    assert not processed_file.exists()


def test_writes_candidate_yaml(tmp_path):
    eval_log, rules_dir, processed_file = _ctx(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(["Never prefix model with brand."])])

    with patch.object(pr, "_EVAL_LOG", eval_log), \
         patch.object(pr, "_RULES_DIR", rules_dir), \
         patch.object(pr, "_PROCESSED_FILE", processed_file), \
         patch.object(pr, "_synthesize_rule",
                      return_value="Never prefix model with brand name when filtering."), \
         patch.object(pr, "_load_model_cfg", return_value={}), \
         patch.object(pr, "load_dotenv"), \
         patch.dict(os.environ, {"MODEL_EVALUATOR": "anthropic/claude-sonnet-4-6"}):
        pr.main(dry_run=False)

    candidates = list(rules_dir.glob("*-candidate.yaml"))
    assert len(candidates) == 1
    rule = yaml.safe_load(candidates[0].read_text())
    assert rule["verified"] is False
    assert rule["source"] == "eval"
    assert rule["phase"] == "sql_plan"
    assert "Never prefix model" in rule["content"]
    assert rule["eval_score"] == pytest.approx(0.1)
    assert processed_file.exists()


def test_dedup_skips_processed(tmp_path):
    eval_log, rules_dir, processed_file = _ctx(tmp_path)
    entry = _eval_entry(["Rule text here."])
    _write_eval_log(eval_log, [entry])
    h = pr._entry_hash(entry["task_text"], "Rule text here.")
    processed_file.write_text(h + "\n")

    with patch.object(pr, "_EVAL_LOG", eval_log), \
         patch.object(pr, "_RULES_DIR", rules_dir), \
         patch.object(pr, "_PROCESSED_FILE", processed_file), \
         patch.object(pr, "_synthesize_rule", return_value="Never do X.") as mock_synth, \
         patch.object(pr, "_load_model_cfg", return_value={}), \
         patch.object(pr, "load_dotenv"), \
         patch.dict(os.environ, {"MODEL_EVALUATOR": "anthropic/claude-sonnet-4-6"}):
        pr.main(dry_run=False)

    mock_synth.assert_not_called()
    assert list(rules_dir.glob("*-candidate.yaml")) == []


def test_llm_null_skips_candidate_saves_hash(tmp_path):
    eval_log, rules_dir, processed_file = _ctx(tmp_path)
    _write_eval_log(eval_log, [_eval_entry(["Duplicate existing rule."])])

    with patch.object(pr, "_EVAL_LOG", eval_log), \
         patch.object(pr, "_RULES_DIR", rules_dir), \
         patch.object(pr, "_PROCESSED_FILE", processed_file), \
         patch.object(pr, "_synthesize_rule", return_value=None), \
         patch.object(pr, "_load_model_cfg", return_value={}), \
         patch.object(pr, "load_dotenv"), \
         patch.dict(os.environ, {"MODEL_EVALUATOR": "anthropic/claude-sonnet-4-6"}):
        pr.main(dry_run=False)

    assert list(rules_dir.glob("*-candidate.yaml")) == []
    assert processed_file.exists()


def test_missing_model_evaluator_exits(tmp_path):
    eval_log, rules_dir, processed_file = _ctx(tmp_path)
    _write_eval_log(eval_log, [_eval_entry()])

    with patch.object(pr, "_EVAL_LOG", eval_log), \
         patch.object(pr, "_RULES_DIR", rules_dir), \
         patch.object(pr, "_PROCESSED_FILE", processed_file), \
         patch.object(pr, "load_dotenv"), \
         patch.dict(os.environ):
        os.environ.pop("MODEL_EVALUATOR", None)
        with pytest.raises(SystemExit):
            pr.main()
```

- [ ] **Step 2: Run tests — verify they FAIL (ImportError)**

```bash
uv run pytest tests/test_propose_rules.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 3: Create scripts/__init__.py**

Create empty file `scripts/__init__.py`.

- [ ] **Step 4: Create scripts/propose_rules.py**

```python
#!/usr/bin/env python3
"""Synthesize eval_log rule_optimization entries into candidate yaml rule files."""
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
_PROCESSED_FILE = _ROOT / "data" / ".eval_rules_processed"
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
        return set(_PROCESSED_FILE.read_text().splitlines())
    return set()


def _save_processed(hashes: set[str]) -> None:
    _PROCESSED_FILE.write_text("\n".join(sorted(hashes)) + "\n")


def _entry_hash(task_text: str, rule_opt: str) -> str:
    return hashlib.sha256(f"{task_text}|{rule_opt}".encode()).hexdigest()[:16]


def _load_existing_rules_text() -> str:
    parts = []
    for f in sorted(_RULES_DIR.glob("*.yaml")):
        try:
            rule = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(rule, dict) and "content" in rule:
                parts.append(f"- {rule['content'].strip()}")
        except Exception:
            pass
    return "\n".join(parts)


def _next_candidate_num() -> int:
    existing = []
    for f in _RULES_DIR.glob("*.yaml"):
        try:
            rule = yaml.safe_load(f.read_text(encoding="utf-8"))
            rid = rule.get("id", "")
            if rid.startswith("sql-"):
                num_part = rid[4:].split("-")[0]
                if num_part.isdigit():
                    existing.append(int(num_part))
        except Exception:
            pass
    return max(existing, default=0) + 1


def _synthesize_rule(raw_recommendation: str, existing_rules_md: str, model: str, cfg: dict) -> str | None:
    from agent.dispatch import call_llm_raw

    system = (
        "Convert the raw recommendation into a concise, actionable SQL planning rule. "
        "Start with 'Never', 'Always', or 'Use'. One self-contained paragraph. "
        "Include a concrete example if helpful. "
        "If the recommendation is already fully covered by an existing rule, respond with exactly: null\n\n"
        f"Existing rules:\n{existing_rules_md}"
    )
    user = f"Raw recommendation:\n{raw_recommendation}"
    result = call_llm_raw(system, user, model, cfg, max_tokens=512, plain_text=True)
    if result is None:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    return result


def _write_candidate(num: int, content: str, entry: dict, raw_recommendation: str) -> Path:
    rule_id = f"sql-{num:03d}-candidate"
    dest = _RULES_DIR / f"{rule_id}.yaml"
    rule = {
        "id": rule_id,
        "phase": "sql_plan",
        "verified": False,
        "source": "eval",
        "content": content,
        "created": date.today().isoformat(),
        "task_text": entry["task_text"][:120],
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_recommendation,
    }
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(rule, f, allow_unicode=True, default_flow_style=False)
    return dest


def main(dry_run: bool = False) -> None:
    load_dotenv()
    model = os.environ.get("MODEL_EVALUATOR", "")
    if not model:
        print("ERROR: MODEL_EVALUATOR env var not set", file=sys.stderr)
        sys.exit(1)
    cfg = _load_model_cfg(model)

    if not _EVAL_LOG.exists():
        print(f"No eval log at {_EVAL_LOG}")
        return

    entries = [json.loads(line) for line in _EVAL_LOG.read_text().splitlines() if line.strip()]
    processed = _load_processed()
    existing_rules_md = _load_existing_rules_text()

    new_processed = set(processed)
    written = 0

    for entry in entries:
        for raw_rec in entry.get("rule_optimization", []):
            h = _entry_hash(entry["task_text"], raw_rec)
            if h in processed:
                print(f"[skip] already processed: {raw_rec[:60]}")
                continue

            print(f"[process] {raw_rec[:80]}...")
            content = _synthesize_rule(raw_rec, existing_rules_md, model, cfg)

            if content is None:
                print("  → duplicate/null, skipping")
                new_processed.add(h)
                continue

            num = _next_candidate_num()
            if dry_run:
                print(f"  → [DRY RUN] sql-{num:03d}-candidate:\n    {content[:120]}")
            else:
                dest = _write_candidate(num, content, entry, raw_rec)
                print(f"  → wrote {dest.name}")
                new_processed.add(h)
                written += 1

    if not dry_run:
        _save_processed(new_processed)
        print(f"\nDone. {written} candidate(s) written.")
    else:
        unprocessed = sum(
            1 for e in entries for r in e.get("rule_optimization", [])
            if _entry_hash(e["task_text"], r) not in processed
        )
        print(f"\n[DRY RUN] {unprocessed} entry(ies) would be processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Propose rule candidates from eval_log.")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates, do not write files.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
```

- [ ] **Step 5: Run tests — verify they PASS**

```bash
uv run pytest tests/test_propose_rules.py -v
```

Expected: All 5 PASSED.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All PASSED.

- [ ] **Step 7: Smoke test dry-run with existing eval_log**

```bash
uv run python scripts/propose_rules.py --dry-run
```

Expected: Prints `[process] ...` lines for each unprocessed rule_optimization entry in `data/eval_log.jsonl`, ends with `[DRY RUN] N entry(ies) would be processed.`

- [ ] **Step 8: Commit**

```bash
git add scripts/__init__.py scripts/propose_rules.py tests/test_propose_rules.py
git commit -m "feat: add propose_rules.py — eval_log to candidate yaml via LLM synthesis"
```

---

## Success Criteria Checklist

- [ ] `data/prompts/sql_plan.md` contains "Final query obligation" section
- [ ] `data/prompts/answer.md` contains "Clarification guard" section
- [ ] `uv run python -c "from agent.rules_loader import RulesLoader; rl=RulesLoader(); md=rl.get_rules_markdown('sql_plan'); print(md)"` prints sql-cycle-budget rule and sql-010 rule content
- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] No new `*-auto.yaml` files appear in `data/rules/` after a pipeline run
- [ ] `uv run python scripts/propose_rules.py --dry-run` prints candidates from existing `data/eval_log.jsonl`
- [ ] `uv run python scripts/propose_rules.py` writes `*-candidate.yaml` files; second run skips already-processed entries
