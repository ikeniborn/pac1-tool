"""Tests for contract distillation script."""
import json
import pytest
from pathlib import Path


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
            "is_default": False,
            "rounds_taken": 1,
        },
        "is_default": False,
        "rounds_taken": 1,
        "score": score,
        "stall_detected": False,
        "write_scope_violations": False,
    }


def test_distill_selects_top_n_plan_steps(tmp_path):
    """Most frequent plan_steps are selected, up to 6."""
    from scripts.distill_contracts import distill_task_type

    common = ["search /contacts", "read /contacts/alice.json", "write /outbox/1.json"]
    rare = ["list /archive"]
    examples = [_make_email_example(plan_steps=common) for _ in range(5)]
    examples.append(_make_email_example(plan_steps=common + rare))

    result = distill_task_type(examples, min_examples=5)
    assert "search /contacts" in result["plan_steps"]
    assert "write /outbox/1.json" in result["plan_steps"]
    assert len(result["plan_steps"]) <= 6


def test_distill_skips_low_score(tmp_path):
    """Examples with score < 1.0 are excluded."""
    from scripts.distill_contracts import distill_task_type

    examples = [
        _make_email_example(plan_steps=["step-good"], score=1.0),
        _make_email_example(plan_steps=["step-bad"], score=0.5),
    ]
    result = distill_task_type(examples, min_examples=1)
    assert "step-good" in result["plan_steps"]
    assert not any("step-bad" in s for s in result["plan_steps"])


def test_distill_returns_none_below_min_examples(tmp_path):
    """Fewer than min_examples good examples → returns None (skip)."""
    from scripts.distill_contracts import distill_task_type

    examples = [_make_email_example() for _ in range(3)]
    result = distill_task_type(examples, min_examples=10)
    assert result is None


def test_distill_apply_writes_file(tmp_path):
    """--apply writes data/default_contracts/{task_type}.json."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.distill_contracts import run_distillation

    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()
    # Write existing default.json (must not be overwritten)
    (contracts_dir / "default.json").write_text('{"plan_steps":["default"]}')

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distillation(
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=True,
        min_examples=5,
        task_type_filter=None,
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
    """Without --apply, no files are written."""
    from scripts.distill_contracts import run_distillation

    examples_path = tmp_path / "dspy_contract_examples.jsonl"
    contracts_dir = tmp_path / "default_contracts"
    contracts_dir.mkdir()

    examples = [_make_email_example() for _ in range(10)]
    _write_examples(examples_path, examples)

    run_distillation(
        examples_path=examples_path,
        contracts_dir=contracts_dir,
        apply=False,
        min_examples=5,
        task_type_filter=None,
    )

    assert not (contracts_dir / "email.json").exists()
