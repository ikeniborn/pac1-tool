"""Regression tests for contract distillation (FIX-377, migrated to agent/maintenance/distill.py — FIX-427)."""
import json
from pathlib import Path

from agent.maintenance.distill import run_distill


def _write_examples(path: Path, examples: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for ex in examples:
            fh.write(json.dumps(ex) + "\n")


def _make_email_example(plan_steps=None, success_criteria=None, score=1.0):
    return {
        "task_text": "Send email to alice",
        "task_type": "email",
        "rounds": [],
        "final_contract": {
            "plan_steps": plan_steps or ["search /contacts", "write /outbox/1.json"],
            "success_criteria": success_criteria or ["file written to /outbox/"],
            "required_evidence": ["/outbox/1.json"],
            "failure_conditions": ["no write to /outbox/"],
        },
        "is_default": False,
        "rounds_taken": 1,
        "score": score,
        "stall_detected": False,
        "write_scope_violations": False,
    }


def test_distill_selects_top_n_plan_steps(tmp_path):
    """Most frequent plan_steps are selected, up to 6."""
    common = ["search /contacts", "read /contacts/alice.json", "write /outbox/1.json"]
    rare = ["list /archive"]
    examples = [_make_email_example(plan_steps=common) for _ in range(5)]
    examples.append(_make_email_example(plan_steps=common + rare))

    ex_path = tmp_path / "examples.jsonl"
    _write_examples(ex_path, examples)
    result = run_distill(min_examples=5, examples_path=ex_path, contracts_dir=tmp_path / "c", apply=True)
    data = json.loads((tmp_path / "c" / "email.json").read_text())
    assert "search /contacts" in data["plan_steps"]
    assert "write /outbox/1.json" in data["plan_steps"]
    assert len(data["plan_steps"]) <= 6


def test_distill_skips_low_score(tmp_path):
    """Examples with score < 1.0 are excluded."""
    examples = [
        _make_email_example(plan_steps=["step-good"], score=1.0),
        _make_email_example(plan_steps=["step-bad"], score=0.5),
    ]
    ex_path = tmp_path / "examples.jsonl"
    _write_examples(ex_path, examples)
    result = run_distill(min_examples=1, examples_path=ex_path, contracts_dir=tmp_path / "c", apply=True)
    data = json.loads((tmp_path / "c" / "email.json").read_text())
    assert "step-good" in data["plan_steps"]
    assert not any("step-bad" in s for s in data["plan_steps"])


def test_distill_returns_none_below_min_examples(tmp_path):
    """Fewer than min_examples good examples → type skipped."""
    examples = [_make_email_example() for _ in range(3)]
    ex_path = tmp_path / "examples.jsonl"
    _write_examples(ex_path, examples)
    result = run_distill(min_examples=10, examples_path=ex_path, contracts_dir=tmp_path / "c", apply=True)
    assert "email" in result.types_skipped
    assert "email" not in result.types_processed


def test_distill_apply_writes_file(tmp_path):
    """apply=True writes data/default_contracts/{task_type}.json."""
    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()
    # Write existing default.json (must not be overwritten)
    (contracts_dir / "default.json").write_text('{"plan_steps":["default"]}')

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distill(
        min_examples=5,
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=True,
    )

    email_file = contracts_dir / "email.json"
    assert email_file.exists()
    data = json.loads(email_file.read_text())
    assert "plan_steps" in data
    assert "success_criteria" in data
    # default.json untouched
    default_data = json.loads((contracts_dir / "default.json").read_text())
    assert default_data["plan_steps"] == ["default"]


def test_distill_dry_run_no_files_written(tmp_path):
    """apply=False, no files are written."""
    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distill(
        min_examples=5,
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=False,
    )

    assert not (contracts_dir / "email.json").exists()


def test_distill_apply_skips_default_type(tmp_path):
    """task_type='default' is never written even with apply=True."""
    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()
    (contracts_dir / "default.json").write_text('{"plan_steps":["fallback"]}')

    examples = []
    for _ in range(10):
        examples.append({
            "task_text": "task",
            "task_type": "default",
            "final_contract": {
                "plan_steps": ["step1"],
                "success_criteria": ["done"],
                "required_evidence": [],
                "failure_conditions": [],
            },
            "is_default": False,
            "score": 1.0,
        })
    examples_path.write_text("\n".join(json.dumps(e) for e in examples) + "\n")

    run_distill(
        min_examples=5,
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=True,
    )

    # default.json must be unchanged
    data = json.loads((contracts_dir / "default.json").read_text())
    assert data["plan_steps"] == ["fallback"]
