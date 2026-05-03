import json
import pytest
from pathlib import Path
from agent.maintenance.distill import run_distill, DistillResult


def _write_examples(path: Path, task_type: str, count: int, score: float = 1.0) -> None:
    lines = []
    for i in range(count):
        lines.append(json.dumps({
            "task_type": task_type,
            "score": score,
            "plan_steps": [f"step_{i % 3}"],
            "success_criteria": [f"criterion_{i % 3}"],
            "required_evidence": [f"evidence_{i % 3}"],
            "failure_conditions": [f"fail_{i % 3}"],
        }))
    path.write_text("\n".join(lines), encoding="utf-8")


def test_distill_skips_below_threshold(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=5)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert isinstance(result, DistillResult)
    assert "email" in result.types_skipped
    assert "email" not in result.types_processed
    assert not list(contracts.iterdir())


def test_distill_processes_above_threshold(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert "email" in result.types_processed
    out = contracts / "email.json"
    assert out.exists()
    data = json.loads(out.read_text())
    assert "plan_steps" in data
    assert "success_criteria" in data
    assert "required_evidence" in data
    assert "failure_conditions" in data


def test_distill_ignores_low_score_examples(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15, score=0.5)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=True)
    assert "email" in result.types_skipped
    assert not list(contracts.iterdir())


def test_distill_dry_run_no_files(tmp_path):
    ex = tmp_path / "examples.jsonl"
    _write_examples(ex, "email", count=15)
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, examples_path=ex, contracts_dir=contracts, apply=False)
    assert "email" in result.types_processed
    assert result.applied is False
    assert not list(contracts.iterdir())


def test_distill_missing_examples_file(tmp_path):
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(
        min_examples=10,
        examples_path=tmp_path / "missing.jsonl",
        contracts_dir=contracts,
        apply=True,
    )
    assert result.types_processed == []
    assert result.types_skipped == []


def test_distill_task_type_filter(tmp_path):
    ex = tmp_path / "examples.jsonl"
    lines = (
        [json.dumps({"task_type": "email", "score": 1.0, "plan_steps": ["s1"],
                     "success_criteria": ["c1"], "required_evidence": ["e1"], "failure_conditions": ["f1"]})] * 15 +
        [json.dumps({"task_type": "lookup", "score": 1.0, "plan_steps": ["s2"],
                     "success_criteria": ["c2"], "required_evidence": ["e2"], "failure_conditions": ["f2"]})] * 15
    )
    ex.write_text("\n".join(lines), encoding="utf-8")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    result = run_distill(min_examples=10, task_type="email", examples_path=ex,
                         contracts_dir=contracts, apply=True)
    assert "email" in result.types_processed
    assert "lookup" not in result.types_processed
    assert not (contracts / "lookup.json").exists()
